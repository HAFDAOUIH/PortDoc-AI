"""Citation parser — the contract that turns 'grounding' from a hope into validation."""

from portdoc.generation.citations import parse_answer


def test_valid_citations_extracted_and_kept():
    r = parse_answer("Le navire doit notifier 48h avant [1]. C'est obligatoire [2][3].", n_sources=3)
    assert r.refused is False
    assert r.citations == [1, 2, 3]
    assert r.hallucinated == []
    assert "[1]" in r.text and "[3]" in r.text  # valid markers preserved for the UI


def test_hallucinated_citation_stripped_and_flagged():
    # only 3 sources given, model invents [7]
    r = parse_answer("Cette règle existe [7]. Elle est confirmée [2].", n_sources=3)
    assert r.hallucinated == [7]
    assert r.citations == [2]
    assert "[7]" not in r.text       # invented marker removed
    assert "[2]" in r.text


def test_refusal_sentinel_detected():
    r = parse_answer("<NO_ANSWER/> L'information n'est pas dans les documents.", n_sources=5)
    assert r.refused is True
    assert "<NO_ANSWER/>" not in r.text  # sentinel removed from displayed text


def test_uncited_factual_sentence_flagged():
    r = parse_answer(
        "Le port applique le niveau de sûreté 3 en cas de menace imminente. "
        "Cette mesure est définie par le code ISPS [1].",
        n_sources=2,
    )
    # first sentence (>=5 words, no [n]) flagged; second is cited
    assert len(r.uncited_sentences) == 1
    assert "niveau de sûreté 3" in r.uncited_sentences[0]


def test_short_fragments_not_flagged_as_uncited():
    r = parse_answer("Oui. C'est correct [1].", n_sources=1)
    assert r.uncited_sentences == []  # "Oui." is too short to be a factual claim


def test_refusal_has_no_uncited_flags():
    r = parse_answer("<NO_ANSWER/> Aucune information disponible sur ce sujet précis.", n_sources=3)
    assert r.refused is True
    assert r.uncited_sentences == []
