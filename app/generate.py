"""Grounded answer generation: context-only prompt, citations, explicit refusal."""
import re
import time

from . import config, llm, query, retrieve

SYSTEM_PROMPT = """You are CampusQuery, the assistant for this college's website.

Rules, in order of priority:
1. Answer ONLY from the CONTEXT below. Never use anything you know from outside it.
2. Cite the source number in square brackets after each fact, like [1] or [2].
3. Keep the answer to 2-4 sentences. No greetings, no filler, no restating the question.
4. If the CONTEXT does not contain the answer, reply with exactly this and nothing else:
   Not available in the college content.
5. Amounts, dates and deadlines must be copied exactly as written in the CONTEXT."""

REWRITE_PROMPT = """Rewrite the user's latest question as one standalone question that keeps
the meaning and fills in anything they referred to indirectly. Reply with the question only,
no explanation."""

FOLLOW_UP_CUES = ("and ", "what about", "how about", "for the", "then ", "same for", "also ")


def rewrite_question(question: str, history) -> str:
    """Fold conversation history into a standalone question."""
    if not history:
        return question
    lowered = question.lower().strip()
    anaphoric = len(question.split()) <= 8 or lowered.startswith(FOLLOW_UP_CUES)
    if not anaphoric:
        return question

    turns = [{"role": "system", "content": REWRITE_PROMPT}]
    turns += [{"role": t["role"], "content": t["content"]} for t in history[-config.HISTORY_TURNS:]]
    turns.append({"role": "user", "content": question})
    try:
        # The rewrite is part of the same wait the student is sitting through.
        rewritten = llm.complete(turns, temperature=0, max_tokens=80,
                                 timeout=config.GEN_TIMEOUT)
        return rewritten.strip().strip('"') or question
    except llm.NoGenerator:
        previous = [t["content"] for t in history if t.get("role") == "user"]
        return f"{previous[-1]} {question}" if previous else question
    except Exception:
        return question


def build_context(results):
    blocks = []
    for number, chunk in enumerate(results, start=1):
        label = chunk["title"]
        if chunk.get("date"):
            label += f" ({chunk['date']})"
        blocks.append(f"[{number}] {label}\n{chunk['text']}")
    return "\n\n".join(blocks)


CITE_RE = re.compile(r"\[([\d\s,]+)\]")


def citations_for(answer: str, results):
    # Models write both [1][2] and [1, 2], so read every number inside a bracket.
    used = {
        int(part)
        for group in CITE_RE.findall(answer)
        for part in group.replace(" ", "").split(",")
        if part.isdigit()
    }
    cited = []
    for number, chunk in enumerate(results, start=1):
        if number in used or not used:
            body = chunk["text"].split("\n", 1)[-1]
            cited.append({
                "n": number,
                "doc_id": chunk.get("doc_id", ""),
                "title": chunk["title"],
                "kind": chunk.get("kind", "page"),
                "date": chunk.get("date", ""),
                "url": chunk.get("url", ""),
                "source": chunk.get("source", ""),
                "section": chunk.get("section", ""),
                "score": chunk.get("score"),
                "preview": body[:420] + ("..." if len(body) > 420 else ""),
            })
        if not used and len(cited) == 1:
            break
    return cited


# A period after one of these is an abbreviation, not the end of a sentence. Splitting
# on it cuts "a late fee of Rs. 500" down to "a late fee of Rs.", which drops the one
# number the student asked for.
ABBREVIATIONS = {
    "rs", "no", "nos", "sr", "jr", "dr", "prof", "mr", "mrs", "ms", "vs", "viz",
    "etc", "approx", "govt", "dept", "hrs", "yrs", "fig", "sec", "ref", "art", "cl",
    "i.e", "e.g",
}
SENTENCE_BREAK_RE = re.compile(r"(?<=[.!?])\s+")
LAST_WORD_RE = re.compile(r"[\s(\[\"']")
# M.E., B.E., Ph.D., i.e. — a dotted initialism, not the end of a sentence. Splitting on
# it strands the amount that follows from the programme it belongs to.
INITIALISM_RE = re.compile(r"^[a-z]{1,3}(?:\.[a-z]{1,3})+$")


