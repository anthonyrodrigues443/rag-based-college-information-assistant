#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv --system-site-packages
  ./.venv/bin/pip install -r requirements.txt
fi

if [ ! -f data/index/vectors.faiss ]; then
  echo "No index found, building from the seed corpus..."
  ./.venv/bin/python -c "from app.ingest import reindex_seed; print(len(reindex_seed()), 'documents indexed')"
fi

exec ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8000}" "$@"
