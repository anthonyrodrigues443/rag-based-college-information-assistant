"""Retrieval has to be about the same thing the question is about.

Issue #3 (an M.E. question answered with B.E. rates), issue #4 (another institution's
course answered from this college's syllabus) and issue #5 (answerable questions refused).
"""
import pytest

from app import generate, query, retrieve


# ------------------------------------------------------------------ normalisation
def test_a_capitalised_programme_abbreviation_is_expanded():
    expanded = query.expand("How much does one year of ME cost?")
    assert "master of engineering" in expanded
    assert "postgraduate" in expanded


def test_the_pronoun_me_is_left_alone():
    """The whole reason the expansion is case sensitive."""
    assert query.expand("Can you help me with the fee?") == "Can you help me with the fee?"


def test_a_department_abbreviation_is_expanded():
    assert "artificial intelligence" in query.expand("How many seats does the AIML department have?")


def test_a_colloquial_paraphrase_reaches_the_official_wording():
    expanded = query.expand("my answer sheet was marked badly, can it be checked again")
    assert "answer book" in expanded
    assert "revaluation" in expanded


def test_programme_is_read_from_the_expanded_question():
    assert query.entities("How much does one year of ME cost?")["programme"] == {"pg"}
    assert "ug" in query.entities("How much does one year of BE cost?")["programme"]


def test_a_named_institution_is_picked_out():
    assert query.institutions("What is the syllabus of the IIT Bombay machine learning course?") \
        == ["IIT Bombay"]


def test_this_college_is_not_treated_as_a_foreign_institution():
    assert query.institutions("What does the institute fee structure say?") == []
    assert query.institutions("What are the college hostel rules?") == []


# ------------------------------------------------------------------ the reported questions
def test_a_postgraduate_fee_question_gets_the_postgraduate_section(indexed):
    result = generate.answer("How much does one year of ME cost?")
    assert not result["refused"]
    assert "96,000" in result["answer"]
    assert "1,45,000" not in result["answer"], "these are the undergraduate rates"


def test_a_postgraduate_admission_question_gets_the_postgraduate_section(indexed):
    result = generate.answer("Which entrance exam do I need for the ME programme?")
    assert not result["refused"]
    assert "postgraduate entrance test" in result["answer"].lower()


def test_the_undergraduate_questions_still_work(indexed):
    """The fix must not simply swap which programme is wrong."""
    fee = generate.answer("How much does one year of BE cost?")
    assert "1,45,000" in fee["answer"]
    admission = generate.answer("Which entrance exam do I need for first year admission?")
    assert "common entrance test" in admission["answer"].lower()


def test_a_question_about_another_institution_is_refused(indexed):
    result = generate.answer("What is the syllabus of the IIT Bombay machine learning course?")
    assert result["refused"], result["answer"]
    assert result["citations"] == []
    assert "IIT Bombay" in result["debug"]["refused_because"]


def test_an_abbreviated_department_question_is_answered(indexed):
    result = generate.answer("How many seats does the AIML department have?")
    assert not result["refused"], result["answer"]
    assert "sixty" in result["answer"].lower()


def test_a_paraphrased_revaluation_question_is_answered(indexed):
    result = generate.answer("my answer sheet was marked badly, can it be checked again")
    assert not result["refused"], result["answer"]
    assert "revaluation" in result["answer"].lower()


# ------------------------------------------------------------------ the gate itself
def test_the_gate_allows_an_institution_the_corpus_does_describe():
    results = [{"title": "Partner institutes", "text": "IIT Bombay runs the joint programme.",
                "rerank": 5.0, "entity": 0}]
    assert retrieve.unsupported("What does IIT Bombay run?", results) is None


def test_the_gate_refuses_when_nothing_retrieved_mentions_the_institution():
    results = [{"title": "Third-year syllabus revision", "text": "Credits change from 22 to 21.",
                "rerank": 5.0, "entity": 0}]
    assert retrieve.unsupported("What is the IIT Bombay syllabus?", results)


def test_the_gate_refuses_when_every_section_is_a_different_programme():
    results = [{"title": "Fees", "text": "B.E. tuition is Rs. 1,45,000 for undergraduate students.",
                "rerank": 5.0, "entity": -1}]
    assert retrieve.unsupported("How much does one year of ME cost?", results)


def test_the_gate_says_nothing_when_there_is_nothing_to_object_to():
    results = [{"title": "Fees", "text": "M.E. tuition is Rs. 96,000.", "rerank": 5.0, "entity": 1}]
    assert retrieve.unsupported("How much does one year of ME cost?", results) is None


def test_an_empty_result_set_is_refused():
    assert retrieve.unsupported("anything at all", [])
