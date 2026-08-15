"""Hybrid retrieval: BM25 + dense, fused by reciprocal rank, then re-ranked."""
import math

from . import config, models
from .store import store


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

    vector = models.encode([question])[0]
    dense = store.dense_search(vector, config.TOP_K_DENSE)
    lexical = store.bm25_search(question, config.TOP_K_BM25)
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
        raw = models.rerank_scores(question, [c["text"] for c in candidates])
        best_rrf = max(c["rrf"] for c in candidates) or 1.0
        for candidate, score in zip(candidates, raw):
            candidate["rerank"] = round(score, 4)
            candidate["score"] = round(
                config.RERANK_WEIGHT * sigmoid(score)
                + (1 - config.RERANK_WEIGHT) * (candidate["rrf"] / best_rrf),
                4,
            )
        candidates.sort(key=lambda c: c["score"], reverse=True)
        reranked = True
    else:
        best_rrf = max(c["rrf"] for c in candidates) or 1.0
        for candidate in candidates:
            candidate["score"] = round(candidate["rrf"] / best_rrf, 4)

    debug = {
        "dense": len(dense),
        "bm25": len(lexical),
        "fused": len(fused),
        "reranked": reranked,
        "top_score": candidates[0]["score"] if candidates else None,
    }
    return candidates[:top_n], debug


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
