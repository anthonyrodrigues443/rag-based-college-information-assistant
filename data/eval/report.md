# CampusQuery result analysis

Corpus: 22 documents, 82 chunks. Generator: ollama:gemma4:12b.

Question set: 62 labelled questions, 50 answerable (each tagged with the document that holds the answer) and 12 off topic that must be refused.

## Retrieval, same questions through four configurations

| Configuration | Hit@1 | Hit@5 | MRR |
|---|---|---|---|
| BM25 only | 0.76 | 0.92 | 0.82 |
| Dense only (MiniLM) | 0.86 | 0.96 | 0.89 |
| Hybrid, RRF fused | 0.80 | 0.94 | 0.86 |
| Hybrid + cross-encoder re-rank | 0.86 | 0.98 | 0.92 |

## Refusals

- Off topic questions correctly refused: 11/12
- Answerable questions wrongly refused: 2/50
  - my answer sheet was marked badly, can it be checked again
  - How many seats does the AIML department have?
  - LEAKED (should have refused): What is the syllabus of the IIT Bombay machine learning course?
