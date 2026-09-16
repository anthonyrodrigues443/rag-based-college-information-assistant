"""Persisted hybrid index: FAISS vectors + BM25 over the same chunks."""
import copy
import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from contextlib import contextmanager

import faiss
import numpy as np
from rank_bm25 import BM25Okapi

from . import config

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str):
    return TOKEN_RE.findall(text.lower())


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def doc_id_for(key: str, origin: str = "upload") -> str:
    return hashlib.sha1(f"{origin}\x00{key}".encode("utf-8")).hexdigest()[:12]


class Store:
    def __init__(self):
        self.lock = threading.RLock()
        self.chunks = []          # [{id, doc_id, title, source, url, kind, section, text}]
        self.docs = {}            # doc_id -> metadata
        self.index = faiss.IndexFlatIP(config.EMBED_DIM)
        self.bm25 = None
        self.load()

    # ---------------------------------------------------------------- paths
    @property
    def faiss_path(self):
        return config.INDEX_DIR / "vectors.faiss"

    @property
    def chunks_path(self):
        return config.INDEX_DIR / "chunks.jsonl"

    @property
    def docs_path(self):
        return config.INDEX_DIR / "docs.json"

    # ---------------------------------------------------------------- state
    def load(self):
        with self.lock:
            if self.faiss_path.exists() and self.chunks_path.exists():
                self.index = faiss.read_index(str(self.faiss_path))
                self.chunks = [
                    json.loads(line)
                    for line in self.chunks_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            if self.docs_path.exists():
                self.docs = json.loads(self.docs_path.read_text(encoding="utf-8"))
            migrated = self._migrate_identities()
            self._rebuild_bm25()
            if migrated:
                self.save()

    def _migrate_identities(self):
        """Upgrade key-only IDs and repair indexes refreshed by the previous release.

        Keep the newest version of each (origin, key), and retain old citation IDs as
        aliases. Vectors follow their chunk rows, never an independently sorted list.
        """
        groups = {}
        for old_id, doc in self.docs.items():
            key = doc.get("key") or doc.get("source")
            canonical = doc_id_for(key, doc.get("origin", "upload")) if key else old_id
            groups.setdefault(canonical, []).append((old_id, doc))
        winners, docs = {}, {}
        for canonical, versions in groups.items():
            old_id, doc = max(versions, key=lambda pair: (
                pair[1].get("indexed_at", ""), pair[0] == canonical))
            aliases = {alias for oid, d in versions for alias in [oid, *d.get("aliases", [])]}
            winners[old_id] = canonical
            docs[canonical] = {**doc, "doc_id": canonical,
                               "aliases": sorted(aliases - {canonical})}
        if docs == self.docs:
            return False
        vectors = self.index.reconstruct_n(0, self.index.ntotal)
        rows, chunks = [], []
        for row, chunk in enumerate(self.chunks):
            if chunk["doc_id"] in winners:
                rows.append(row)
                chunks.append({**chunk, "id": len(chunks),
                               "doc_id": winners[chunk["doc_id"]]})
        index = faiss.IndexFlatIP(config.EMBED_DIM)
        if rows:
            index.add(np.asarray(vectors[rows], dtype="float32"))
        self.docs, self.chunks, self.index = docs, chunks, index
        return True

    @contextmanager
    def transaction(self):
        """Restore both memory and persisted index files if an update fails."""
        with self.lock:
            docs, chunks = copy.deepcopy(self.docs), copy.deepcopy(self.chunks)
            index = faiss.clone_index(self.index)
            files = {p: p.read_bytes() if p.exists() else None
                     for p in (self.faiss_path, self.chunks_path, self.docs_path)}
            try:
                yield
            except Exception:
                self.docs, self.chunks, self.index = docs, chunks, index
                self._rebuild_bm25()
                for path, data in files.items():
                    if data is None:
                        path.unlink(missing_ok=True)
                    else:
                        path.write_bytes(data)
                raise

    def document(self, doc_id):
        """Resolve saved citation links from before the identity migration."""
        return self.docs.get(doc_id) or next(
            (doc for doc in self.docs.values() if doc_id in doc.get("aliases", [])), None)

    def save(self):
        with self.lock:
            faiss.write_index(self.index, str(self.faiss_path))
            with self.chunks_path.open("w", encoding="utf-8") as fh:
                for chunk in self.chunks:
                    fh.write(json.dumps(chunk, ensure_ascii=False) + "\n")
            self.docs_path.write_text(json.dumps(self.docs, indent=2), encoding="utf-8")

    def _rebuild_bm25(self):
        corpus = [tokenize(c["text"]) for c in self.chunks]
        self.bm25 = BM25Okapi(corpus) if corpus else None

    def reset(self):
        with self.lock:
            self.chunks, self.docs = [], {}
            self.index = faiss.IndexFlatIP(config.EMBED_DIM)
            self.bm25 = None
            for path in (self.faiss_path, self.chunks_path, self.docs_path):
                path.unlink(missing_ok=True)

    # ---------------------------------------------------------------- writes
    def add_document(self, doc_id, meta, chunks, vectors):
        """chunks: [{section, text}], vectors: (n, dim) float32 normalised."""
        with self.lock:
            aliases = self.docs.get(doc_id, {}).get("aliases", [])
            if doc_id in self.docs:
                self.delete_document(doc_id)
            start = len(self.chunks)
            for offset, chunk in enumerate(chunks):
                self.chunks.append({
                    "id": start + offset,
                    "doc_id": doc_id,
                    "title": meta.get("title", doc_id),
                    "source": meta.get("source", ""),
                    "url": meta.get("url", ""),
                    "kind": meta.get("kind", "page"),
                    "date": meta.get("date", ""),
                    "section": chunk.get("section", ""),
                    "text": chunk["text"],
                })
            self.index.add(vectors)
            self.docs[doc_id] = {
                **meta,
                "doc_id": doc_id,
                "n_chunks": len(chunks),
                "indexed_at": now_iso(),
                "aliases": aliases,
            }
            self._rebuild_bm25()
            return len(chunks)

    def delete_document(self, doc_id):
        """Rebuild without the document. Flat indexes are cheap to rebuild at this scale."""
        with self.lock:
            keep = [c for c in self.chunks if c["doc_id"] != doc_id]
            if len(keep) == len(self.chunks):
                return 0
            removed = len(self.chunks) - len(keep)
            vectors = self.index.reconstruct_n(0, self.index.ntotal)
            keep_rows = [c["id"] for c in keep]
            self.index = faiss.IndexFlatIP(config.EMBED_DIM)
            if keep_rows:
                self.index.add(np.asarray(vectors[keep_rows], dtype="float32"))
            for new_id, chunk in enumerate(keep):
                chunk["id"] = new_id
            self.chunks = keep
            self.docs.pop(doc_id, None)
            self._rebuild_bm25()
            return removed

    # ---------------------------------------------------------------- reads
    def dense_search(self, vector, k):
        if self.index.ntotal == 0:
            return []
        k = min(k, self.index.ntotal)
        scores, ids = self.index.search(vector.reshape(1, -1), k)
        return [(int(i), float(s)) for i, s in zip(ids[0], scores[0]) if i >= 0]

    def bm25_search(self, query, k):
        if not self.bm25:
            return []
        scores = self.bm25.get_scores(tokenize(query))
        top = np.argsort(scores)[::-1][:k]
        return [(int(i), float(scores[i])) for i in top if scores[i] > 0]

    def stats(self):
        with self.lock:
            kinds = {}
            for doc in self.docs.values():
                kinds[doc.get("kind", "page")] = kinds.get(doc.get("kind", "page"), 0) + 1
            return {
                "documents": len(self.docs),
                "chunks": len(self.chunks),
                "vectors": int(self.index.ntotal),
                "by_kind": kinds,
                "seed_documents": sum(1 for d in self.docs.values() if d.get("origin") == "seed"),
                "uploaded_documents": sum(1 for d in self.docs.values() if d.get("origin") == "upload"),
                "last_indexed": max((d.get("indexed_at", "") for d in self.docs.values()), default=""),
            }


store = Store()
