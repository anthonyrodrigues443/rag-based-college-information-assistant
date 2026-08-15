"""Extraction and indexing. This is the backend/admin side of the demo,
not something a public visitor touches."""
import hashlib
import re
from pathlib import Path

from . import chunking, config, models
from .store import store

FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
STRIP_TAGS = ("script", "style", "nav", "header", "footer", "aside", "form", "noscript")


def doc_id_for(source: str) -> str:
    return hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]


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
    try:
        import pytesseract
        from PIL import Image
        import io
        pix = page.get_pixmap(dpi=200)
        image = Image.open(io.BytesIO(pix.tobytes("png")))
        return pytesseract.image_to_string(image).strip()
    except Exception:
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
        return {"title": title, "chunks": 0, "skipped": "document has too little text"}

    chunks = chunking.chunk_document(text, title)
    if not chunks:
        return {"title": title, "chunks": 0, "skipped": "nothing to index"}

    vectors = models.encode([c["text"] for c in chunks])
    meta = {"title": title, "source": source, "url": url, "kind": kind,
            "date": date, "origin": origin, "words": len(text.split())}
    added = store.add_document(doc_id_for(key or source), meta, chunks, vectors)
    store.save()
    return {"title": title, "chunks": added, "words": meta["words"]}


def index_file(path: Path, *, origin="upload", kind=None):
    text = extract(path)
    meta, body = parse_front_matter(text) if path.suffix.lower() in (".md", ".txt") else ({}, text)
    title = meta.get("title") or path.stem.replace("-", " ").replace("_", " ").title()
    return index_text(
        body,
        title=title,
        source=meta.get("source") or path.name,
        key=path.name,
        origin=origin,
        kind=kind or meta.get("kind", "pdf" if path.suffix.lower() == ".pdf" else "page"),
        url=meta.get("url", ""),
        date=meta.get("date", ""),
    )


def index_url(url: str, *, origin="upload"):
    text, title = fetch_url(url)
    return index_text(text, title=title or url, source=url, key=url,
                      origin=origin, kind="page", url=url)


def reindex_seed():
    """Wipe and rebuild the demo college corpus from data/seed."""
    store.reset()
    results = []
    for path in sorted(config.SEED_DIR.glob("*.md")):
        results.append(index_file(path, origin="seed"))
    return results
