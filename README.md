# CampusQuery

A retrieval-augmented assistant for a college website. It answers a student's question
using only the college's own published content, and shows the source behind every answer.
When the corpus does not cover the question it says so instead of guessing.

Two surfaces:

- **`/`** the demo college site with the chat widget. This is the product. Visitors only ask.
- **`/admin`** the back office: upload documents, index a URL, paste text, rebuild the index.
  On a real deployment staff load the corpus once and refresh it on a schedule. It is exposed
  here so you can point CampusQuery at your own documents and see how it answers them.

## Run it

```bash
cd ~/Desktop/CampusQuery
cp .env.example .env       # already done if .env exists
./run.sh                   # http://127.0.0.1:8000
```

`run.sh` creates the venv, builds the index from `data/seed` on first run, and starts the server.
First start takes about 25 seconds because the embedding and re-ranking models load into memory.

### Generation

The generator is pluggable and chosen by `LLM_PROVIDER` in `.env`:

| Setting | What runs |
|---|---|
| `auto` (default) | Groq if `GROQ_API_KEY` is set, else a local Ollama server, else extractive |
| `ollama` | Local model, no API key. Set `OLLAMA_MODEL`, e.g. `gemma4:12b` |
| `groq` | Hosted, needs `GROQ_API_KEY`. Set `GROQ_MODEL` |
| `none` | No generator. The app quotes the retrieved sentences verbatim |

With no generator available the pipeline still retrieves, cites and refuses. Only the sentence
writing changes. `/api/health` and the `mode` field on every answer say which one is live, so a
misconfigured key is visible rather than silent.

## How a question is answered

```
question
  -> rewrite using the last turns, so "and for second year?" becomes standalone
  -> embed with all-MiniLM-L6-v2 (384-d)
  -> FAISS cosine over the chunk index        top 20
  -> BM25 over the same chunks                top 20
  -> reciprocal rank fusion of the two lists
  -> cross-encoder re-rank, blended with the fusion rank
  -> top 5 chunks into a context-only prompt, temperature 0.2
  -> answer with [n] citations, or a refusal
```

Two scores do two different jobs. Ordering uses
`RERANK_WEIGHT * sigmoid(cross-encoder) + (1 - w) * normalised RRF`, because the cross-encoder
on its own buries the right chunk for short colloquial questions. Refusal uses the raw
cross-encoder score of the best returned chunk against `REFUSAL_THRESHOLD`, because the
blended score contains a rank term that is 1.0 for the top candidate by construction and
therefore says nothing about whether the corpus covers the question at all.

## Evaluation

`scripts/eval.py` holds 40 labelled questions: 32 answerable, each tagged with the document
that actually contains the answer, and 8 off-topic ones that must be refused.

```bash
./.venv/bin/python scripts/eval.py            # current settings
./.venv/bin/python scripts/eval.py --sweep    # compare re-ranker weights
```

Measured on the 20-document seed corpus:

| | Hit@1 | Hit@5 | MRR | off-topic refused | false refusals |
|---|---|---|---|---|---|
| pure cross-encoder ordering | 0.81 | 1.00 | 0.89 | 8/8 | 7/32 |
| blended ordering, raw-score refusal | 0.84 | 1.00 | 0.90 | 8/8 | 2/32 |

## Layout

```
app/
  config.py     settings, read from .env
  chunking.py   clean, split on headings, window with overlap, keep the heading as a prefix
  models.py     lazy singletons for the embedder and cross-encoder
  store.py      FAISS index + BM25 + chunk and document metadata, persisted to data/index
  ingest.py     extract from pdf/html/md/txt/url, chunk, embed, add to the index
  retrieve.py   hybrid search, fusion, re-ranking, refusal decision
  llm.py        Groq or Ollama behind one interface
  generate.py   prompt, citations, refusal, conversation rewrite
  main.py       FastAPI routes
web/            demo college site, chat widget, admin console (plain HTML, CSS, JS)
data/seed/      the demo college's documents, 20 markdown files with front matter
scripts/        make_seed.py, eval.py
```

## API

| Route | Auth | Purpose |
|---|---|---|
| `POST /api/chat` | none | `{question, history[], debug}` returns answer, citations, mode, latency |
| `GET /api/site/notices` | none | The notices the demo site renders, taken from the index |
| `GET /api/health` | none | Index stats and which generator is live |
| `GET /api/admin/status` | token | Index stats and every indexed document |
| `POST /api/admin/ingest/files` | token | Multipart upload: pdf, html, md, txt. 20 MB per file |
| `POST /api/admin/ingest/urls` | token | Fetch and index web pages |
| `POST /api/admin/ingest/text` | token | Index pasted text |
| `POST /api/admin/reindex-seed` | token | Wipe and rebuild from `data/seed` |
| `DELETE /api/admin/document/{id}` | token | Remove one document from the index |

Admin routes need the `X-Admin-Token` header matching `ADMIN_TOKEN`. Change it before exposing
the app anywhere.

## Known limits

- The index rebuild is manual. There is no scheduler yet, so a changed page is not picked up
  until someone re-indexes it.
- OCR runs only when a PDF page has almost no extractable text. It has not been tested against
  a large batch of real scanned notices.
- `data/index` is rebuilt in full when a document is deleted. Fine at this scale, not at 100k chunks.
- A local 12B model answers in roughly 5 to 10 seconds. Groq is much faster if latency matters
  for the demo.
