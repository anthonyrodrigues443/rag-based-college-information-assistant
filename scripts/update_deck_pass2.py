"""Second pass over the deck: the slides that were not touched the first time.

Slides 3, 4, 9 and 10 still carried claims from before anything was measured, and
some of them contradicted the numbers now on slides 7 and 8.

    ./.venv/bin/python scripts/update_deck_pass2.py <deck.pptx> [<deck.pptx> ...]
"""
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path


def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


EDITS = {
    3: [
        # "240+ documents in scope" contradicted slide 7, which says the corpus is 22
        ("240+", "Dozens", "s3 stat"),
        ("documents in scope", "pages and PDFs to search", "s3 stat label"),
    ],
    4: [
        ("Under 3 second response on free tier hardware",
         "An answer in a few seconds on free tier hardware", "s4 latency requirement"),
    ],
    9: [
        ("Restricting generation to retrieved college content removed the invented fees",
         "Restricting generation to retrieved college content removed the invented fees and "
         "dates a plain LLM produced. The same model with no retrieval scored 0 of 50.",
         "s9 grounding claim"),
        ("BM25 carries codes and names, dense retrieval carries paraphrase.",
         "BM25 carries codes and names, dense retrieval carries paraphrase. Fusing them and "
         "re-ranking lifted Hit@5 from 0.92 to 0.98 and Hit@1 from 0.76 to 0.86.",
         "s9 hybrid claim"),
        ("Crawl, index and chat work end to end",
         "Crawl, index and chat work end to end, answering in about 5 seconds on a local "
         "model with a source link on every answer.", "s9 system claim"),
    ],
    10: [
        ("Layout aware PDF parsing and a stronger OCR pass",
         "Layout aware PDF parsing and a stronger OCR pass, for scans of lower quality than "
         "the two we read today.", "s10 OCR item"),
        ("Priority for the end-term",
         "Priority for the end-term: extraction quality and domain tuned embeddings, because "
         "both target the six answers we still get wrong.", "s10 footnote"),
    ],
}


def patch(deck: Path):
    print(f"\n{deck.parent.name} / {deck.name}")
    work = Path(tempfile.mkdtemp(prefix="pass2_"))
    with zipfile.ZipFile(deck) as zf:
        zf.extractall(work)

    total = 0
    for slide, rules in EDITS.items():
        path = work / f"ppt/slides/slide{slide}.xml"
        xml = path.read_text(encoding="utf-8")
        for starts_with, new_text, label in rules:
            pattern = re.compile(r"<a:t>" + re.escape(esc(starts_with)) + r".*?</a:t>", re.S)
            xml, count = pattern.subn("<a:t>" + esc(new_text) + "</a:t>", xml, count=1)
            print(("  ok   " if count else "  MISS ") + label)
            total += count
        path.write_text(xml, encoding="utf-8")

    deck.unlink()
    with zipfile.ZipFile(deck, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(work.rglob("*")):
            if file.is_file():
                zf.write(file, file.relative_to(work))
    shutil.rmtree(work, ignore_errors=True)
    print(f"  {total} edits applied")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: update_deck_pass2.py <deck.pptx> [...]")
    for target in sys.argv[1:]:
        patch(Path(target))
