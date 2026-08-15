"""Lazy singletons for the embedding and re-ranking models."""
import threading

import numpy as np

from . import config

_lock = threading.Lock()
_embedder = None
_reranker = None


def embedder():
    global _embedder
    if _embedder is None:
        with _lock:
            if _embedder is None:
                from sentence_transformers import SentenceTransformer
                _embedder = SentenceTransformer(config.EMBED_MODEL)
    return _embedder


def reranker():
    global _reranker
    if _reranker is None:
        with _lock:
            if _reranker is None:
                from sentence_transformers import CrossEncoder
                _reranker = CrossEncoder(config.RERANK_MODEL)
    return _reranker


def encode(texts, batch_size: int = 32) -> np.ndarray:
    vectors = embedder().encode(
        list(texts),
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(vectors, dtype="float32")


def rerank_scores(question: str, texts) -> list:
    if not texts:
        return []
    pairs = [(question, t) for t in texts]
    return [float(s) for s in reranker().predict(pairs, show_progress_bar=False)]


def warmup():
    encode(["warmup"])
    if config.USE_RERANKER:
        rerank_scores("warmup", ["warmup"])
