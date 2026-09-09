"""Labelled evaluation of the retriever.

Every question below is tagged with the document that actually holds the answer,
so Hit@1, Hit@5 and MRR are measured, not estimated. Off-topic questions are
tagged REFUSE and must fall under the refusal threshold.

    ./.venv/bin/python scripts/eval.py                 # current settings
    ./.venv/bin/python scripts/eval.py --sweep         # compare rerank weights
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, retrieve  # noqa: E402

REFUSE = "REFUSE"

# question -> substring of the title of the document that answers it
QUESTIONS = [
    ("What is the last date to pay the semester fee?", ["Extension of last date"]),
    ("I missed the deadline for my tuition money, what happens now", ["Extension of last date"]),
    ("How much is the late fee if I pay after the last date?", ["Extension of last date"]),
    ("Where do I pay my fees, can I pay cash at the counter?", ["Extension of last date"]),
    ("When does the KT exam form window close?", ["KT examination"]),
    ("What is the late fee for submitting the KT form in September?", ["KT examination"]),
    ("How many backlog subjects can I register in one attempt?", ["KT examination"]),
    ("How much attendance do I need to sit for the exam?", ["attendance shortfall", "Student handbook"]),
    ("am I allowed to sit for exams if I bunked a lot of lectures", ["attendance shortfall", "Student handbook"]),
    ("What happens if my attendance is below 65 percent?", ["attendance shortfall", "Student handbook"]),
    ("my answer sheet was marked badly, can it be checked again", ["Revaluation"]),
    ("What does revaluation cost per paper?", ["Revaluation"]),
    ("Can I get a photocopy of my answer book?", ["Revaluation"]),
    ("What documents do I need for hostel allotment?", ["Hostel allotment"]),
    ("I stay far away from campus, can I get a room", ["Hostel rules", "Hostel allotment"]),
    ("How much does a two seater hostel room cost per year?", ["Hostel rules", "Hostel allotment"]),
    ("When is the last date for the scholarship application?", ["Government scholarship"]),
    ("What is the income limit for the EBC concession?", ["Government scholarship"]),
    ("What is the new subject code for NLP?", ["Third-year syllabus"]),
    ("How many credits does Semester V have now?", ["Third-year syllabus"]),
    ("When do the theory exams start?", ["Revised academic calendar", "Academic calendar", "Examination timetable"]),
    ("When do I get my hall ticket?", ["Examination timetable"]),
    ("Can I carry a calculator into the exam hall?", ["Examination timetable"]),
    ("What is the BE tuition fee for one year?", ["Institute fee structure"]),
    ("How much does a transcript cost and how long does it take?", ["Bonafide certificate"]),
    ("How many books can I borrow from the library?", ["Library"]),
    ("What is the fine for returning a library book late?", ["Library"]),
    ("Can I sit for placements with three backlogs?", ["Training and placement"]),
    ("how do I complain if my internal marks look wrong", ["Student handbook"]),
    ("What marks do I need in HSC to apply?", ["Admissions 2026"]),
    ("How many seats does the AIML department have?", ["Department of Artificial Intelligence"]),
    ("What time does the accounts section open?", ["Contact"]),
    # off topic, must refuse
    ("Who won the cricket world cup in 2011?", REFUSE),
    ("What is the capital of France?", REFUSE),
    ("Where can I get the best pizza near campus?", REFUSE),
    ("Can you write my assignment for me?", REFUSE),
    ("What is the share price of Infosys today?", REFUSE),
    ("How do I get into the college wifi router admin panel?", REFUSE),
    ("Will it rain tomorrow in Mumbai?", REFUSE),
    ("Which is better, this college or the one in Pune?", REFUSE),
]


def hits(results, wanted):
    return [any(w.lower() in r["title"].lower() for w in wanted) for r in results]


def run(label=""):
    answerable = [(q, w) for q, w in QUESTIONS if w != REFUSE]
    offtopic = [q for q, w in QUESTIONS if w == REFUSE]

    hit1 = hit5 = 0
    reciprocal = 0.0
    false_refusals = []
    misses = []

    for question, wanted in answerable:
        results, _ = retrieve.search(question, top_n=5)
        flags = hits(results, wanted)
        if retrieve.unsupported(question, results):
            false_refusals.append(question)
        if flags and flags[0]:
            hit1 += 1
        if any(flags):
            hit5 += 1
            reciprocal += 1 / (flags.index(True) + 1)
        else:
            misses.append((question, results[0]["title"] if results else "nothing"))

    refused = 0
    leaked = []
    for question in offtopic:
        results, _ = retrieve.search(question, top_n=5)
        if retrieve.unsupported(question, results):
            refused += 1
        else:
            leaked.append((question, results[0]["title"], results[0]["score"]))

    n, m = len(answerable), len(offtopic)
    print(f"\n{label}")
    print(f"  questions          {n} answerable, {m} off topic")
    print(f"  Hit@1              {hit1}/{n}  {hit1/n:.2f}")
    print(f"  Hit@5              {hit5}/{n}  {hit5/n:.2f}")
    print(f"  MRR                {reciprocal/n:.2f}")
    print(f"  correctly refused  {refused}/{m}  {refused/m:.2f}")
    print(f"  false refusals     {len(false_refusals)}/{n}")
    for question, got in misses:
        print(f"    MISS   {question[:52]:<54} -> {got[:44]}")
    for question, got, score in leaked:
        print(f"    LEAK   {question[:52]:<54} -> {got[:34]} @ {score}")
    return hit1 / n, hit5 / n, reciprocal / n, refused / m


if __name__ == "__main__":
    if "--sweep" in sys.argv:
        for weight in (1.0, 0.8, 0.6, 0.4, 0.0):
            config.RERANK_WEIGHT = weight
            run(f"RERANK_WEIGHT = {weight}"
                f"{'   (pure cross-encoder)' if weight == 1.0 else ''}"
                f"{'   (no re-ranker, fusion only)' if weight == 0.0 else ''}")
    else:
        run(f"RERANK_WEIGHT = {config.RERANK_WEIGHT}, threshold = {config.REFUSAL_THRESHOLD}")
