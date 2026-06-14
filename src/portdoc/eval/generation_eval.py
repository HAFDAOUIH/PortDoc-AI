"""Generation evaluation — the RAG triad (context · faithfulness · answer relevance) + refusal.

Four signals on the live pipeline, graded *strictly*:

  context relevance  — are the retrieved passages actually relevant to the question?
                       (judge, per passage) -> precision@k
  faithfulness       — is every cited claim supported by its cited source?
                       (judge, per claim, STRICT — claims that add unsourced detail fail)
  answer relevance   — does the answer actually address the question?
                       (judge, per answer: yes/partial/no -> 1.0/0.5/0.0)
  refusal accuracy   — correct <NO_ANSWER/> on OOC/adversarial, no over-refusal on
                       answerable ones. DETERMINISTIC (exact sentinel, no judge).

The judge (config.judge_*) is a SEPARATE, stronger model run OFFLINE over PUBLIC docs;
the served product (config.llm_*) stays fully local.

Run:  uv run python -m portdoc.eval.generation_eval   (or: make eval-gen)
"""

from __future__ import annotations

import json
import time

from portdoc.config import get_settings
from portdoc.generation.answer import generate
from portdoc.generation.citations import CITE_RE, _SENT_SPLIT
from portdoc.retrieval.pipeline import retrieve

FAITH_SYS = (
    "You are a STRICT grader of factual grounding for a French port-security assistant. "
    "A CLAIM is 'supported' ONLY if the SOURCE explicitly states it or it follows by direct, "
    "unambiguous entailment. If the claim adds any specific detail (a number, condition, entity, "
    "or obligation) not present in the SOURCE, mark it NOT supported. Judge only on the source text "
    '— never on world knowledge or plausibility. Reply with JSON only: {"supported": true|false, "reason": "<short>"}.'
)
CTX_SYS = (
    "You are a STRICT relevance grader for a French port-security retrieval system. "
    "A PASSAGE is 'relevant' ONLY if it contains information that directly helps answer the QUESTION. "
    "Passages that are merely on the same topic, or that mention the keywords without answering, are NOT "
    'relevant. Reply with JSON only: {"relevant": true|false}.'
)
ANS_SYS = (
    "You grade whether an ANSWER addresses a QUESTION for a French port assistant. "
    'Reply with JSON only: {"addresses": "yes"|"partial"|"no"} — '
    "'yes' = directly and adequately answers; 'partial' = related but incomplete or evasive; "
    "'no' = does not answer the question."
)


def _judge_model_kwargs() -> tuple[str, dict]:
    s = get_settings()
    if s.judge_backend == "ollama":
        return f"ollama_chat/{s.judge_model}", {"api_base": s.llm_api_base or "http://localhost:11434"}
    if s.judge_backend == "vllm":
        return f"openai/{s.judge_model}", {"api_base": s.llm_api_base, "api_key": s.llm_api_key or "EMPTY"}
    return s.judge_model, ({"api_key": s.llm_api_key} if s.llm_api_key else {})


def _judge_json(system: str, user: str) -> dict | None:
    """One strict judge call returning a parsed dict, or None if the call failed."""
    import litellm

    litellm.drop_params = True  # drop params a given judge model rejects (e.g. temperature)
    model, kw = _judge_model_kwargs()
    try:
        resp = litellm.completion(
            model=model, temperature=0.0, max_tokens=200,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_object"}, **kw,
        )
        raw = resp.choices[0].message.content or "{}"
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            a, b = raw.find("{"), raw.rfind("}")
            return json.loads(raw[a : b + 1]) if a != -1 else {}
    except Exception as exc:  # noqa: BLE001 — a judge error must not abort the whole eval
        print(f"    [judge error] {exc!r}")
        return None


def judge_faithful(claim: str, context: str) -> bool | None:
    d = _judge_json(FAITH_SYS, f"SOURCE:\n{context}\n\nCLAIM:\n{claim}\n\nIs the CLAIM fully supported by the SOURCE?")
    return None if d is None else bool(d.get("supported", False))


def judge_relevant(question: str, passage: str) -> bool | None:
    d = _judge_json(CTX_SYS, f"QUESTION:\n{question}\n\nPASSAGE:\n{passage}\n\nIs the PASSAGE relevant to answering the QUESTION?")
    return None if d is None else bool(d.get("relevant", False))


def judge_answer_rel(question: str, answer: str) -> float | None:
    d = _judge_json(ANS_SYS, f"QUESTION:\n{question}\n\nANSWER:\n{answer}\n\nDoes the ANSWER address the QUESTION?")
    if d is None:
        return None
    return {"yes": 1.0, "partial": 0.5, "no": 0.0}.get(str(d.get("addresses", "")).lower(), 0.0)


