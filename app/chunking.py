import re
import unicodedata

from . import config

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)          # de-hyphenate PDF line breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sections(text: str):
    """Split markdown-ish text into (heading, body) sections."""
    sections, heading, buffer = [], "", []
    for line in text.split("\n"):
        match = HEADING_RE.match(line.strip())
        if match:
            if buffer:
                sections.append((heading, "\n".join(buffer).strip()))
                buffer = []
            heading = match.group(2).strip()
        else:
            buffer.append(line)
    if buffer:
        sections.append((heading, "\n".join(buffer).strip()))
    return [(h, b) for h, b in sections if b]


def window(words, size, overlap):
    step = max(1, size - overlap)
    for start in range(0, len(words), step):
        piece = words[start:start + size]
        if piece:
            yield piece
        if start + size >= len(words):
            break


def chunk_document(text: str, title: str):
    """Return [{section, text}] with the heading kept as a prefix on every chunk."""
    text = clean_text(text)
    sections = split_sections(text) or [("", text)]
    chunks = []
    for heading, body in sections:
        words = body.split()
        if not words:
            continue
        for piece in window(words, config.CHUNK_WORDS, config.CHUNK_OVERLAP_WORDS):
            if len(piece) < config.MIN_CHUNK_WORDS and chunks:
                continue
            label = " > ".join(x for x in (title, heading) if x)
            chunks.append({
                "section": heading,
                "text": f"{label}\n{' '.join(piece)}" if label else " ".join(piece),
            })
    return chunks
