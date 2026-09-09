# CampusQuery result analysis

Corpus: 22 documents, 82 chunks. Generator: ollama:gemma4:12b.

Question set: 62 labelled questions, 50 answerable (each tagged with the document that holds the answer) and 12 off topic that must be refused.

## Retrieval, same questions through five configurations

| Configuration | Hit@1 | Hit@5 | MRR |
|---|---|---|---|
| BM25 only | 0.76 | 0.92 | 0.82 |
| Dense only (MiniLM) | 0.86 | 0.96 | 0.89 |
| Hybrid, RRF fused | 0.80 | 0.94 | 0.86 |
| Hybrid + cross-encoder re-rank | 0.86 | 0.98 | 0.92 |
| Shipped pipeline (+ question normalisation, entity ordering) | 0.92 | 0.98 | 0.95 |

## Refusals

- Off topic questions correctly refused: 12/12
- Answerable questions wrongly refused: 0/50

## Answers, judged

Each answer is marked by a second LLM pass against the official college text: correct means it states what the source says with the right numbers and dates, grounded means every fact in it appears in that source.

| System | Correct | Grounded |
|---|---|---|
| CampusQuery (retrieval + generation) | 47/50 | 45/50 |
| Same model, no retrieval | 0/50 | 3/50 |

## Latency

- Median end to end: 7184 ms
- 90th percentile end to end: 11940 ms
- Median retrieval: 536 ms
- Median generation: 6522 ms
- 90th percentile generation: 10971 ms
- Refused without calling the generator: 0
- Fell back to the extractive answer: 0