def _cited_sentences(text: str) -> list[tuple[str, list[int]]]:
    """(sentence, cited [n]) for factual sentences carrying >=1 citation."""
    out = []
    for sent in _SENT_SPLIT.split(text):
        s = sent.strip()
        nums = sorted({int(x) for x in CITE_RE.findall(s)})
        if nums and len(s.split()) >= 4:
            out.append((s, nums))
    return out


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def run() -> dict:
    s = get_settings()
    s.ensure_dirs()
    data = json.loads((s.eval_dir / "qa_dataset.json").read_text(encoding="utf-8"))
    items = data["items"]
    have_judge = (s.judge_backend != "openai") or bool(s.llm_api_key)

    print(f"Served: {s.llm_model} ({s.llm_backend})  |  Judge: {s.judge_model} ({s.judge_backend})"
          f"{'' if have_judge else '  [no judge key — refusal only]'}\n")

    g_total = g_ans = r_total = r_correct = c_total = c_sup = 0
    over_ref: list[str] = []
    halluc: list[str] = []
    ctx_scores: list[float] = []
    ctx_rr_scores: list[float] = []  # context relevance with rerank=ON (precision comparison)
    ans_scores: list[float] = []
    faith_scores: list[float] = []
    detail: list[dict] = []  # per-grounded-question breakdown

    for item in items:
        typ = item["type"]
        qid, q = item["id"], item["question"]
        clr = item.get("expected_clearance", 2) if typ == "grounded" else 2
        t0 = time.perf_counter()
        chunks = retrieve(q, user_clearance=clr, rerank=False)

        if typ != "grounded":
            ans = generate(q, chunks)
            r_total += 1
            if ans.refused:
                r_correct += 1
                tag = "OK refused"
            else:
                halluc.append(qid)
                tag = "XX ANSWERED (should refuse)"
            print(f"  {typ:<12} {qid:<16} {tag}  ({time.perf_counter() - t0:.0f}s)")
            continue

        # --- grounded: context relevance (per retrieved passage) ---
        g_total += 1
        ctx = ctx_rr = None
        if have_judge and chunks:
            rels = [judge_relevant(q, c.payload["raw_text"]) for c in chunks]
            rels = [r for r in rels if r is not None]
            if rels:
                ctx = sum(rels) / len(rels)
                ctx_scores.append(ctx)
            # rerank=ON comparison: re-retrieve top-5 through the cross-encoder, re-judge.
            # Only an extra retrieve+judge — generation below still uses the rerank=OFF chunks.
            rr_chunks = retrieve(q, user_clearance=clr, rerank=True)
            rr_rels = [judge_relevant(q, c.payload["raw_text"]) for c in rr_chunks]
            rr_rels = [r for r in rr_rels if r is not None]
            if rr_rels:
                ctx_rr = sum(rr_rels) / len(rr_rels)
                ctx_rr_scores.append(ctx_rr)

        ans = generate(q, chunks)
        if ans.refused:
            over_ref.append(qid)
            detail.append({"id": qid, "ctx": ctx, "ctx_rr": ctx_rr, "ans_rel": None, "faith": None, "refused": True})
            print(f"  grounded     {qid:<16} refused=True  ! over-refusal  ({time.perf_counter() - t0:.0f}s)")
            continue

        g_ans += 1
        ans_rel = faith = None
        sup = tot = 0
        if have_judge:
            ans_rel = judge_answer_rel(q, ans.text)
            if ans_rel is not None:
                ans_scores.append(ans_rel)
            smap = {src.n: src.raw_text for src in ans.sources}
            for sent, nums in _cited_sentences(ans.text):
                context = "\n\n".join(smap[n] for n in nums if n in smap)
                if not context:
                    continue
                v = judge_faithful(sent, context)
                if v is None:
                    continue
                tot += 1
                sup += int(v)
            c_total += tot
            c_sup += sup
            if tot:
                faith = sup / tot
                faith_scores.append(faith)

        detail.append({"id": qid, "ctx": ctx, "ctx_rr": ctx_rr, "ans_rel": ans_rel,
                       "faith": (f"{sup}/{tot}" if tot else None), "refused": False})
        print(f"  grounded     {qid:<16} ctx={_fmt(ctx)} ctx_rr={_fmt(ctx_rr)} ans_rel={_fmt(ans_rel)} "
              f"faith={f'{sup}/{tot}' if tot else 'n/a'}  ({time.perf_counter() - t0:.0f}s)")

    res = {
        "served_model": s.llm_model, "judge_model": s.judge_model, "judge_backend": s.judge_backend,
        "n_questions": len(items), "grounded_total": g_total, "grounded_answered": g_ans,
        "over_refusals": over_ref, "refuse_total": r_total, "refuse_correct": r_correct,
        "hallucinated": halluc,
        "context_relevance": _mean(ctx_scores), "context_judged": len(ctx_scores),
        "context_relevance_reranked": _mean(ctx_rr_scores), "context_reranked_judged": len(ctx_rr_scores),
        "answer_relevance": _mean(ans_scores), "answer_judged": len(ans_scores),
        "faithfulness": _mean(faith_scores), "faith_judged": len(faith_scores),
        "claims_total": c_total, "claims_supported": c_sup,
        "detail": detail,
    }
    _write(s, res)
    return res


