"""Build the evaluation dataset: hand-authored questions + resolved gold chunk_ids.

We do NOT trust ungated synthetic data. Each grounded question is authored by hand
and tied to a distinctive phrase in a specific document; the resolver finds the
chunk(s) containing that phrase -> gold_chunk_ids, grounded in the ACTUAL current
chunking. Out-of-corpus and adversarial items carry no gold (they test refusal).

§8.4 guard: we stamp a corpus_fingerprint (hash of manifest + chunker config) into
the dataset; the sweep runner hard-fails if the corpus was re-chunked, so gold ids
can never silently drift out of alignment.

Run:  uv run python -m portdoc.eval.make_dataset
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path

from portdoc.config import get_settings

# (id, question, doc_id to search, distinctive phrase, expected min clearance)
# Distinctive phrases (long quotes) so gold pins the answer-bearing chunk(s), not every
# chunk mentioning a common term. Target: small, precise gold sets.
GROUNDED = [
    ("md-notif", "Combien de temps à l'avance faut-il notifier l'arrivée d'un navire transportant des marchandises dangereuses ?", "anp-reglement-casablanca-fr", "48 heures au moins avant", 0),
    ("portnet", "Par quelle plateforme l'agent maritime communique-t-il les informations à la capitainerie ?", "anp-reglement-casablanca-fr", "plate-forme d'échange des données informatisées", 0),
    ("niveau3-ip", "Que doit faire l'installation portuaire au niveau de sûreté 3 ?", "code-isps-fr", "au niveau de sûreté 3, l'installation portuaire", 2),
    ("pup-qui", "Qui doit disposer d'un plan d'urgence portuaire ?", "loi-67-14-surete-portuaire-fr", "plan d'urgence portuaire", 0),
    ("controle-acces", "Comment le contrôle d'accès au port est-il assuré ?", "ilo-surete-ports-fr", "contrôle d'accès", 2),
    ("identite", "Quel document d'identité est prévu pour accéder à l'installation portuaire ?", "ilo-surete-ports-fr", "pièce d'identité", 2),
    ("eval-ssa", "Qui réalise l'évaluation de la sûreté de l'installation portuaire ?", "code-isps-fr", "évaluation de la sûreté de l'installation portuaire", 2),
    ("plan-surete", "Que doit décrire le plan de sûreté de l'installation portuaire ?", "code-isps-fr", "plan de sûreté de l'installation portuaire", 2),
    ("exploitant-oblig", "Quelles sont les obligations de l'exploitant d'une installation portuaire ?", "anp-reglement-casablanca-fr", "l'exploitant d'une installation portuaire doit", 0),
    ("incident-surete", "Qui prévient-on en cas d'incident de sûreté dans le port ?", "anp-reglement-casablanca-fr", "incident de sûreté", 0),
]

OUT_OF_CORPUS = [
    ("ooc-ferry", "Quel est le prix d'un billet de ferry pour Barcelone ?"),
    ("ooc-meteo", "Quelle est la météo prévue au port demain ?"),
    ("ooc-recrut", "Quels postes sont ouverts au recrutement à Tanger Med ?"),
    ("ooc-resto", "Quels restaurants se trouvent près du port ?"),
    ("ooc-bourse", "Quel est le cours de l'action de Tanger Med en bourse aujourd'hui ?"),
]

ADVERSARIAL = [
    ("adv-niveau5", "Que doit faire l'installation portuaire au niveau de sûreté 5 ?"),  # no level 5 exists
    ("adv-terminal99", "Quelles sont les règles d'exploitation du terminal 99 ?"),       # no such terminal
    ("adv-2099", "Quel est le règlement d'exploitation du port pour l'année 2099 ?"),     # wrong year
    ("adv-aerien", "Quelles sont les procédures de sûreté pour le trafic aérien ?"),      # wrong domain
]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def corpus_fingerprint() -> str:
    s = get_settings()
    h = hashlib.sha256()
    h.update(s.manifest_path.read_bytes())
    h.update(f"{s.chunk_max_tokens}|{s.dense_model}|{s.min_chunk_chars}".encode())
    return h.hexdigest()[:16]


def _load_chunks() -> list[dict]:
    path = get_settings().corpus_dir / "chunks.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def resolve_gold(chunks: list[dict], doc_id: str, phrase: str) -> list[str]:
    p = _norm(phrase)
    return [c["chunk_id"] for c in chunks if c["doc_id"] == doc_id and p in _norm(c["raw_text"])]


def build() -> dict:
    chunks = _load_chunks()
    items = []
    print("Resolving gold chunks for grounded questions:")
    for qid, question, doc_id, phrase, clr in GROUNDED:
        gold = resolve_gold(chunks, doc_id, phrase)
        flag = "  <-- ZERO MATCHES, FIX" if not gold else ""
        print(f"  {qid:<18} gold={len(gold):>2}{flag}")
        items.append({"id": qid, "question": question, "type": "grounded",
                      "gold_chunk_ids": gold, "expected_clearance": clr})
    for qid, question in OUT_OF_CORPUS:
        items.append({"id": qid, "question": question, "type": "out_of_corpus", "gold_chunk_ids": []})
    for qid, question in ADVERSARIAL:
        items.append({"id": qid, "question": question, "type": "adversarial", "gold_chunk_ids": []})

    return {"corpus_fingerprint": corpus_fingerprint(), "items": items}


def main() -> int:
    settings = get_settings()
    settings.ensure_dirs()
    dataset = build()
    out = settings.eval_dir / "qa_dataset.json"
    out.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    grounded = [i for i in dataset["items"] if i["type"] == "grounded"]
    zero = [i["id"] for i in grounded if not i["gold_chunk_ids"]]
    print(f"\nWrote {out}: {len(dataset['items'])} items "
          f"({len(grounded)} grounded, fingerprint={dataset['corpus_fingerprint']})")
    if zero:
        print(f"⚠ grounded items with no gold (fix the phrase): {zero}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
