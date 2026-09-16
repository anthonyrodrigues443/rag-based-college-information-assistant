"""Upgrade an actual persisted legacy index without losing uploads or citation links."""
import hashlib
import json

import numpy as np
import pytest

from app import config
from app.store import Store, doc_id_for


@pytest.mark.parametrize("already_duplicated", [False, True])
def test_legacy_index_is_migrated_and_deduplicated(tmp_path, monkeypatch, already_duplicated):
    monkeypatch.setattr(config, "INDEX_DIR", tmp_path)
    original = Store()
    key = "contact.md"
    legacy = hashlib.sha1(key.encode()).hexdigest()[:12]
    seed = doc_id_for(key, "seed")
    upload = doc_id_for(key, "upload")
    vector = np.eye(3, config.EMBED_DIM, dtype="float32")
    original.add_document(legacy, {"origin": "seed", "key": key, "title": "Old policy"},
                          [{"text": "Old accepted policy"}], vector[:1])
    original.docs[legacy]["indexed_at"] = "2026-08-01T00:00:00+00:00"
    original.add_document(upload, {"origin": "upload", "key": key, "title": "Staff upload"},
                          [{"text": "A different document with the same filename"}], vector[1:2])
    if already_duplicated:
        original.add_document(seed, {"origin": "seed", "key": key, "title": "New policy"},
                              [{"text": "New accepted policy"}], vector[2:3])
    original.save()

    upgraded = Store()
    assert set(upgraded.docs) == {seed, upload}
    assert upgraded.stats()["chunks"] == upgraded.stats()["vectors"] == 2
    assert upgraded.document(legacy) == upgraded.docs[seed]
    chosen = next(c for c in upgraded.chunks if c["doc_id"] == seed)
    assert chosen["text"] == ("New accepted policy" if already_duplicated else "Old accepted policy")
    assert np.array_equal(upgraded.index.reconstruct(chosen["id"]),
                          vector[2 if already_duplicated else 0])
    before = json.loads(upgraded.docs_path.read_text())
    assert Store().docs == before, "migration is persistent and idempotent"

    upgraded.add_document(seed, {"origin": "seed", "key": key},
                          [{"text": "Refreshed current policy"}], vector[:1])
    upgraded.save()
    reloaded = Store()
    assert reloaded.document(legacy)["doc_id"] == seed
    assert len(reloaded.docs) == 2 and len(reloaded.chunks) == 2
    assert upload in reloaded.docs
