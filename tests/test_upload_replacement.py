"""A skipped or failed replacement must preserve the previously accepted document."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config, ingest, main
from app.store import Store

BODY = ("The QA observatory telescope booking fee is Rs. 700 per session. Students must "
        "reserve a place with the laboratory coordinator before arrival and bring their "
        "student identity card. The observatory is open for supervised study every Friday.")


@pytest.fixture
def uploaded(tmp_path, monkeypatch):
    for name in ("UPLOAD_DIR", "INDEX_DIR"):
        path = tmp_path / name
        path.mkdir()
        monkeypatch.setattr(config, name, path)
    store = Store()
    monkeypatch.setattr(ingest, "store", store)
    monkeypatch.setattr(main, "store", store)
    client = TestClient(main.app, headers={"X-Admin-Token": config.ADMIN_TOKEN})
    response = client.post("/api/admin/ingest/files", files={"files": ("policy.txt", BODY)})
    assert response.json()["results"][0]["chunks"]
    doc_id = ingest.doc_id_for("policy.txt")
    yield client, store, doc_id
    client.close()


@pytest.mark.parametrize("failure", ["short", "oversized", "extraction", "save", "publish"])
def test_rejected_replacement_preserves_file_index_and_public_source(uploaded, monkeypatch, failure):
    client, store, doc_id = uploaded
    original = (config.UPLOAD_DIR / "policy.txt").read_bytes()
    original_chunks = [dict(c) for c in store.chunks]
    persisted = {p: p.read_bytes() for p in (store.docs_path, store.chunks_path, store.faiss_path)}

    def fail(*args, **kwargs):
        raise OSError("QA simulated failure")

    text = BODY.replace("700", "900")
    if failure == "short":
        text = "withdrawn"
    elif failure == "oversized":
        monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 32)
    elif failure == "extraction":
        monkeypatch.setattr(ingest, "extract", fail)
    elif failure == "save":
        # Simulate a partial persistence failure, not just a failure before writing.
        def partial_save():
            store.docs_path.write_text("partial write")
            fail()
        monkeypatch.setattr(store, "save", partial_save)
    elif failure == "publish":
        monkeypatch.setattr(Path, "replace", fail)

    response = client.post("/api/admin/ingest/files", files={"files": ("policy.txt", text)})
    assert response.status_code == 200
    assert response.json()["results"][0]["skipped"]
    assert (config.UPLOAD_DIR / "policy.txt").read_bytes() == original
    assert store.chunks == original_chunks
    assert {p: p.read_bytes() for p in persisted} == persisted
    assert client.get(f"/api/site/document/{doc_id}").json()["text"] == BODY
    assert not list(config.UPLOAD_DIR.glob(".staging-*"))


def test_successful_replacement_updates_source_chunks_and_file(uploaded):
    client, store, doc_id = uploaded
    new = BODY.replace("700", "900")
    response = client.post("/api/admin/ingest/files", files={"files": ("policy.txt", new)})
    assert response.json()["results"][0]["replaced"] is True
    assert (config.UPLOAD_DIR / "policy.txt").read_text() == new
    assert client.get(f"/api/site/document/{doc_id}").json()["text"] == new
    assert len(store.docs) == 1 and store.index.ntotal == len(store.chunks)
    assert all("700" not in c["text"] for c in store.chunks)


def test_external_file_changes_do_not_change_an_indexed_citation(uploaded):
    client, store, doc_id = uploaded
    (config.UPLOAD_DIR / "policy.txt").write_text("not indexed")
    assert client.get(f"/api/site/document/{doc_id}").json()["text"] == BODY
