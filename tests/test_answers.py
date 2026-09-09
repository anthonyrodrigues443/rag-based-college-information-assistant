"""Extractive answers must carry the amount the student asked for.

Issue #2: the sentence splitter treated the period in "Rs." as a sentence boundary, so
"a late fee of Rs. 500" was served as "a late fee of Rs.".
"""
import pytest

from app import generate


def test_an_abbreviation_does_not_end_a_sentence():
    text = ("Payments made after 29 August 2026 attract a late fee of Rs. 500. "
            "No further extension will be granted after this date.")
    assert generate.split_sentences(text) == [
        "Payments made after 29 August 2026 attract a late fee of Rs. 500.",
        "No further extension will be granted after this date.",
    ]


def test_a_dotted_initialism_does_not_end_a_sentence():
    text = "M.E. tuition fee is Rs. 96,000 per year. The laboratory charge is Rs. 8,000 per year."
    assert generate.split_sentences(text) == [
        "M.E. tuition fee is Rs. 96,000 per year.",
        "The laboratory charge is Rs. 8,000 per year.",
    ]


def test_ordinary_sentences_still_split():
    text = "The window opens on Monday. It closes on Friday. Late applications are refused."
    assert len(generate.split_sentences(text)) == 3


# Every amount issue #2 reported as lost, and the M.E. rate from issue #3.
AMOUNTS = [
    ("How much is the late fee if I pay after the last date?", "Rs. 500"),
    ("How much does revaluation of a paper cost?", "Rs. 800"),
    ("What does a photocopy of the answer book cost?", "Rs. 400"),
    ("What is the duplicate identity card charge?", "Rs. 200"),
    ("How much does one year of ME cost?", "Rs. 96,000"),
    ("How much does one year of BE cost?", "Rs. 1,45,000"),
]


@pytest.mark.parametrize("question,amount", AMOUNTS)
def test_extractive_mode_keeps_the_amount(indexed, question, amount):
    result = generate.answer(question)
    assert result["mode"].startswith("extractive"), result["mode"]
    assert not result["refused"], result["answer"]
    assert amount in result["answer"], result["answer"]


@pytest.mark.parametrize("question,amount", AMOUNTS)
def test_generator_failure_falls_back_with_the_amount_intact(indexed, monkeypatch, question, amount):
    """The same path runs when a configured generator errors, not only when none is set."""
    def explode(*args, **kwargs):
        raise RuntimeError("connection reset")

    monkeypatch.setattr(generate.llm, "complete", explode)
    monkeypatch.setattr(generate.llm, "provider", lambda: "ollama")
    result = generate.answer(question)
    assert result["degraded"]["reason"] == "error"
    assert amount in result["answer"], result["answer"]


def test_a_slow_generator_falls_back_and_says_so(indexed, monkeypatch):
    """Issue #6: a stalled generator must not be an undifferentiated wait."""
    def stall(*args, **kwargs):
        raise generate.llm.Timeout("ollama did not answer in time")

    monkeypatch.setattr(generate.llm, "complete", stall)
    monkeypatch.setattr(generate.llm, "provider", lambda: "ollama")
    result = generate.answer("How much is the late fee if I pay after the last date?")

    assert result["degraded"]["reason"] == "timeout"
    assert "quoted from the source" in result["degraded"]["detail"]
    assert result["mode"].startswith("extractive")
    assert "Rs. 500" in result["answer"]
    assert result["citations"], "a fallback answer still has to be cited"


def test_retrieval_and_generation_are_timed_separately(indexed):
    """Issue #6: a long wait has to be attributable to one stage or the other."""
    result = generate.answer("How much is the late fee if I pay after the last date?")
    assert result["retrieval_ms"] >= 0
    assert result["generation_ms"] >= 0
    assert result["latency_ms"] >= result["retrieval_ms"]


def test_a_citation_carries_the_document_it_came_from(indexed):
    """Issue #7: a citation the reader cannot open is not a citation."""
    result = generate.answer("How much is the late fee if I pay after the last date?")
    assert result["citations"]
    for cite in result["citations"]:
        assert cite["doc_id"] in indexed.docs
        assert cite["n"] >= 1
