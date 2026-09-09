"""Full result analysis: retrieval ablation, baselines, latency, and LLM-judged
correctness and faithfulness. This produces every number the mid-term deck claims.

    ./.venv/bin/python scripts/eval_full.py            # everything (slow, uses the LLM)
    ./.venv/bin/python scripts/eval_full.py --retrieval-only

Writes data/eval/report.md and data/eval/results.json.
"""
import json
import re
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, generate, llm, models, retrieve  # noqa: E402
from app.store import store  # noqa: E402
from eval import QUESTIONS as BASE_QUESTIONS, REFUSE  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "eval"
OUT.mkdir(parents=True, exist_ok=True)

EXTRA = [
    ("Is there a break for the festival in October?", ["Revised academic calendar"]),
    ("When does teaching start for the odd semester?", ["Revised academic calendar", "Academic calendar"]),
    ("What is the refundable deposit for a hostel seat?", ["Hostel allotment", "Hostel rules"]),
    ("How much is the mess bill every month?", ["Hostel rules"]),
    ("Can I keep a heater in my hostel room?", ["Hostel rules"]),
    ("What happens if I miss my document verification slot?", ["Hostel allotment"]),
    ("What is the exam fee for a KT laboratory subject?", ["KT examination"]),
    ("What is the caution deposit for the BE programme?", ["Institute fee structure"]),
    ("How much does one year of ME cost?", ["Institute fee structure"]),
    ("When will I get my revaluation result?", ["Revaluation"]),
    ("Do I get my money back if my marks change after revaluation?", ["Revaluation"]),
    ("What is the punishment for using unfair means in an exam?", ["Examination timetable"]),
    ("What do I need to clear to get into third year?", ["Student handbook"]),
    ("How do I get a duplicate identity card?", ["Bonafide certificate"]),
    ("When is the library open on Saturday?", ["Library"]),
    ("What was the highest package last year?", ["Training and placement"]),
    ("Which entrance exam do I need for the ME programme?", ["Admissions 2026"]),
    ("Is the office open on the second Saturday of the month?", ["Contact"]),
    ("Can you tell me a joke?", REFUSE),
    ("What is the population of India?", REFUSE),
    ("Who is the chief minister of Maharashtra?", REFUSE),
    ("What is the syllabus of the IIT Bombay machine learning course?", REFUSE),
]

QUESTIONS = BASE_QUESTIONS + EXTRA
ANSWERABLE = [(q, w) for q, w in QUESTIONS if w != REFUSE]
OFFTOPIC = [q for q, w in QUESTIONS if w == REFUSE]

JUDGE_PROMPT = """You are marking a college assistant's answer.

REFERENCE (the official college text that holds the correct answer):
{reference}

QUESTION: {question}

ANSWER GIVEN: {answer}

Reply with only a JSON object, no other text:
{{"correct": true or false, "grounded": true or false, "why": "under 12 words"}}

correct  = the answer states what the REFERENCE says, with the right numbers and dates.
grounded = every fact in the answer appears in the REFERENCE. An answer that invents a
           number, date or rule not in the REFERENCE is not grounded."""


def gold_text(wanted, limit=2400):
    parts = [c["text"] for c in store.chunks
             if any(w.lower() in c["title"].lower() for w in wanted)]
    return "\n\n".join(parts)[:limit]


def hits(results, wanted):
    return [any(w.lower() in r["title"].lower() for w in wanted) for r in results]


def metrics(flag_lists):
    n = len(flag_lists)
    hit1 = sum(1 for f in flag_lists if f and f[0])
    hit5 = sum(1 for f in flag_lists if any(f))
    mrr = sum(1 / (f.index(True) + 1) for f in flag_lists if any(f))
    return {"hit1": hit1 / n, "hit5": hit5 / n, "mrr": mrr / n, "n": n}


# ------------------------------------------------------------------ retrieval ablation
def ablation():
    modes = {m: [] for m in ("bm25", "dense", "hybrid", "hybrid_rerank", "pipeline")}
    for question, wanted in ANSWERABLE:
        vector = models.encode([question])[0]
        dense = store.dense_search(vector, config.TOP_K_DENSE)
        lexical = store.bm25_search(question, config.TOP_K_BM25)
        fused = retrieve.reciprocal_rank_fusion(dense, lexical)

        modes["dense"].append(hits([store.chunks[i] for i, _ in dense[:5]], wanted))
        modes["bm25"].append(hits([store.chunks[i] for i, _ in lexical[:5]], wanted))
        modes["hybrid"].append(hits([store.chunks[i] for i, _ in fused[:5]], wanted))

        pool = [store.chunks[i] | {"rrf": s} for i, s in fused[:40]]
        raw = models.rerank_scores(question, [c["text"] for c in pool])
        best = max(c["rrf"] for c in pool) or 1.0
        blended = sorted(
            zip(pool, raw),
            key=lambda p: config.RERANK_WEIGHT * retrieve.sigmoid(p[1])
            + (1 - config.RERANK_WEIGHT) * (p[0]["rrf"] / best),
            reverse=True,
        )
        modes["hybrid_rerank"].append(hits([c for c, _ in blended[:5]], wanted))

        # The four rows above each isolate one retriever choice on the raw question.
        # This one is the shipped pipeline, which also normalises the question and
        # orders on the programme it asks about.
        shipped, _ = retrieve.search(question, top_n=5)
        modes["pipeline"].append(hits(shipped, wanted))
    return {name: metrics(flags) for name, flags in modes.items()}


# ------------------------------------------------------------------ refusals
def refusals():
    correct, leaked = 0, []
    for question in OFFTOPIC:
        results, _ = retrieve.search(question)
        if retrieve.unsupported(question, results):
            correct += 1
        else:
            leaked.append(question)
    false_refusals = []
    for question, _ in ANSWERABLE:
        results, _ = retrieve.search(question)
        if retrieve.unsupported(question, results):
            false_refusals.append(question)
    return {"offtopic_total": len(OFFTOPIC), "offtopic_refused": correct,
            "leaked": leaked, "false_refusals": false_refusals,
            "answerable_total": len(ANSWERABLE)}


# ------------------------------------------------------------------ judging
def judge(question, reference, answer):
    try:
        raw = llm.complete(
            [{"role": "user", "content": JUDGE_PROMPT.format(
                reference=reference, question=question, answer=answer)}],
            temperature=0, max_tokens=120)
        match = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(match.group()) if match else {}
        return bool(data.get("correct")), bool(data.get("grounded")), data.get("why", "")
    except Exception as exc:
        return False, False, f"judge failed: {exc}"


def end_to_end():
    """The real product path, plus an LLM-with-no-retrieval baseline on the same questions."""
    rag, cold, latencies = [], [], []
    retrieval_ms, generation_ms = [], []
    for index, (question, wanted) in enumerate(ANSWERABLE, 1):
        reference = gold_text(wanted)

        started = time.perf_counter()
        result = generate.answer(question)
        latencies.append((time.perf_counter() - started) * 1000)
        retrieval_ms.append(result["retrieval_ms"])
        generation_ms.append(result["generation_ms"])
        correct, grounded, why = (False, True, "refused") if result["refused"] \
            else judge(question, reference, result["answer"])
        rag.append({"question": question, "answer": result["answer"], "refused": result["refused"],
                    "correct": correct, "grounded": grounded, "why": why,
                    "mode": result["mode"], "degraded": result["degraded"],
                    "retrieval_ms": result["retrieval_ms"], "generation_ms": result["generation_ms"],
                    "citations": len(result["citations"]), "latency_ms": latencies[-1]})

        try:
            bare = llm.complete([{"role": "user", "content":
                                  f"Answer in 2 to 4 sentences: {question}"}], max_tokens=250)
            c2, g2, w2 = judge(question, reference, bare)
        except Exception as exc:
            bare, c2, g2, w2 = f"(no generator: {exc})", False, False, "no generator"
        cold.append({"question": question, "answer": bare, "correct": c2, "grounded": g2, "why": w2})

        print(f"  {index:>2}/{len(ANSWERABLE)}  rag={'ok ' if correct else 'BAD'} "
              f"cold={'ok ' if c2 else 'BAD'}  {question[:46]}", flush=True)

    return rag, cold, {"total": latencies, "retrieval": retrieval_ms, "generation": generation_ms}


