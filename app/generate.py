"""Grounded answer generation: context-only prompt, citations, explicit refusal."""
import re
import time

from . import config, llm, retrieve

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
        rewritten = llm.complete(turns, temperature=0, max_tokens=80)
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


def extractive_answer(question: str, results):
    """Used when no GROQ_API_KEY is set: quote the retrieved text instead of generating."""
    terms = {w for w in re.findall(r"[a-z0-9]+", question.lower()) if len(w) > 3}
    body = results[0]["text"].split("\n", 1)[-1]
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if len(s.strip()) > 30]
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

    if retrieve.below_threshold(results):
        return {
            "answer": config.REFUSAL_TEXT,
            "refused": True,
            "citations": [],
            "mode": "refusal",
            "rewritten": standalone,
            "retrieved": results,
            "debug": debug,
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

    try:
        text, mode = llm.complete(messages), llm.describe()
    except llm.NoGenerator:
        text, mode = extractive_answer(question, results), "extractive"
    except Exception as exc:
        text = extractive_answer(question, results)
        mode = f"extractive ({llm.provider()} error: {str(exc)[:120]})"

    refused = config.REFUSAL_TEXT.lower().rstrip(".") in text.lower()
    return {
        "answer": text,
        "refused": refused,
        "citations": [] if refused else citations_for(text, results),
        "mode": mode,
        "rewritten": standalone,
        "retrieved": results,
        "debug": debug,
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }
