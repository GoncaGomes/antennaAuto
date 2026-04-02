# MVP Implementation Summary

## Goal

This repository is implementing a small, inspectable pipeline for working with one antenna-paper PDF per run.

The design is intentionally conservative:

- deterministic ingestion
- deterministic parsing
- inspectable bundle artifacts
- local indexing
- local retrieval over stable evidence units

The project is still not trying to solve the full extraction problem. The current objective is to make the paper auditable and retrieval-ready before introducing an extraction agent.

## What Is Implemented

### 1. Ingestion

The ingestion stage accepts a PDF path, validates it, creates a new run folder, and copies the source article into:

- `runs/<run_id>/input/article.pdf`

It also creates the bundle and index folders used later in the pipeline:

- `bundle/`
- `bundle/tables/`
- `bundle/figures/`
- `indexes/`

The run metadata is written to `bundle/metadata.json`, including:

- run id
- original path and filename
- file size
- SHA-256
- ingestion timestamp
- page count
- PDF metadata from PyMuPDF

### 2. Deterministic Parsing

The parsing stage builds a stable article bundle under `bundle/`.

#### Full text

- `pymupdf4llm` extracts the article into `bundle/fulltext.md`

#### Sections

- `bundle/sections.json` is generated as a simple page-oriented structure
- this is intentionally basic, but it gives downstream code stable text anchors

#### Figures

- PyMuPDF extracts image objects from the PDF
- each figure is written under `bundle/figures/<figure_id>/`
- each figure directory contains:
  - `image.png`
  - `caption.txt`
  - `context.txt`
  - `figure.json`

Figure caption and context extraction are still heuristic, but the bundle preserves inspectable local evidence for later use.

#### Tables

The table stage was refined to be conservative and auditable.

- caption detection is strict and line-based
- inline mentions like `... shown in Table 2 ...` are ignored
- structured extraction is text-first, not crop-first
- two simple table modes are supported:
  - parameter/value tables
  - axis-column tables such as `X-axis / Y-axis / Z-axis`

If structured extraction succeeds, the table is saved as:

- `bundle/tables/table_001.json`

If structured extraction fails but a valid caption candidate exists, fallback evidence is still saved as:

- `bundle/tables/table_XXX/caption.txt`
- `bundle/tables/table_XXX/context.txt`
- `bundle/tables/table_XXX/crop.png`
- `bundle/tables/table_XXX/table.json`

This prevents silent loss of table evidence and keeps later review possible.

#### Parse report

`bundle/parse_report.json` records the parsing outcome and includes detailed counters such as:

- table caption candidates found
- deduplicated table candidates
- structured tables extracted
- fallback-only tables
- validation rejects
- extracted images
- warnings

### 3. Index Stage

After parsing, the project can build indexes under:

- `runs/<run_id>/indexes/`

The index stage currently creates:

- `indexes/bm25/`
- `indexes/faiss/`
- `indexes/graph.json`
- `indexes/index_report.json`
- `indexes/index_config.json`

The config used for indexing is persisted so retrieval can later reproduce the same behavior.

### 4. Unified Evidence Items

Indexing and retrieval are driven by one internal evidence-item representation. Each item has a stable shape with fields such as:

- `evidence_id`
- `source_type`
- `source_id`
- `page_number`
- `text`
- `snippet`
- `metadata`

This matters because BM25, FAISS, graph generation, diagnostics, and later extraction logic all operate over the same atomic evidence units.

Current evidence sources are:

- sections from `sections.json`
- structured and fallback tables
- figures from caption/context
- chunks derived from `fulltext.md`

### 5. Fulltext Chunking

The retrieval pipeline now supports configurable chunking modes.

#### Legacy mode

- `fixed` chunking is still available for experiments and backward comparison

#### Current default

- `paragraph` chunking is now the default retrieval baseline
- fulltext is split by blank-line Markdown blocks
- very short paragraph candidates are merged
- long paragraphs are split conservatively while preserving paragraph semantics
- adjacent chunks can overlap
- default overlap is `15%`

Chunk metadata preserves useful local information where practical, including:

- `chunk_id`
- `paragraph_id`
- `paragraph_index`
- `chunk_index_within_paragraph`
- `source="fulltext.md"`
- `chunking_mode`
- local character offsets
- page number when recoverable heuristically

This was added because paragraph-first chunks expose extraction-ready evidence more cleanly than the earlier fixed chunking.

### 6. BM25 Index

The lexical index is built over the evidence items and persisted as inspectable artifacts:

- `indexes/bm25/evidence_items.json`
- `indexes/bm25/bm25_stats.json`

The implementation remains deliberately simple:

- local tokenization
- BM25-style scoring
- explicit saved statistics

