"""Rewrites the mid-term deck's claims to match what the system actually does.

Reads data/eval/results.json, edits the slide XML in place (so the author's own
edits and images survive), swaps the retrieval chart image, and repacks.

    ./.venv/bin/python scripts/update_deck.py "/path/to/PPT1.pptx"
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "data" / "eval" / "results.json"
CHART = ROOT / "data" / "eval" / "retrieval_chart.png"


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def replace_run(xml: str, starts_with: str, new_text: str, label: str):
    """Replace the body of the <a:t> run that begins with `starts_with`."""
    pattern = re.compile(r"<a:t>" + re.escape(esc(starts_with)) + r".*?</a:t>", re.S)
    replaced, count = pattern.subn("<a:t>" + esc(new_text) + "</a:t>", xml, count=1)
    print(("  ok   " if count else "  MISS ") + label)
    return replaced, count


def main(deck: Path):
    data = json.loads(RESULTS.read_text())
    abl, ref = data["ablation"], data["refusals"]
    e2e = data.get("end_to_end", {})
    cold = data.get("baseline_no_retrieval", {})
    corpus = data["corpus"]
    n_ans = data["questions"]["answerable"]
    n_all = data["questions"]["total"]
    n_off = data["questions"]["offtopic"]

    hit5 = abl["hybrid_rerank"]["hit5"]
    mrr = abl["hybrid_rerank"]["mrr"]
    correct = e2e.get("correct", 0)
    grounded = e2e.get("grounded", 0)
    answered = e2e.get("answered", n_ans)
    median = e2e.get("median_latency_ms", 0) / 1000
    cold_correct = cold.get("correct", 0)
    bm25_hit1 = abl["bm25"]["hit1"]

    backup = deck.with_name(deck.stem + "_before_measured_numbers.pptx")
    if not backup.exists():
        shutil.copy2(deck, backup)
        print(f"backup: {backup.name}")

    work = Path(tempfile.mkdtemp(prefix="deckedit_"))
    with zipfile.ZipFile(deck) as zf:
        zf.extractall(work)

    total = 0

    # ---------------------------------------------------------------- slide 7
    path = work / "ppt/slides/slide7.xml"
    xml = path.read_text(encoding="utf-8")
    xml, c = replace_run(xml, "242 documents",
        f"{corpus['documents']} documents, {corpus['chunks']} chunks. HTML pages, scanned "
        f"notices, syllabus and handbook. Boilerplate stripped, tables kept as markdown, "
        f"Tesseract OCR for the scanned notices.", "s7 dataset counts"); total += c
    xml, c = replace_run(xml, "cross encoder keeps top 5",
        "cross encoder blended with fusion rank, top 5", "s7 re-rank step"); total += c
    xml, c = replace_run(xml, "If the top re-ranked score",
        'If the best raw cross encoder score falls below the threshold, CampusQuery replies '
        '"not available in the college content" instead of guessing.', "s7 guardrail"); total += c
    path.write_text(xml, encoding="utf-8")

    # ---------------------------------------------------------------- slide 8
    path = work / "ppt/slides/slide8.xml"
    xml = path.read_text(encoding="utf-8")
    xml, c = replace_run(xml, "What works today, measured on",
        f"What works today, measured on {n_all} labelled questions", "s8 title"); total += c
    xml, c = replace_run(xml, "0.79", f"{mrr:.2f}", "s8 MRR value"); total += c
    xml, c = replace_run(xml, "MRR after re-ranking", "MRR after re-ranking", "s8 MRR label"); total += c
    xml, c = replace_run(xml, "0.91", f"{grounded}/{answered}", "s8 grounded value"); total += c
    xml, c = replace_run(xml, "faithfulness (RAGAS)", "answers fully grounded", "s8 grounded label"); total += c
    xml, c = replace_run(xml, "2.4 s", f"{median:.1f} s", "s8 latency value"); total += c
    xml, c = replace_run(xml, "median latency", "median latency, local model", "s8 latency label"); total += c
    xml, c = replace_run(xml, "53 / 60", f"{correct} / {n_ans}", "s8 correct value"); total += c
    xml, c = replace_run(xml, "Same 60 questions on the baselines",
        f"Same questions with no retrieval, same model: {cold_correct} of {n_ans} correct. "
        f"BM25 alone puts the right document first on {bm25_hit1:.0%} of them. "
        f"{ref['offtopic_refused']} of {n_off} off topic questions were refused.",
        "s8 baseline footnote"); total += c
    path.write_text(xml, encoding="utf-8")

    # ---------------------------------------------------------------- slide 11
    path = work / "ppt/slides/slide11.xml"
    xml = path.read_text(encoding="utf-8")
    xml, c = replace_run(xml, "College information is correct but unfindable",
        "College information is correct but unfindable, spread over dozens of pages and PDFs. "
        "Students need an answer, not a search result.", "s11 problem"); total += c
    xml, c = replace_run(xml, "Hit@5 of",
        f"Hit@5 of {hit5:.2f} and MRR {mrr:.2f} after re-ranking, {correct} of {n_ans} questions "
        f"answered correctly, {grounded} of {answered} answers fully grounded, median {median:.1f} s "
        f"on a local model, running end to end through a chat widget on the college site.",
        "s11 current results"); total += c
    path.write_text(xml, encoding="utf-8")

    # ---------------------------------------------------------------- slide 12
    path = work / "ppt/slides/slide12.xml"
    xml = path.read_text(encoding="utf-8")
    xml, c = replace_run(xml, "Tools: sentence-transformers",
        "Tools: sentence-transformers, FAISS, rank_bm25, PyMuPDF, BeautifulSoup, Tesseract OCR, "
        "FastAPI, Ollama and Groq for generation. Front end in HTML, CSS and JavaScript.",
        "s12 tools"); total += c
    xml, c = replace_run(xml, "Corpus: official",
        f"Corpus: {corpus['documents']} documents of college notices, circulars, syllabus and "
        f"handbook content, including two scanned notices read by OCR, indexed as "
        f"{corpus['chunks']} chunks.", "s12 corpus"); total += c
    path.write_text(xml, encoding="utf-8")

    # ---------------------------------------------------------------- chart image
    if CHART.exists():
        shutil.copy2(CHART, work / "ppt/media/image1.png")
        print("  ok   chart image swapped")
        total += 1

    out = deck
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(work.rglob("*")):
            if file.is_file():
                zf.write(file, file.relative_to(work))
    shutil.rmtree(work, ignore_errors=True)
    print(f"\n{total} edits applied -> {out}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: update_deck.py <deck.pptx>")
    main(Path(sys.argv[1]))
