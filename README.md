# AntennaAuto MVP

This repository is a local MVP pipeline for single-paper ingestion, deterministic parsing, bundle generation, indexing, and field-oriented retrieval over antenna papers.

## Current Retrieval Default

The default retrieval baseline is now:

- `chunking_mode="paragraph"`
- `chunk_overlap_pct=0.15`
- `paragraph_min_chars=120`
- `paragraph_max_chars=800`
- `embedding_backend="sentence_transformer"`
- `embedding_model_name="sentence-transformers/all-MiniLM-L6-v2"`
- `fusion_strategy="weighted"`
- `weighted_alpha=0.7`
- `weighted_beta=0.3`
- `rrf_k=60`

This baseline was chosen because paragraph-first chunking produced cleaner evidence units than fixed chunking, weighted fusion surfaced more extraction-ready results than RRF on the benchmark set, and the sentence-transformer backend improved retrieval quality for explicit evidence such as `Rogers RT5880` and numeric spans such as the `51Ω to 55Ω` input-impedance range.

## Default Usage

Build a parsed and indexed run with the project defaults:

```powershell
uv run python -m mvp.cli --input data/raw/paper_001/article.pdf --index
```

Run the default benchmark configuration and write the concise confirmation report:

```powershell
uv run python -m mvp.benchmark --input data/raw/paper_001/article.pdf --write-default-confirmation
```

## Retrieval Experiments

Legacy and experimental modes are still available through config flags and named benchmark presets.

Examples:

```powershell
uv run python -m mvp.cli --input data/raw/paper_001/article.pdf --index --chunking-mode fixed --embedding-backend hash
uv run python -m mvp.cli --input data/raw/paper_001/article.pdf --index --fusion-strategy rrf
uv run python -m mvp.benchmark --input data/raw/paper_001/article.pdf --config-name baseline_current
uv run python -m mvp.benchmark --input data/raw/paper_001/article.pdf --config-name paragraph_real_embedding_rrf
```

Supported retrieval toggles:

- `--chunking-mode fixed|paragraph`
- `--chunk-overlap-pct`
- `--paragraph-min-chars`
- `--paragraph-max-chars`
- `--embedding-backend hash|sentence_transformer`
- `--embedding-model-name`
- `--fusion-strategy weighted|rrf`
- `--weighted-alpha`
- `--weighted-beta`
- `--rrf-k`

## Migration Note

The default dense backend is now `sentence_transformer` instead of `hash`. Existing runs indexed with the older hash default are still readable, but they should be re-indexed if you want the new default behavior, updated diagnostics, and directly comparable benchmark outputs.