This keeps debugging straightforward.

### 7. Dense Index

The dense index is also built over the same evidence items and persisted as:

- `indexes/faiss/index.faiss`
- `indexes/faiss/evidence_items.json`
- `indexes/faiss/embedding_meta.json`

The dense backend is now swappable.

#### Supported backends

- `hash`
- `sentence_transformer`

The current default backend is:

- `sentence-transformers/all-MiniLM-L6-v2`

`embedding_meta.json` records:

- backend name
- model name
- embedding dimension
- index build timestamp

The older deterministic hash backend is still supported for fallback and controlled comparison. The sentence-transformer backend is now the default because it improved retrieval quality while preserving local inspectability.

### 8. Structural Graph

`indexes/graph.json` stores a lightweight deterministic graph. It is not a full GraphRAG system.

It currently models relationships such as:

- section -> table
- section -> figure
- table -> caption/content
- figure -> caption/context

The goal is to preserve local structure in a minimal, inspectable form.

### 9. Retrieval Layer

The retrieval interface is implemented in `mvp.retrieval` and currently exposes:

- `search_text(query, top_k=5)`
- `search_tables(query, top_k=5)`
- `search_figures(query, top_k=5)`
- `get_section(section_id)`
- `get_table(table_id)`
- `get_figure(figure_id)`

Retrieval remains field-oriented:

- `search_text` searches section and chunk evidence
- `search_tables` searches table evidence
- `search_figures` searches figure caption/context evidence

This avoids flattening the whole article into one document and makes the system more suitable for later field-by-field extraction.

### 10. Hybrid Fusion

The retrieval layer supports two fusion modes:

- `weighted`
- `rrf`

Weighted fusion remains available and is now the default. It combines:

- normalized BM25 score
- normalized dense score

using:

- `weighted_alpha = 0.7`
- `weighted_beta = 0.3`

RRF is still available for experiments through config, but it is not the default baseline.

### 11. Retrieval Diagnostics

Per-result diagnostics are now exposed and can be persisted for auditability. Returned results can include:

- `bm25_score`
- `dense_score`
- `weighted_score` or `rrf_score`
- `bm25_rank`
- `dense_rank`
- `final_rank`
- `fusion_strategy`
- `chunking_mode`
- `embedding_backend`

This makes retrieval comparisons explicit instead of opaque.

### 12. Benchmarking And Experimentation

The repository now has a small benchmark runner that can execute named retrieval configurations on the sample article and write Markdown reports into `docs/`.

Benchmark presets include:

- `baseline_current`
- `paragraph_only`
- `paragraph_rrf`
- `paragraph_real_embedding`
- `paragraph_real_embedding_rrf`

The generated docs currently include:

- per-configuration retrieval reports
- a comparison summary
- a default-baseline confirmation report

This was added so retrieval improvements can be evaluated incrementally and not hardwired blindly.

## Current Default Retrieval Baseline

The current default retrieval behavior is:

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

This became the default because:

- paragraph chunking gave cleaner evidence units than fixed chunking
- weighted fusion surfaced more extraction-ready evidence than RRF on the benchmark
- the sentence-transformer backend improved technical retrieval quality
- on the sample article, the query `substrate material` surfaces explicit `Rogers RT5880` evidence at rank 1 under this default

## Why The System Is Structured This Way

The current implementation is shaped around a specific MVP objective: make the article evidence stable, local, inspectable, and retrieval-ready before introducing any extraction agent.

The main reasons for the current design are:

- **Auditability:** important processing steps write artifacts that can be inspected directly on disk
- **Determinism:** parsing, chunking, indexing, and reporting are kept stable and configuration-driven
- **Field-oriented retrieval:** later extraction will need targeted evidence such as substrate, dimensions, feed type, impedance, or bandwidth, not just a generic article summary
- **Controlled experimentation:** chunking, embeddings, and fusion can be changed independently without redesigning the pipeline
- **Low complexity:** the code avoids framework-heavy abstractions and keeps the data flow readable
- **Swapability:** embedding backends and fusion logic can evolve without breaking bundle artifacts or the retrieval interface

## What Is Not Implemented Yet

The following remain intentionally out of scope at this stage:

- extraction agents
- structured field output
- CST logic
- optimization
- orchestration beyond the local single-run workflow

## Current Result

At this point, the project has a usable local pipeline for:

1. ingesting a paper
2. parsing it into a stable bundle
3. indexing bundle evidence
4. retrieving field-oriented evidence with configurable lexical and dense search
5. benchmarking retrieval configurations and documenting the results

That gives a solid foundation for the next sprint, which can focus on field-by-field extraction on top of the existing bundle and retrieval layers.
