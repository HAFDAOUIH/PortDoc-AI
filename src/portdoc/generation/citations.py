"""Citation parser — turns the citation 'grammar' from a prompt hope into a validated output.

It does three jobs (all unit-tested):
  1. extract [n] markers and map them to real sources,
  2. REJECT hallucinated source numbers (e.g. [7] when only 5 sources were given) —
     strip them and flag them,
  3. flag factual sentences that carry NO citation (fed to the faithfulness judge later).

Also detects the <NO_ANSWER/> refusal sentinel.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CITE_RE = re.compile(r"\[(\d+)\]")
REFUSAL_TOKEN = "<NO_ANSWER/>"
# naive but deterministic sentence splitter (good enough to flag uncited claims)
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass
class ParsedAnswer:
    text: str                  # cleaned: hallucinated [n] stripped, sentinel removed
    refused: bool
    citations: list[int]       # valid source numbers actually cited (sorted, unique)
    hallucinated: list[int]    # cited numbers that don't exist (sorted, unique)
    uncited_sentences: list[str]


def parse_answer(raw: str, n_sources: int) -> ParsedAnswer:
    refused = REFUSAL_TOKEN in raw
    body = raw.replace(REFUSAL_TOKEN, "").strip()

    found = [int(x) for x in CITE_RE.findall(body)]
    valid = sorted({n for n in found if 1 <= n <= n_sources})
    hallucinated = sorted({n for n in found if not (1 <= n <= n_sources)})

    # strip ONLY the hallucinated markers; keep valid ones for the UI
    def _strip_bad(m: re.Match) -> str:
        return m.group(0) if 1 <= int(m.group(1)) <= n_sources else ""

    cleaned = CITE_RE.sub(_strip_bad, body)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()

    uncited = _uncited_sentences(cleaned) if not refused else []
    return ParsedAnswer(cleaned, refused, valid, hallucinated, uncited)


def _uncited_sentences(text: str) -> list[str]:
    """Factual-looking sentences (>=5 words) that carry no [n] citation."""
    out = []
    for sent in _SENT_SPLIT.split(text):
        s = sent.strip()
        if len(s.split()) >= 5 and not CITE_RE.search(s):
            out.append(s)
    return out
