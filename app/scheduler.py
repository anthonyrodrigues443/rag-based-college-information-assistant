"""Keeps the index current.

A college page changes and nobody tells the assistant, so the corpus is refreshed
on a schedule: seed files are re-read, indexed URLs are re-fetched, and documents
whose source has disappeared are dropped. Uploaded documents are left alone, so a
refresh never destroys work done in the admin console.
"""
import threading
import time
from datetime import datetime, timedelta, timezone

from . import config, ingest
from .store import store

state = {
    "enabled": False,
    "interval_hours": None,
    "running": False,
    "last_run": None,
    "next_run": None,
    "last_result": None,
}

_stop = threading.Event()
_lock = threading.Lock()


def _now():
    return datetime.now(timezone.utc)


def refresh() -> dict:
    """Re-read every seed file, re-fetch every indexed URL, drop what is gone."""
    with _lock:
        state["running"] = True
        started = time.perf_counter()
        reindexed, refetched, dropped, errors = 0, 0, 0, []

        seed_paths = sorted(list(config.SEED_DIR.glob("*.md")) + list(config.SEED_DIR.glob("*.pdf")))
        seen = set()
        for path in seed_paths:
            seen.add(path.name)
            try:
                ingest.index_file(path, origin="seed")
                reindexed += 1
            except Exception as exc:
                errors.append(f"{path.name}: {exc}")

        for doc in list(store.docs.values()):
            key = doc.get("key", "")
            if doc.get("origin") == "seed":
                # `key` is the file name; `source` is only a label shown in citations
                if key not in seen and not (config.SEED_DIR / key).exists():
                    store.delete_document(doc["doc_id"])
                    dropped += 1
            elif doc.get("url"):
                try:
                    ingest.index_url(doc["url"], origin=doc.get("origin", "upload"))
                    refetched += 1
                except Exception as exc:
                    errors.append(f"{doc['url']}: {exc}")

        store.save()
        result = {
            "at": _now().isoformat(timespec="seconds"),
            "seed_reindexed": reindexed,
            "urls_refetched": refetched,
            "stale_dropped": dropped,
            "errors": errors,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "stats": store.stats(),
        }
        state.update(running=False, last_run=result["at"], last_result=result)
        return result


def _loop(interval_seconds: float):
    while not _stop.is_set():
        state["next_run"] = (_now() + timedelta(seconds=interval_seconds)).isoformat(timespec="seconds")
        if _stop.wait(interval_seconds):
            return
        try:
            refresh()
        except Exception as exc:                      # a failed refresh must not kill the thread
            state["last_result"] = {"at": _now().isoformat(timespec="seconds"), "error": str(exc)}


def start():
    if not config.REINDEX_ENABLED:
        state.update(enabled=False, interval_hours=config.REINDEX_INTERVAL_HOURS)
        return
    interval = max(60.0, config.REINDEX_INTERVAL_HOURS * 3600)
    state.update(enabled=True, interval_hours=config.REINDEX_INTERVAL_HOURS)
    threading.Thread(target=_loop, args=(interval,), daemon=True, name="reindex").start()


def stop():
    _stop.set()
