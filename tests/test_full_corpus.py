"""Semantic answer regressions use the entire shipped corpus, including distractors."""
import shutil

import pytest

from app import config, generate, ingest, main, query, retrieve, scheduler
from app.store import Store


@pytest.fixture(scope="module")
def full_corpus(tmp_path_factory):
    directory = tmp_path_factory.mktemp("full-corpus")
    shutil.copytree(config.ROOT / "data" / "seed", directory / "seed")
    with pytest.MonkeyPatch.context() as patch:
        for name, sub in (("SEED_DIR", "seed"), ("INDEX_DIR", "index"), ("UPLOAD_DIR", "uploads")):
            path = directory / sub
            path.mkdir(exist_ok=True)
            patch.setattr(config, name, path)
        store = Store()
        for module in (ingest, main, retrieve, scheduler):
            patch.setattr(module, "store", store)
        ingest.reindex_seed()
        yield store


@pytest.mark.parametrize("question,required,forbidden", [
    ("How many backlog subjects can I register in one attempt?", ["six"], ["half the second"]),
    ("What marks do I need in HSC to apply?", ["45", "physics", "mathematics"], ["diploma"]),
    ("How much is the mess bill every month?", ["4,200", "month"], ["62,000", "48,000"]),
    ("I stay far away from campus, can I get a room", ["50 kilometres", "priority"], ["parking"]),
    ("What time does the accounts section open?", ["10:00", "16:00"], []),
    ("How many KT papers can I take at once?", ["six"], ["half the second"]),
    ("What are the higher secondary marks required for first year admission?", ["45", "physics"], ["diploma"]),
    ("What is the monthly mess charge?", ["4,200"], ["62,000"]),
    ("I live far from campus and need a room", ["50 kilometres"], ["parking"]),
    ("When can I visit Accounts about a failed payment?", ["10:00", "16:00"], []),
    ("How much does one year of ME cost?", ["96,000", "8,000"], ["1,45,000", "45,000"]),
    ("What is the annual hostel room fee?", ["62,000", "48,000"], []),
    ("How many credits does Semester V have now?", ["semester v ", "22 to 21"], ["semester vi"]),
    ("What happens if my attendance is below 65 percent?", ["below 65", "not permitted"], ["may condone"]),
    ("How much does a transcript cost and how long does it take?", ["750", "ten working days"], []),
    ("How do I get a duplicate identity card?", ["200", "complaint", "acknowledgement"], []),
])
def test_answer_contains_the_requested_fact(full_corpus, question, required, forbidden):
    result = generate.answer(question)
    answer = result["answer"].lower()
    assert not result["refused"], result
    assert all(x in answer for x in required), answer
    assert not any(x in answer for x in forbidden), answer
    assert result["citations"]
    for citation in result["citations"]:
        assert f"[{citation['n']}]" in result["answer"]
        source = ingest.document_text(full_corpus.docs[citation["doc_id"]]).lower()
        assert all(x in source for x in required)


@pytest.mark.parametrize("institution", [
    "IIT Bombay", "iit bombay", "IiT BoMbAy", "Stanford University",
    "stanford university", "Harvard College", "harvard college",
    "Massachusetts Institute of Technology", "massachusetts institute of technology",
])
def test_other_institutions_are_refused_before_generation(full_corpus, monkeypatch, institution):
    def must_not_generate(*args, **kwargs):
        pytest.fail("unsupported institution reached the generator")
    monkeypatch.setattr(generate.llm, "complete", must_not_generate)
    answer = generate.answer(f"What is the syllabus of the {institution} machine learning course?")
    assert answer["refused"] and not answer["citations"]


@pytest.mark.parametrize("question", [
    "What are this college's fees?", "What are the college hostel rules?",
    "What are the fees at the Institute of Engineering & Technology?",
    "What are the fees at the institute of engineering and technology?",
])
def test_own_college_is_not_misidentified(question):
    assert query.institutions(question) == []


def test_institution_tokens_do_not_match_inside_other_words():
    assert not query.mentions("Students admitted to the programme", "MIT")


def test_rewrite_cannot_discard_an_explicit_institution(full_corpus, monkeypatch):
    monkeypatch.setattr(generate, "rewrite_question", lambda *args: "What are the college fees?")
    result = generate.answer("and at harvard college?", [{"role": "user", "content": "What are the fees?"}])
    assert result["refused"] and not result["citations"]


def test_refresh_is_idempotent_on_full_corpus(full_corpus):
    counts = full_corpus.stats()
    scheduler.refresh()
    scheduler.refresh()
    after = full_corpus.stats()
    for key in ("documents", "chunks", "vectors"):
        assert counts[key] == after[key]


@pytest.mark.parametrize("failure", ["none", "error", "timeout"])
@pytest.mark.parametrize("previous,question,required,forbidden", [
    ("What is the tuition fee for BE?", "And for ME?", ["96,000"], ["1,45,000", "72,500"]),
    ("What is the tuition fee for ME?", "And for BE?", ["1,45,000"], ["96,000"]),
    ("How much does hostel mess cost?", "And the annual room fee?", ["62,000", "48,000"], ["4,200"]),
    ("What is the revaluation fee?", "What is the hostel curfew?", ["22:30"], ["800", "1,000"]),
])
def test_followups_prioritise_latest_question_without_model(
        full_corpus, monkeypatch, failure, previous, question, required, forbidden):
    def fail(*args, **kwargs):
        raise {"none": generate.llm.NoGenerator, "error": RuntimeError,
               "timeout": generate.llm.Timeout}[failure]("QA model unavailable")
    monkeypatch.setattr(generate.llm, "complete", fail)
    result = generate.answer(question, [{"role": "user", "content": previous}])
    assert not result["refused"], result
    assert all(x in result["answer"] for x in required), result
    assert not any(x in result["answer"] for x in forbidden), result
    assert result["citations"]


@pytest.mark.parametrize("institution", ["Oxford", "oxford", "Harvard", "stanford"])
def test_bare_institution_names_are_not_answered_with_local_rules(full_corpus, institution):
    result = generate.answer(f"What is the attendance policy at {institution}?")
    assert result["refused"] and not result["citations"]


def test_semester_vi_cannot_use_semester_v_payment_extension(full_corpus):
    result = generate.answer("What is the Semester VI tuition fee payment deadline?")
    assert result["refused"], result


@pytest.mark.parametrize("percentage", ["64 percent", "70 percent", "64%"])
def test_numeric_attendance_answer_includes_condonation_limits(full_corpus, percentage):
    result = generate.answer(f"Can I attend exams with {percentage} attendance?")
    assert not result["refused"]
    assert "75" in result["answer"]
    assert "65" in result["answer"]
    assert "not permitted" in result["answer"]
    assert "medical" in result["answer"]
    assert len(result["citations"]) == 2
