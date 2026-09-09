"""Issue #15: a refresh logged a 404 and left the withdrawn page indexed and citable.

A permanent 404 or 410 means the page was taken down; a timeout or a 5xx means the
server is having a bad day and the content must survive it.
"""
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app import ingest, scheduler
from app.store import store

PAGE = ("<html><body><main><h1>Hostel mess timings</h1><p>The mess serves breakfast "
        "between seven and nine in the morning and dinner between seven and nine in the "
        "evening on every day of the week including Sunday and public holidays.</p>"
        "</main></body></html>")


class Fixture(BaseHTTPRequestHandler):
    status = 200

    def do_GET(self):
        if Fixture.status == 200:
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(Fixture.status)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def log_message(self, *args):
        pass


@pytest.fixture
def served():
    Fixture.status = 200
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/notice"
    httpd.shutdown()
    httpd.server_close()


def test_a_withdrawn_page_is_removed_and_reported(indexed, served):
    ingest.index_url(served, origin="upload")
    doc_id = ingest.doc_id_for(served, "upload")
    assert doc_id in store.docs

    Fixture.status = 404
    result = scheduler.refresh()

    assert doc_id not in store.docs, "a page that answers 404 must not stay citable"
    assert result["urls_withdrawn"] == 1
    assert result["stale_dropped"] >= 1
    assert any("withdrawn at the source" in e for e in result["errors"])


def test_a_gone_page_is_treated_the_same_way(indexed, served):
    ingest.index_url(served, origin="upload")
    doc_id = ingest.doc_id_for(served, "upload")

    Fixture.status = 410
    scheduler.refresh()
    assert doc_id not in store.docs


@pytest.mark.parametrize("status", [500, 503])
def test_a_server_error_leaves_the_document_alone(indexed, served, status):
    ingest.index_url(served, origin="upload")
    doc_id = ingest.doc_id_for(served, "upload")
    chunks = store.docs[doc_id]["n_chunks"]

    Fixture.status = status
    result = scheduler.refresh()

    assert doc_id in store.docs, "a transient failure must not destroy valid content"
    assert store.docs[doc_id]["n_chunks"] == chunks
    assert result["urls_withdrawn"] == 0
    assert result["errors"]

    store.delete_document(doc_id)


def test_a_refresh_leaves_uploaded_files_intact(indexed, served, tmp_path):
    upload = tmp_path / "club-notice.md"
    upload.write_text(
        "The robotics club meets every Thursday at five in the afternoon in the "
        "workshop behind the mechanical engineering building for its weekly build "
        "session, and every student of the institute is welcome to join at any time.\n",
        encoding="utf-8")
    assert ingest.index_file(upload, origin="upload")["chunks"] == 1
    doc_id = ingest.doc_id_for(upload.name, "upload")

    ingest.index_url(served, origin="upload")
    Fixture.status = 404
    scheduler.refresh()

    assert doc_id in store.docs, "only the withdrawn URL should have gone"
    store.delete_document(doc_id)


def test_only_a_status_failure_counts_as_withdrawn():
    import httpx
    request = httpx.Request("GET", "http://example.edu/x")
    gone = httpx.HTTPStatusError("404", request=request, response=httpx.Response(404, request=request))
    server_error = httpx.HTTPStatusError("500", request=request, response=httpx.Response(500, request=request))

    assert ingest.is_withdrawn(gone)
    assert not ingest.is_withdrawn(server_error)
    assert not ingest.is_withdrawn(httpx.ConnectTimeout("timed out"))
    assert not ingest.is_withdrawn(OSError("network is down"))
