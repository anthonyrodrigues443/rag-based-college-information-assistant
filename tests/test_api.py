"""The routes a citation and a browser depend on.

Issue #7 (a citation could not be opened) and issue #21 (/favicon.ico answered 404).
"""
import pytest
from fastapi.testclient import TestClient

from app import config, ingest
from app.store import store


@pytest.fixture(scope="module")
def client(indexed):
    from app.main import app
    with TestClient(app) as test_client:
        yield test_client


def test_favicon_is_served(client):
    response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/x-icon"
    assert response.content[:4] == b"\x00\x00\x01\x00", "a real ICO, not an HTML error page"


def test_both_pages_link_the_icon():
    for page in ("index.html", "admin.html", "source.html"):
        markup = (config.WEB_DIR / page).read_text(encoding="utf-8")
        assert 'rel="icon"' in markup, page


def test_a_cited_document_can_be_read_in_full(client, indexed):
    answer = client.post("/api/chat", json={
        "question": "How much is the late fee if I pay after the last date?"}).json()
    assert answer["citations"]
    doc_id = answer["citations"][0]["doc_id"]

    document = client.get(f"/api/site/document/{doc_id}").json()
    assert document["title"]
    assert "Rs. 500" in document["text"], "the full policy, not the 420-character preview"
    assert len(document["text"]) > len(answer["citations"][0]["preview"])


def test_the_source_page_is_public(client, indexed):
    doc_id = next(iter(indexed.docs))
    assert client.get(f"/source/{doc_id}").status_code == 200


def test_an_unknown_document_is_a_404_not_a_crash(client):
    assert client.get("/api/site/document/does-not-exist").status_code == 404


def test_a_crafted_key_cannot_reach_outside_the_corpus(indexed):
    """`key` decides which file is read back, and it comes from an upload."""
    for key in ("../../../../etc/passwd", "/etc/passwd", "..", "sub/dir/file.md"):
        assert ingest.source_path({"origin": "upload", "key": key}) is None


def test_a_pasted_document_still_has_readable_text(client, indexed):
    """Pasted text has no file behind it, so it is rebuilt from the indexed chunks."""
    body = ("The examination cell issues hall tickets four working days before the first "
            "paper and a student without one is not permitted inside the hall on any day.")
    ingest.index_text(body, title="Hall ticket rules", source="Pasted text",
                      key="pasted:Hall ticket rules", origin="upload")
    doc_id = ingest.doc_id_for("pasted:Hall ticket rules", "upload")

    document = client.get(f"/api/site/document/{doc_id}").json()
    assert "hall tickets four working days" in document["text"]
    store.delete_document(doc_id)


def test_the_chat_response_reports_where_the_time_went(client, indexed):
    payload = client.post("/api/chat", json={"question": "What is the revaluation fee?"}).json()
    for field in ("retrieval_ms", "generation_ms", "latency_ms", "degraded", "mode"):
        assert field in payload, field


def test_notices_never_carry_an_unusable_date(client, indexed):
    for item in client.get("/api/site/notices").json()["items"]:
        assert ingest.clean_date(item["date"]) == item["date"]
