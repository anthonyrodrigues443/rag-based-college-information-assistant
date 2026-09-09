"""Hybrid retrieval: BM25 + dense, fused by reciprocal rank, then re-ranked."""
import math

from . import config, models, query
from .store import store


# How far a programme match moves a candidate, on the same 0-1 scale as `score`.
PROGRAMME_WEIGHT = 0.3


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))


def reciprocal_rank_fusion(*ranked_lists, k=None):
    k = k or config.RRF_K
    fused = {}
    for ranked in ranked_lists:
        for rank, (chunk_id, _score) in enumerate(ranked):
            fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(fused.items(), key=lambda pair: pair[1], reverse=True)


def search(question: str, top_n: int = None):
    """Returns (results, debug). results are the top_n chunks after re-ranking."""
    top_n = top_n or config.TOP_N_CONTEXT
    if not store.chunks:
        return [], {"dense": 0, "bm25": 0, "fused": 0, "reranked": False}

    # Every stage sees the expanded question: BM25 needs the corpus's own words, the
    # embedder needs more than a two-letter token, and the cross-encoder scores the
    # answer-bearing passage far higher once the abbreviation is spelled out.
    expanded = query.expand(question)
    asked = query.entities(question)

    vector = models.encode([expanded])[0]
    dense = store.dense_search(vector, config.TOP_K_DENSE)
    lexical = store.bm25_search(expanded, config.TOP_K_BM25)
    fused = reciprocal_rank_fusion(dense, lexical)

    dense_scores = dict(dense)
    lexical_scores = dict(lexical)
    candidates = [store.chunks[cid] | {
        "rrf": round(score, 5),
        "dense": round(dense_scores.get(cid, 0.0), 4),
        "bm25": round(lexical_scores.get(cid, 0.0), 3),
    } for cid, score in fused[: config.TOP_K_DENSE + config.TOP_K_BM25]]

    reranked = False
    if config.USE_RERANKER and candidates:
        # The cross-encoder alone mis-ranks short colloquial questions ("can I get a
        # room", "bunked lectures"): it buries the right chunk that dense retrieval
        # already had at rank 1. Blending it with the fusion rank keeps its precision
        # without letting it override retrieval on its own.
        raw = models.rerank_scores(expanded, [c["text"] for c in candidates])
        best_rrf = max(c["rrf"] for c in candidates) or 1.0
        for candidate, score in zip(candidates, raw):
            candidate["rerank"] = round(score, 4)
            candidate["score"] = round(
                config.RERANK_WEIGHT * sigmoid(score)
                + (1 - config.RERANK_WEIGHT) * (candidate["rrf"] / best_rrf),
                4,
            )
        reranked = True
    else:
        best_rrf = max(c["rrf"] for c in candidates) or 1.0
        for candidate in candidates:
            candidate["score"] = round(candidate["rrf"] / best_rrf, 4)

    # A section about the B.E. fee is a good match for any fee question, which is how a
    # question about the M.E. ends up answered with undergraduate rates. Ordering has to
    # know that the passage is about a different programme from the one asked about.
    for candidate in candidates:
        candidate["entity"] = query.programme_alignment(candidate["text"], asked["programme"])
        candidate["score"] = round(candidate["score"] + PROGRAMME_WEIGHT * candidate["entity"], 4)
    candidates.sort(key=lambda c: c["score"], reverse=True)

    debug = {
        "dense": len(dense),
        "bm25": len(lexical),
        "fused": len(fused),
        "reranked": reranked,
        "expanded": expanded if expanded != question else None,
        "programme": sorted(asked["programme"]),
        "institutions": asked["institution"],
        "top_score": candidates[0]["score"] if candidates else None,
    }
    return candidates[:top_n], debug


def unsupported(question: str, results):
    """Why the retrieved content cannot answer this question, or None when it can.

    A high retrieval score means the passage looks like the question, not that it is
    about the same thing. "The syllabus of the IIT Bombay machine learning course"
    retrieves this college's own syllabus revision at a comfortable score, and citing it
    presents another institution's course as answered. So the entities the student named
    are checked against what actually came back before the score is consulted at all.
    """
    if not results:
        return "nothing was retrieved"

    asked = query.entities(question)
    for name in asked["institution"]:
        if not any(query.mentions(f"{r['title']} {r['text']}", name) for r in results):
            return f"the indexed content does not describe {name}"

    if asked["programme"] and all(r.get("entity") == -1 for r in results):
        return "every retrieved section is about a different programme"

    if below_threshold(results):
        return "nothing retrieved is a close enough match"
    return None


def below_threshold(results) -> bool:
    """True when nothing retrieved is good enough to answer from.

    Judged on the raw cross-encoder score, not on the blended ordering score: the
    blend contains a rank term that is 1.0 for the top candidate by construction,
    so it says nothing about whether the corpus actually covers the question.
    Any of the returned chunks being a decent match is enough to answer.
    """
    if not results:
        return True
    if not config.USE_RERANKER:
        return False
    best = max(r.get("rerank", -99) for r in results)
    return best < config.REFUSAL_THRESHOLD