def ends_with_abbreviation(text: str) -> bool:
    tail = text.rstrip()
    if not tail.endswith("."):
        return False
    word = LAST_WORD_RE.split(tail[:-1])[-1].lower()
    return (word in ABBREVIATIONS
            or INITIALISM_RE.match(word) is not None
            or (len(word) == 1 and word.isalpha()))


def split_sentences(text: str):
    """Sentence split that keeps an abbreviation attached to what follows it."""
    sentences = []
    for part in SENTENCE_BREAK_RE.split(text):
        if sentences and ends_with_abbreviation(sentences[-1]):
            sentences[-1] = f"{sentences[-1]} {part}"
        else:
            sentences.append(part)
    return [s.strip() for s in sentences if s.strip()]


def extractive_answer(question: str, results):
    """Used when no GROQ_API_KEY is set: quote the retrieved text instead of generating."""
    terms = {w for w in re.findall(r"[a-z0-9]+", query.expand(question).lower()) if len(w) > 3}
    body = results[0]["text"].split("\n", 1)[-1]
    sentences = [s for s in split_sentences(body) if len(s) > 30]
    ranked = sorted(
        sentences,
        key=lambda s: len(terms & set(re.findall(r"[a-z0-9]+", s.lower()))),
        reverse=True,
    )
    picked = ranked[:2] if ranked else sentences[:2]
    ordered = [s for s in sentences if s in picked][:2]
    return " ".join(ordered) + " [1]"


def answer(question: str, history=None):
    started = time.perf_counter()
    history = history or []
    standalone = rewrite_question(question, history)
    results, debug = retrieve.search(standalone)
    retrieval_ms = int((time.perf_counter() - started) * 1000)

    unsupported = retrieve.unsupported(standalone, results)
    if unsupported:
        return {
            "answer": config.REFUSAL_TEXT,
            "refused": True,
            "citations": [],
            "mode": "refusal",
            "degraded": None,
            "rewritten": standalone,
            "retrieved": results,
            "debug": debug | {"refused_because": unsupported},
            "retrieval_ms": retrieval_ms,
            "generation_ms": 0,
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }

    context = build_context(results)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in history[-config.HISTORY_TURNS:]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({
        "role": "user",
        "content": f"CONTEXT:\n{context}\n\nQUESTION:\n{standalone}",
    })

    # Latency here is the generator's, not the retriever's. Keeping them apart is what
    # tells a slow model from a slow index when someone reports a long wait.
    generation_started = time.perf_counter()
    degraded = None
    try:
        text, mode = llm.complete(messages, timeout=config.GEN_TIMEOUT), llm.describe()
    except llm.NoGenerator:
        text, mode = extractive_answer(question, results), "extractive"
        degraded = {"reason": "no-generator",
                    "detail": "No generator is configured, so the answer is quoted from the source."}
    except llm.Timeout as exc:
        text = extractive_answer(question, results)
        mode = f"extractive ({exc})"
        degraded = {"reason": "timeout",
                    "detail": (f"The {llm.provider()} model did not answer within "
                               f"{config.GEN_TIMEOUT:g} seconds, so the answer is quoted "
                               "from the source instead.")}
    except Exception as exc:
        text = extractive_answer(question, results)
        mode = f"extractive ({llm.provider()} error: {str(exc)[:120]})"
        degraded = {"reason": "error",
                    "detail": (f"The {llm.provider()} model could not be reached, so the "
                               "answer is quoted from the source instead.")}
    generation_ms = int((time.perf_counter() - generation_started) * 1000)

    refused = config.REFUSAL_TEXT.lower().rstrip(".") in text.lower()
    return {
        "answer": text,
        "refused": refused,
        "citations": [] if refused else citations_for(text, results),
        "mode": mode,
        "degraded": degraded,
        "rewritten": standalone,
        "retrieved": results,
        "debug": debug,
        "retrieval_ms": retrieval_ms,
        "generation_ms": generation_ms,
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }
