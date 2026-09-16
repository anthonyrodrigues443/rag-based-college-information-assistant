"""Extraction and indexing. This is the backend/admin side of the demo,
not something a public visitor touches."""
import datetime
import re
from pathlib import Path

from . import chunking, config, models
from .store import doc_id_for, store

FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
_ocr_failure = None            # why the last OCR attempt failed, so it is not swallowed
STRIP_TAGS = ("script", "style", "nav", "header", "footer", "aside", "form", "noscript")

# Metadata arrives from files staff did not write, so every value that reaches a
# page is constrained here rather than trusted at render time.
KINDS = ("page", "circular", "notice", "handbook", "pdf")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def clean_kind(value, default: str = "page") -> str:
    kind = str(value or "").strip().lower()
    return kind if kind in KINDS else default


def clean_date(value) -> str:
    """Keep only a real ISO calendar date. 2026-13-01 and free text become empty."""
    text = str(value or "").strip()
    if not ISO_DATE_RE.match(text):
        return ""
    try:
        datetime.date.fromisoformat(text)
    except ValueError:
        return ""
    return text


def clean_url(value) -> str:
    url = str(value or "").strip()
    return url if url.startswith(("http://", "https://")) else ""


def parse_front_matter(text: str):
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text
    meta = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta, text[match.end():]


def text_from_html(html: str) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(list(STRIP_TAGS)):
        tag.decompose()
    for table in soup.find_all("table"):           # keep table rows readable
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
            if cells:
                rows.append(" | ".join(cells))
        table.replace_with("\n".join(rows))
    main = soup.find("main") or soup.find("article") or soup.body or soup
    return main.get_text("\n", strip=True)


def text_from_pdf(path: Path) -> str:
    import fitz
    parts = []
    with fitz.open(path) as pdf:
        for page in pdf:
            text = page.get_text("text").strip()
            if len(text) < 40:                     # likely a scan, try OCR
                text = ocr_page(page) or text
            if text:
                parts.append(text)
    return "\n\n".join(parts)


def ocr_page(page) -> str:
    """OCR needs the tesseract binary, which pip does not install. If it is missing
    the reason is recorded rather than swallowed, so a scanned document is not
    dropped silently."""
    global _ocr_failure
    try:
        import pytesseract
        from PIL import Image
        import io
        pix = page.get_pixmap(dpi=200)
        image = Image.open(io.BytesIO(pix.tobytes("png")))
        text = pytesseract.image_to_string(image).strip()
        _ocr_failure = None
        return text
    except Exception as exc:
        _ocr_failure = str(exc)
        return ""


def extract(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return text_from_pdf(path)
    if suffix in (".html", ".htm"):
        return text_from_html(path.read_text(encoding="utf-8", errors="ignore"))
    return path.read_text(encoding="utf-8", errors="ignore")


def fetch_url(url: str):
    import httpx
    response = httpx.get(url, timeout=20, follow_redirects=True,
                         headers={"User-Agent": "CampusQuery/1.0 (demo indexer)"})
    response.raise_for_status()
    body = response.text
    title = ""
    match = re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I)
    if match:
        title = re.sub(r"\s+", " ", match.group(1)).strip()
    return text_from_html(body), title


def index_text(text: str, *, title: str, source: str, key: str = None, origin="upload",
               kind="page", url="", date=""):
    """Chunk, embed and add to the index. `key` identifies the document (file name,
    URL); `source` is the human label shown in a citation and is not unique."""
    text = chunking.clean_text(text)
    if len(text.split()) < config.MIN_CHUNK_WORDS:
        reason = "document has too little text"
        if _ocr_failure:
            reason += (f". This looks like a scan and OCR is unavailable: {_ocr_failure}. "
                       "Install the tesseract binary, for example: brew install tesseract")
        return {"title": title, "chunks": 0, "skipped": reason}

    chunks = chunking.chunk_document(text, title)
    if not chunks:
        return {"title": title, "chunks": 0, "skipped": "nothing to index"}

    vectors = models.encode([c["text"] for c in chunks])
    meta = {"title": title, "source": source, "key": key or source, "url": clean_url(url),
            "kind": clean_kind(kind), "date": clean_date(date), "origin": origin,
            "words": len(text.split()), "text": text}
    doc_id = doc_id_for(key or source, origin)
    replaced = doc_id in store.docs
    added = store.add_document(doc_id, meta, chunks, vectors)
    store.save()
    result = {"title": title, "chunks": added, "words": meta["words"]}
    if replaced:
        # Re-indexing the same key from the same origin is a deliberate update; say so
        # rather than letting a document quietly disappear from the index.
        result["replaced"] = True
    return result


