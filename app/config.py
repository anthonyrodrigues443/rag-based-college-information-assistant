import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"


def load_dotenv(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_dotenv()


def env(key: str, default=None):
    value = os.environ.get(key)
    return value if value not in (None, "") else default


# Overridable so a test run, or a second instance, can keep its own corpus and index.
DATA = Path(env("DATA_DIR", ROOT / "data"))
SEED_DIR = Path(env("SEED_DIR", DATA / "seed"))
INDEX_DIR = Path(env("INDEX_DIR", DATA / "index"))
UPLOAD_DIR = Path(env("UPLOAD_DIR", DATA / "uploads"))

EMBED_MODEL = env("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
RERANK_MODEL = env("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
EMBED_DIM = 384

# auto = Groq when a key is set, else a local Ollama server, else extractive answers.
LLM_PROVIDER = env("LLM_PROVIDER", "auto")

GROQ_API_KEY = env("GROQ_API_KEY")
GROQ_MODEL = env("GROQ_MODEL", "llama-3.1-8b-instant")

OLLAMA_HOST = env("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = env("OLLAMA_MODEL", "gemma4:12b")
OLLAMA_TIMEOUT = float(env("OLLAMA_TIMEOUT", 120))

# How long a student waits for the generator before the answer is served from the
# retrieved text instead. A local model that has not answered in this long is not going
# to feel interactive, and the extractive answer is already correct and cited.
GEN_TIMEOUT = float(env("GEN_TIMEOUT", 30))

CHUNK_WORDS = int(env("CHUNK_WORDS", 300))
CHUNK_OVERLAP_WORDS = int(env("CHUNK_OVERLAP_WORDS", 45))
MIN_CHUNK_WORDS = int(env("MIN_CHUNK_WORDS", 25))

TOP_K_DENSE = int(env("TOP_K_DENSE", 20))
TOP_K_BM25 = int(env("TOP_K_BM25", 20))
RRF_K = int(env("RRF_K", 60))
TOP_N_CONTEXT = int(env("TOP_N_CONTEXT", 5))

# Ordering: blended score = RERANK_WEIGHT * sigmoid(cross-encoder) + (1-w) * normalised RRF.
RERANK_WEIGHT = float(env("RERANK_WEIGHT", 0.6))
# Refusal: raw cross-encoder logit of the best returned chunk. Picked with scripts/eval.py.
REFUSAL_THRESHOLD = float(env("REFUSAL_THRESHOLD", -6.0))
REFUSAL_TEXT = "Not available in the college content."

# Scheduled refresh: re-read seed files, re-fetch indexed URLs, drop stale documents.
REINDEX_ENABLED = env("REINDEX_ENABLED", "1") == "1"
REINDEX_INTERVAL_HOURS = float(env("REINDEX_INTERVAL_HOURS", 168))

HISTORY_TURNS = int(env("HISTORY_TURNS", 4))
ADMIN_TOKEN = env("ADMIN_TOKEN", "campusquery-demo")
USE_RERANKER = env("USE_RERANKER", "1") == "1"

for d in (INDEX_DIR, UPLOAD_DIR):
    d.mkdir(parents=True, exist_ok=True)
