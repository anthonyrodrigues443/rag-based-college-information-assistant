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

`scripts/eval.py` and `scripts/eval_full.py` hold 62 labelled questions:
50 answerable, each tagged with the document that actually contains the answer, and 12
off-topic ones that must be refused.

```bash
./.venv/bin/python scripts/eval.py                 # quick retrieval check
./.venv/bin/python scripts/eval_full.py            # ablation, baselines, latency, judged answers
./.venv/bin/python scripts/eval_full.py --retrieval-only
```

Retrieval, same 50 questions through four configurations:

| Configuration | Hit@1 | Hit@5 | MRR |
|---|---|---|---|
| BM25 only | 0.76 | 0.92 | 0.82 |
| Dense only (MiniLM) | 0.86 | 0.96 | 0.89 |
| Hybrid, RRF fused | 0.80 | 0.94 | 0.86 |
| Hybrid + cross-encoder re-rank | 0.86 | 0.98 | 0.92 |

Fusing BM25 into dense retrieval lowers Hit@1 on its own, from 0.86 to
0.80: it adds recall by catching exact codes, and adds noise to the top rank.
The cross-encoder is what recovers it.

Answers, marked by a second LLM pass against the source text. Correct means it states what the
source says with the right numbers and dates. Grounded means every fact in it appears in that source.

| System | Correct | Grounded |
|---|---|---|
| CampusQuery | 44/50 | 42/47 |
| Same model, no retrieval | 0/50 | 7/50 |

Refusals: 11/12 off-topic questions refused,
2/50 answerable questions wrongly refused.
Latency on a local 12B model: median 5.2 s, 90th percentile
6.6 s.

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
  scheduler.py  weekly refresh: re-read seed files, re-fetch URLs, drop stale documents
  generate.py   prompt, citations, refusal, conversation rewrite
  main.py       FastAPI routes
web/            demo college site, chat widget, admin console (plain HTML, CSS, JS)
data/seed/      the demo college's documents: 20 markdown files plus 2 scanned PDFs read by OCR
scripts/        make_seed.py, make_scans.py, eval.py, eval_full.py, make_chart.py, update_deck.py
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
| `POST /api/admin/refresh` | token | Run the scheduled refresh now |
| `POST /api/admin/reindex-seed` | token | Wipe and rebuild from `data/seed` |
| `DELETE /api/admin/document/{id}` | token | Remove one document from the index |

Admin routes need the `X-Admin-Token` header matching `ADMIN_TOKEN`. Change it before exposing
the app anywhere.

## Known limits

- The scheduled refresh re-reads seed files and re-fetches indexed URLs, but it does not
  discover new pages on its own. A real deployment would crawl, not just refresh what it knows.
- OCR runs only when a PDF page has almost no extractable text. It has not been tested against
  a large batch of real scanned notices.
- `data/index` is rebuilt in full when a document is deleted. Fine at this scale, not at 100k chunks.
- A local 12B model answers in roughly 5 to 10 seconds. Groq is much faster if latency matters
  for the demo.