def _fmt(x) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


def _ctx_compare(r: dict) -> str:
    """One-line 'rerank off X% vs on Y%' verdict for the context-precision comparison."""
    off, on = r.get("context_relevance"), r.get("context_relevance_reranked")
    base = f"**Context precision: rerank off {_fmt(off)} vs on {_fmt(on)}**"
    if off is None or on is None:
        return base + "."
    d = (on - off) * 100
    if abs(d) < 1e-9:
        return base + " — reranking left precision unchanged."
    if d > 0:
        return base + f" — reranking lifts precision by {d:+.0f} pts."
    return base + f" — reranking did not help ({d:+.0f} pts)."


def _write(s, r: dict) -> None:
    over = (" -> " + ", ".join(r["over_refusals"])) if r["over_refusals"] else ""
    hall = (" -> " + ", ".join(r["hallucinated"])) if r["hallucinated"] else ""
    ctx_cmp = _ctx_compare(r)
    rows = "\n".join(
        f"| {d['id']} | {_fmt(d['ctx'])} | {_fmt(d.get('ctx_rr'))} | "
        f"{('refused' if d['refused'] else _fmt(d['ans_rel']))} | "
        f"{(d['faith'] or ('refused' if d['refused'] else 'n/a'))} |"
        for d in r["detail"]
    )
    md = f"""# Generation Evaluation — RAG triad + refusal accuracy

Served model: `{r['served_model']}` (local). Judge: `{r['judge_model']}` ({r['judge_backend']}), strict rubric, temp 0.
{r['n_questions']} questions ({r['grounded_total']} grounded, {r['refuse_total']} out-of-corpus/adversarial).

## The RAG triad (LLM-judged, strict)

| Metric | Score | What it proves |
|---|---|---|
| **Context relevance** (precision@5, rerank OFF, over {r['context_judged']} Qs) | **{_fmt(r['context_relevance'])}** | retrieval surfaces passages that actually help |
| Context relevance (precision@5, rerank ON, over {r['context_reranked_judged']} Qs) | **{_fmt(r['context_relevance_reranked'])}** | cross-encoder rerank of the top-20 candidates |
| **Faithfulness** (over {r['faith_judged']} answers, {r['claims_supported']}/{r['claims_total']} claims) | **{_fmt(r['faithfulness'])}** | every cited claim is backed by its source |
| **Answer relevance** (over {r['answer_judged']} answers) | **{_fmt(r['answer_relevance'])}** | answers actually address the question |

{ctx_cmp} (cross-encoder `BAAI/bge-reranker-base` over the top-20, returning the reranked top-5).

## Refusal accuracy — deterministic (`<NO_ANSWER/>` sentinel, no judge)

|  | model answered | model refused |
|---|---|---|
| **should answer** (grounded, {r['grounded_total']}) | OK {r['grounded_answered']} correct | {len(r['over_refusals'])} over-refusal |
| **should refuse** (OOC+adversarial, {r['refuse_total']}) | {len(r['hallucinated'])} hallucinated | OK {r['refuse_correct']} correct |

- Out-of-corpus / adversarial correctly refused: **{r['refuse_correct']}/{r['refuse_total']}** — the "won't invent a procedure" signal
- Hallucinated answers (should-refuse but answered): **{len(r['hallucinated'])}**{hall}
- Over-refusals (should-answer but refused): **{len(r['over_refusals'])}**{over}

## Per-question breakdown (grounded)

| id | context (rerank off) | context (rerank on) | answer rel | faithfulness |
|---|---|---|---|---|
{rows}

*Triad graded by `{r['judge_model']}` — stronger than the served `{r['served_model']}` — offline, over public docs, with a deliberately strict rubric. Refusal is exact-token, no judge in the loop. Product stays 100% local.*
"""
    (s.results_dir / "generation.md").write_text(md, encoding="utf-8")
    (s.results_dir / "generation.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {s.results_dir / 'generation.md'}")


if __name__ == "__main__":
    import sys

    r = run()
    print(f"\nContext {_fmt(r['context_relevance'])} (rerank off) vs {_fmt(r['context_relevance_reranked'])} (rerank on) "
          f"· Faithfulness {_fmt(r['faithfulness'])} "
          f"({r['claims_supported']}/{r['claims_total']}) · Answer-rel {_fmt(r['answer_relevance'])}")
    print(f"Refusal: grounded {r['grounded_answered']}/{r['grounded_total']} answered, "
          f"OOC/adv {r['refuse_correct']}/{r['refuse_total']} refused, {len(r['hallucinated'])} hallucinated")
    sys.exit(0)
