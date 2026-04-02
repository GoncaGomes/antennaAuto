# Retrieval Comparison Summary

## Configurations

| Configuration | Rogers RT5880 in top-3 text results | First rank with explicit Rogers evidence | Top text source ids |
|---|---:|---:|---|
| baseline_current | yes | 1 | chunk_010, page_004, chunk_013 |
| paragraph_only | yes | 1 | chunk_027, chunk_026, page_004 |
| paragraph_rrf | yes | 1 | chunk_027, chunk_026, page_004 |
| paragraph_real_embedding | yes | 1 | chunk_027, chunk_026, page_004 |
| paragraph_real_embedding_rrf | yes | 2 | chunk_026, chunk_027, chunk_076 |

## Best Configuration For `substrate material`

`paragraph_only` best surfaces explicit evidence because Rogers RT5880 appears in the top-3 text results and first appears at rank 1.

## Tradeoffs

- Weighted fusion versus RRF: weighted surfaced explicit Rogers evidence in 3 run(s), while RRF did so in 2 run(s).
- Hash embeddings versus sentence-transformer embeddings: hash backends produced explicit Rogers evidence in 3 run(s); sentence-transformer backends did so in 2 run(s).
- Paragraph chunking versus fixed chunking: fixed chunking produced explicit Rogers evidence in 1 run(s); paragraph chunking did so in 4 run(s).
