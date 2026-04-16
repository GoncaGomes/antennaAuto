# Extraction Agent MVP

## What It Does

This is the first extraction agent for the project.

It takes an existing prepared `run_dir`, uses the existing `BundleRetriever` retrieval interface, calls an LLM once with one possible repair pass, validates the result with Pydantic, and writes:

- `runs/<run_id>/outputs/antenna_architecture_spec_mvp_v2.json`
- `runs/<run_id>/outputs/extraction_run_report.json`

The extractor is grounded only in the prepared run artifacts. It does not control ingestion, parsing, or indexing directly.

## Expected Input

The extractor expects a run directory that already contains:

- `bundle/`
- `indexes/bm25/`
- `indexes/faiss/`

Typical flow:

1. prepare the run deterministically with ingestion/parsing/indexing
2. run the extraction agent on that `run_dir`

## Required Environment Variables

The extractor loads `.env` from the project root and requires:

- `NEW_OPENAI_API_KEY` preferred, otherwise `OPENAI_API_KEY`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_CHANNEL_ID`

If any of these are missing, the extractor fails with a clear error before making a request.

Secrets are not printed and are not written into the spec JSON or extraction report.

## Command

Real extraction call:

```powershell
uv run python -m mvp.extract --run-dir runs/<run_id> --model gpt-4o
```

Optional flags:

```powershell
uv run python -m mvp.extract --run-dir runs/<run_id> --model gpt-4o --top-k 5 --debug
```

## Outputs

### Structured spec

`antenna_architecture_spec_mvp_v2.json` contains:

- schema metadata
- document context
- classification
- units
- parameters
- materials
- layers
- entities
- feeds
- instances
- quality
- `evidence_used`

The final JSON stores only evidence IDs, not copied evidence snippets.

### Extraction report

`extraction_run_report.json` contains:

- run id
- timestamp
- model name
- extraction status
- retrieval queries used
- retrieved evidence ids per block
- final evidence ids used
- validation success or failure
- schema errors
- warnings

If the first model response fails validation, the pipeline performs one repair pass. If repair still fails, the invalid payload is saved in the report and the command fails clearly.

## Retrieval Scope

The extraction agent uses targeted retrieval for:

- classification
- materials
- layers
- parameters
- entities
- feeds
- quality

It uses:

- `search_text`
- `search_tables`
- `search_figures`
- `get_section`
- `get_table`
- `get_figure`
- `get_evidence_by_id`

## What Is Intentionally Out Of Scope

This first MVP does not do:

- raw image analysis
- OCR
- CST build logic
- simulation setup extraction
- operations trees
- optimization
- UI

## Why Raw Image Analysis Is Not Used Yet

The current figure layer is still heuristic and noisy. For this reason, the first extraction agent uses only:

- retrieved text evidence
- structured table evidence
- fallback table evidence
- figure caption/context metadata already present in the bundle

This keeps the extractor auditable and avoids overclaiming geometric facts that are not explicitly grounded in the current pipeline.
