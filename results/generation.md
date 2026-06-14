# Generation Evaluation — RAG triad + refusal accuracy

Served model: `mistral-small:24b` (local). Judge: `gpt-4o` (openai), strict rubric, temp 0.
19 questions (10 grounded, 9 out-of-corpus/adversarial).

## The RAG triad (LLM-judged, strict)

| Metric | Score | What it proves |
|---|---|---|
| **Context relevance** (precision@5, rerank OFF, over 10 Qs) | **48%** | retrieval surfaces passages that actually help |
| Context relevance (precision@5, rerank ON, over 10 Qs) | **62%** | cross-encoder rerank of the top-20 candidates |
| **Faithfulness** (over 10 answers, 20/21 claims) | **90%** | every cited claim is backed by its source |
| **Answer relevance** (over 10 answers) | **95%** | answers actually address the question |

**Context precision: rerank off 48% vs on 62%** — reranking lifts precision by +14 pts. (cross-encoder `BAAI/bge-reranker-base` over the top-20, returning the reranked top-5).

## Refusal accuracy — deterministic (`<NO_ANSWER/>` sentinel, no judge)

|  | model answered | model refused |
|---|---|---|
| **should answer** (grounded, 10) | OK 10 correct | 0 over-refusal |
| **should refuse** (OOC+adversarial, 9) | 0 hallucinated | OK 9 correct |

- Out-of-corpus / adversarial correctly refused: **9/9** — the "won't invent a procedure" signal
- Hallucinated answers (should-refuse but answered): **0**
- Over-refusals (should-answer but refused): **0**

## Per-question breakdown (grounded)

| id | context (rerank off) | context (rerank on) | answer rel | faithfulness |
|---|---|---|---|---|
| md-notif | 40% | 60% | 100% | 1/1 |
| portnet | 80% | 100% | 100% | 1/1 |
| niveau3-ip | 40% | 100% | 100% | 2/2 |
| pup-qui | 40% | 20% | 100% | 1/1 |
| controle-acces | 60% | 40% | 100% | 4/4 |
| identite | 20% | 20% | 50% | 1/1 |
| eval-ssa | 60% | 60% | 100% | 2/2 |
| plan-surete | 40% | 40% | 100% | 4/4 |
| exploitant-oblig | 60% | 100% | 100% | 4/4 |
| incident-surete | 40% | 80% | 100% | 0/1 |

*Triad graded by `gpt-4o` — stronger than the served `mistral-small:24b` — offline, over public docs, with a deliberately strict rubric. Refusal is exact-token, no judge in the loop. Product stays 100% local.*
