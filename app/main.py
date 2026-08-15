import shutil
import time
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, generate, ingest, llm, models
from .store import store

app = FastAPI(title="CampusQuery", version="1.0")
app.mount("/static", StaticFiles(directory=config.WEB_DIR / "static"), name="static")

ALLOWED_SUFFIXES = {".pdf", ".txt", ".md", ".html", ".htm"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class Turn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    history: list[Turn] = []
    debug: bool = False


class UrlRequest(BaseModel):
    urls: list[str]


class TextRequest(BaseModel):
    title: str
    text: str


def require_admin(x_admin_token: str = Header(default="")):
    """The ingest side is a backend service, not part of the public product."""
    if x_admin_token != config.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing admin token")
    return True


@app.on_event("startup")
def startup():
    models.warmup()


# ------------------------------------------------------------------ public site
@app.get("/")
def home():
    return FileResponse(config.WEB_DIR / "index.html")


@app.get("/admin")
def admin_page():
    return FileResponse(config.WEB_DIR / "admin.html")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "index": store.stats(),
        "generation": llm.describe(),
        "provider": llm.provider(),
        "embedder": config.EMBED_MODEL,
        "reranker": config.RERANK_MODEL if config.USE_RERANKER else None,
    }


@app.get("/api/site/notices")
def notices():
    """The demo site renders exactly what is indexed, so the page and the
    assistant can never disagree."""
    items = [
        {
            "title": doc.get("title", ""),
            "date": doc.get("date", ""),
            "kind": doc.get("kind", "page"),
            "source": doc.get("source", ""),
            "origin": doc.get("origin", ""),
        }
        for doc in store.docs.values()
        if doc.get("kind") in ("circular", "notice")
    ]
    items.sort(key=lambda d: d.get("date", ""), reverse=True)
    return {"items": items, "total": len(items), "stats": store.stats()}


@app.post("/api/chat")
def chat(request: ChatRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question is empty")
    if len(question) > 500:
        raise HTTPException(status_code=422, detail="Question is too long")

    result = generate.answer(question, [t.model_dump() for t in request.history])
    payload = {
        "answer": result["answer"],
        "refused": result["refused"],
        "citations": result["citations"],
        "mode": result["mode"],
        "latency_ms": result["latency_ms"],
    }
    if request.debug:
        payload["rewritten"] = result["rewritten"]
        payload["debug"] = result["debug"]
        payload["retrieved"] = [
            {k: chunk[k] for k in ("title", "section", "score", "dense", "bm25", "rrf")}
            | {"preview": chunk["text"][:220]}
            for chunk in result["retrieved"]
        ]
    return payload


# ------------------------------------------------------------------ admin / ingest
@app.get("/api/admin/status")
def admin_status(_=Depends(require_admin)):
    return {
        "stats": store.stats(),
        "documents": sorted(store.docs.values(), key=lambda d: d.get("indexed_at", ""), reverse=True),
    }


@app.post("/api/admin/ingest/files")
async def ingest_files(files: list[UploadFile] = File(...), _=Depends(require_admin)):
    started, results = time.perf_counter(), []
    for upload in files:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            results.append({"title": upload.filename, "chunks": 0,
                            "skipped": f"unsupported file type {suffix or '(none)'}"})
            continue
        target = config.UPLOAD_DIR / Path(upload.filename).name
        with target.open("wb") as fh:
            shutil.copyfileobj(upload.file, fh)
        if target.stat().st_size > MAX_UPLOAD_BYTES:
            target.unlink(missing_ok=True)
            results.append({"title": upload.filename, "chunks": 0, "skipped": "file over 20 MB"})
            continue
        try:
            results.append(ingest.index_file(target, origin="upload"))
        except Exception as exc:
            results.append({"title": upload.filename, "chunks": 0, "skipped": str(exc)})
    return {"results": results, "stats": store.stats(),
            "elapsed_ms": int((time.perf_counter() - started) * 1000)}


@app.post("/api/admin/ingest/urls")
def ingest_urls(request: UrlRequest, _=Depends(require_admin)):
    started, results = time.perf_counter(), []
    for url in request.urls:
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            results.append({"title": url, "chunks": 0, "skipped": "not an http(s) URL"})
            continue
        try:
            results.append(ingest.index_url(url, origin="upload"))
        except Exception as exc:
            results.append({"title": url, "chunks": 0, "skipped": str(exc)})
    return {"results": results, "stats": store.stats(),
            "elapsed_ms": int((time.perf_counter() - started) * 1000)}


@app.post("/api/admin/ingest/text")
def ingest_raw_text(request: TextRequest, _=Depends(require_admin)):
    title = request.title or "Pasted text"
    result = ingest.index_text(
        request.text, title=title, source="Pasted text",
        key=f"pasted:{title}", origin="upload", kind="page",
    )
    return {"results": [result], "stats": store.stats()}


@app.post("/api/admin/reindex-seed")
def reindex_seed(_=Depends(require_admin)):
    results = ingest.reindex_seed()
    return {"results": results, "stats": store.stats()}


@app.delete("/api/admin/document/{doc_id}")
def delete_document(doc_id: str, _=Depends(require_admin)):
    removed = store.delete_document(doc_id)
    store.save()
    if not removed:
        return JSONResponse({"detail": "No such document"}, status_code=404)
    return {"removed_chunks": removed, "stats": store.stats()}