READABLE_SUFFIXES = (".pdf", ".txt", ".md", ".html", ".htm")


def source_path(doc: dict):
    """Where a document's original file lives, or None. Only a bare file name inside the
    seed or upload directory resolves, so a crafted key cannot reach the rest of the disk."""
    key = doc.get("key", "")
    directory = {"seed": config.SEED_DIR, "upload": config.UPLOAD_DIR}.get(doc.get("origin"))
    if not directory or not key or Path(key).name != key:
        return None
    path = (directory / key).resolve()
    if directory.resolve() not in path.parents or not path.is_file():
        return None
    return path if path.suffix.lower() in READABLE_SUFFIXES else None


def rejoin(chunks) -> str:
    """Reassemble indexed chunks into readable text, dropping the heading prefix each
    one carries and the window overlap it shares with the one before."""
    out = []
    for chunk in chunks:
        words = chunk["text"].split("\n", 1)[-1].split()
        if out:
            previous = out[-1].split()
            overlap = min(len(previous), len(words), config.CHUNK_OVERLAP_WORDS + 5)
            while overlap and previous[-overlap:] != words[:overlap]:
                overlap -= 1
            words = words[overlap:]
        if words:
            out.append(" ".join(words))
    return "\n\n".join(out)


def document_text(doc: dict) -> str:
    """The complete text behind a citation, so a student can read the qualifications and
    exceptions around the sentence that was quoted."""
    # Read the accepted version, not a mutable file that may have changed since it
    # was indexed. Legacy indexes can be reconstructed without trusting the file.
    if "text" in doc:
        return doc["text"]
    return rejoin([c for c in store.chunks if c["doc_id"] == doc.get("doc_id")])


def sidecar(path: Path) -> dict:
    """A scanned PDF carries no front matter, so `<name>.meta.json` supplies its title."""
    companion = path.with_suffix(".meta.json")
    if companion.exists():
        import json
        return json.loads(companion.read_text(encoding="utf-8"))
    return {}


def index_file(path: Path, *, origin="upload", kind=None):
    text = extract(path)
    meta, body = parse_front_matter(text) if path.suffix.lower() in (".md", ".txt") else ({}, text)
    meta = {**sidecar(path), **meta}
    title = meta.get("title") or path.stem.replace("-", " ").replace("_", " ").title()
    default_kind = "pdf" if path.suffix.lower() == ".pdf" else "page"
    return index_text(
        body,
        title=title,
        source=meta.get("source") or path.name,
        key=path.name,
        origin=origin,
        kind=clean_kind(kind or meta.get("kind"), default_kind),
        url=meta.get("url", ""),
        date=meta.get("date", ""),
    )


GONE_STATUSES = (404, 410)


def is_withdrawn(exc: Exception) -> bool:
    """True only for a definite "this page no longer exists" answer. A timeout, a DNS
    failure or a 5xx is the server having a bad day and must not destroy content."""
    import httpx
    return (isinstance(exc, httpx.HTTPStatusError)
            and exc.response.status_code in GONE_STATUSES)


def index_url(url: str, *, origin="upload"):
    text, title = fetch_url(url)
    return index_text(text, title=title or url, source=url, key=url,
                      origin=origin, kind="page", url=url)


def reindex_seed():
    """Wipe and rebuild the demo college corpus from data/seed."""
    store.reset()
    results = []
    paths = sorted(list(config.SEED_DIR.glob("*.md")) + list(config.SEED_DIR.glob("*.pdf")))
    for path in paths:
        results.append(index_file(path, origin="seed"))
    return results