def main():
    retrieval_only = "--retrieval-only" in sys.argv
    print(f"{len(QUESTIONS)} labelled questions: {len(ANSWERABLE)} answerable, {len(OFFTOPIC)} off topic\n")

    print("retrieval ablation...")
    abl = ablation()
    ref = refusals()

    report = {"generator": llm.describe(), "corpus": store.stats(),
              "questions": {"total": len(QUESTIONS), "answerable": len(ANSWERABLE),
                            "offtopic": len(OFFTOPIC)},
              "ablation": abl, "refusals": ref}

    if not retrieval_only:
        print("\nend to end answers and judging (this is the slow part)...")
        rag, cold, timings = end_to_end()
        answered = [r for r in rag if not r["refused"]]
        latencies = timings["total"]
        report["end_to_end"] = {
            "correct": sum(1 for r in rag if r["correct"]),
            "grounded": sum(1 for r in answered if r["grounded"]),
            "answered": len(answered),
            "refused": sum(1 for r in rag if r["refused"]),
            "fell_back": sum(1 for r in rag if r["degraded"]),
            "median_latency_ms": statistics.median(latencies),
            "p90_latency_ms": sorted(latencies)[int(len(latencies) * 0.9) - 1],
            "median_retrieval_ms": statistics.median(timings["retrieval"]),
            "median_generation_ms": statistics.median(timings["generation"]),
            "p90_generation_ms": sorted(timings["generation"])[int(len(timings["generation"]) * 0.9) - 1],
        }
        report["baseline_no_retrieval"] = {
            "correct": sum(1 for r in cold if r["correct"]),
            "grounded": sum(1 for r in cold if r["grounded"]),
        }
        report["detail"] = {"rag": rag, "no_retrieval": cold}

    (OUT / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report)
    print(f"\nwrote {OUT/'report.md'}")


def write_markdown(r):
    a, ref = r["ablation"], r["refusals"]
    n = r["questions"]["answerable"]
    lines = [
        "# CampusQuery result analysis", "",
        f"Corpus: {r['corpus']['documents']} documents, {r['corpus']['chunks']} chunks. "
        f"Generator: {r['generator']}.", "",
        f"Question set: {r['questions']['total']} labelled questions, "
        f"{n} answerable (each tagged with the document that holds the answer) and "
        f"{r['questions']['offtopic']} off topic that must be refused.", "",
        "## Retrieval, same questions through five configurations", "",
        "| Configuration | Hit@1 | Hit@5 | MRR |", "|---|---|---|---|",
    ]
    labels = {"bm25": "BM25 only", "dense": "Dense only (MiniLM)",
              "hybrid": "Hybrid, RRF fused", "hybrid_rerank": "Hybrid + cross-encoder re-rank",
              "pipeline": "Shipped pipeline (+ question normalisation, entity ordering)"}
    for key in ("bm25", "dense", "hybrid", "hybrid_rerank", "pipeline"):
        m = a[key]
        lines.append(f"| {labels[key]} | {m['hit1']:.2f} | {m['hit5']:.2f} | {m['mrr']:.2f} |")

    lines += ["", "## Refusals", "",
              f"- Off topic questions correctly refused: "
              f"{ref['offtopic_refused']}/{ref['offtopic_total']}",
              f"- Answerable questions wrongly refused: {len(ref['false_refusals'])}/{n}"]
    for q in ref["false_refusals"]:
        lines.append(f"  - {q}")
    for q in ref["leaked"]:
        lines.append(f"  - LEAKED (should have refused): {q}")

    if "end_to_end" in r:
        e, b = r["end_to_end"], r["baseline_no_retrieval"]
        lines += ["", "## Answers, judged", "",
                  "Each answer is marked by a second LLM pass against the official college text: "
                  "correct means it states what the source says with the right numbers and dates, "
                  "grounded means every fact in it appears in that source.", "",
                  "| System | Correct | Grounded |", "|---|---|---|",
                  f"| CampusQuery (retrieval + generation) | {e['correct']}/{n} | "
                  f"{e['grounded']}/{e['answered']} |",
                  f"| Same model, no retrieval | {b['correct']}/{n} | {b['grounded']}/{n} |",
                  "", "## Latency", "",
                  f"- Median end to end: {e['median_latency_ms']:.0f} ms",
                  f"- 90th percentile end to end: {e['p90_latency_ms']:.0f} ms",
                  f"- Median retrieval: {e['median_retrieval_ms']:.0f} ms",
                  f"- Median generation: {e['median_generation_ms']:.0f} ms",
                  f"- 90th percentile generation: {e['p90_generation_ms']:.0f} ms",
                  f"- Refused without calling the generator: {e['refused']}",
                  f"- Fell back to the extractive answer: {e['fell_back']}"]
    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
