"""Document metadata comes from files staff did not write.

Issue #1 (HTML in `kind` ran in the admin console), issue #14 (an impossible month
broke citation rendering) and issue #16 (an uploaded contact.md replaced the seeded one).
"""
import pytest

from app import ingest


@pytest.mark.parametrize("value", [
    '<img src=x onerror="document.documentElement.dataset.qaXss=1">',
    "<script>alert(1)</script>",
    "circulars",          # close, but not a supported kind
    "",
    None,
    123,
])
def test_unsupported_kind_falls_back_to_the_default(value):
    assert ingest.clean_kind(value) == "page"
    assert ingest.clean_kind(value, "pdf") == "pdf"


@pytest.mark.parametrize("value,expected", [
    ("circular", "circular"),
    ("  Notice ", "notice"),
    ("HANDBOOK", "handbook"),
])
def test_supported_kinds_survive(value, expected):
    assert ingest.clean_kind(value) == expected


@pytest.mark.parametrize("value", [
    "2026-13-01",         # the month reported in the issue
    "2026-00-10",
    "2026-02-30",
    "14 August 2026",
    "2026/08/14",
    "20260814",
    "",
    None,
])
def test_impossible_dates_become_empty(value):
    assert ingest.clean_date(value) == ""


def test_real_dates_survive():
    assert ingest.clean_date("2026-08-14") == "2026-08-14"
    assert ingest.clean_date(" 2028-02-29 ") == "2028-02-29"   # 2028 is a leap year


def test_the_calendar_is_consulted_not_just_the_shape():
    assert ingest.clean_date("2026-02-29") == ""               # 2026 is not a leap year


@pytest.mark.parametrize("value", [
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "/etc/passwd",
    "ftp://example.edu/fees",
    None,
])
def test_only_http_urls_are_kept(value):
    assert ingest.clean_url(value) == ""


def test_http_urls_survive():
    assert ingest.clean_url("https://example.edu/fees") == "https://example.edu/fees"


def test_identity_is_namespaced_by_origin():
    """An uploaded contact.md must not be the same document as the seeded contact.md."""
    assert ingest.doc_id_for("contact.md", "seed") != ingest.doc_id_for("contact.md", "upload")
    assert ingest.doc_id_for("contact.md", "seed") == ingest.doc_id_for("contact.md", "seed")


def test_hostile_front_matter_is_neutralised_at_ingestion(indexed, tmp_path):
    upload = tmp_path / "evening-lab.md"
    upload.write_text(
        "---\n"
        "title: Laboratory access notice for the evening batch\n"
        'kind: <img src=x onerror="document.documentElement.dataset.qaXss=1">\n'
        "date: 2026-13-01\n"
        "url: javascript:alert(1)\n"
        "---\n\n"
        "The machine learning laboratory in the east wing opens at nineteen hundred hours "
        "for the evening batch and closes at twenty two hundred hours on working days.\n",
        encoding="utf-8")

    result = ingest.index_file(upload, origin="upload")
    assert result["chunks"] == 1

    doc = indexed.docs[ingest.doc_id_for(upload.name, "upload")]
    assert doc["kind"] == "page"
    assert doc["date"] == ""
    assert doc["url"] == ""
    assert "<img" not in doc["kind"]

    indexed.delete_document(doc["doc_id"])


def test_upload_does_not_replace_a_seeded_document_of_the_same_name(indexed, tmp_path, seed_dir):
    """The exact scenario in issue #16: same file name, unrelated content."""
    name = "departments-aiml.md"
    before = indexed.stats()
    seeded_id = ingest.doc_id_for(name, "seed")
    seeded_title = indexed.docs[seeded_id]["title"]

    upload = tmp_path / name
    upload.write_text(
        "---\ntitle: Student photography club schedule\nkind: page\n---\n\n"
        "The photography club meets in the seminar hall on the first Saturday of every "
        "month at four in the afternoon and welcomes students from every department.\n",
        encoding="utf-8")
    ingest.index_file(upload, origin="upload")

    after = indexed.stats()
    assert after["documents"] == before["documents"] + 1
    assert after["seed_documents"] == before["seed_documents"]
    assert indexed.docs[seeded_id]["title"] == seeded_title

    uploaded_id = ingest.doc_id_for(name, "upload")
    assert indexed.docs[uploaded_id]["title"] == "Student photography club schedule"
    indexed.delete_document(uploaded_id)


def test_reindexing_the_same_key_and_origin_is_reported_as_a_replacement(indexed, tmp_path):
    upload = tmp_path / "notice.md"
    body = ("The library reading room stays open until midnight during the examination "
            "period and closes at eight in the evening for the rest of the semester.\n")
    upload.write_text(body, encoding="utf-8")

    first = ingest.index_file(upload, origin="upload")
    second = ingest.index_file(upload, origin="upload")
    assert "replaced" not in first
    assert second["replaced"] is True

    indexed.delete_document(ingest.doc_id_for(upload.name, "upload"))
