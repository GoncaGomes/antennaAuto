# MVP Implementation Summary

## Goal

This repository is currently implementing a small, inspectable pipeline for working with a single antenna-paper PDF per run. The design is intentionally conservative:

- deterministic ingestion
- deterministic parsing
- inspectable bundle artifacts
- local indexing
- local retrieval over evidence units

The project is **not** trying to solve the full extraction problem yet. It is building the substrate that later extraction logic can rely on.

## What Is Implemented

### 1. Ingestion

The ingestion stage accepts a PDF path, validates it, creates a new run folder, and copies the source article into the run as:

- `runs/<run_id>/input/article.pdf`

It also creates the expected bundle folders:

- `bundle/`
- `bundle/tables/`
- `bundle/figures/`

The run metadata is saved to `bundle/metadata.json`, including:

- run id
- original path and filename
- file size
- SHA-256
- timestamp
- page count
- PDF metadata from PyMuPDF

### 2. Deterministic Parsing

The parsing stage builds a stable article bundle under `bundle/`.

#### Full text

- `pymupdf4llm` is used to extract the article into `bundle/fulltext.md`

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

The figure captions and context are still heuristic, but the bundle preserves enough local evidence for later use.

#### Tables

The table stage was refined to be conservative.

- caption detection is strict and line-based
- inline paragraph mentions like `... shown in Table 2 ...` are ignored
- table parsing is text-first, not crop-first
- two simple table modes are supported:
  - parameter/value tables
  - axis-column tables such as `X-axis / Y-axis / Z-axis`

If structured extraction succeeds, a table is saved as:

- `bundle/tables/table_001.json`

If structured extraction fails but a real caption candidate exists, fallback evidence is saved as:

- `bundle/tables/table_XXX/caption.txt`
- `bundle/tables/table_XXX/context.txt`
- `bundle/tables/table_XXX/crop.png`
- `bundle/tables/table_XXX/table.json`

This keeps the parser auditable and prevents silent loss of table evidence.

#### Parse report

`bundle/parse_report.json` records the parsing outcome and includes detailed table-related counters such as:

- caption candidates found
- deduplicated candidates
- structured tables extracted
- fallback-only tables
- validation rejects

### 3. INDEX Stage

After parsing, the project can build indexes under:

- `runs/<run_id>/indexes/`

The index stage currently creates:

- `indexes/bm25/`
- `indexes/faiss/`
- `indexes/graph.json`
- `indexes/index_report.json`

### 4. Unified Evidence Items

Indexing is driven by a single internal evidence-item representation. Each item has a stable shape with fields such as:

- `evidence_id`
- `source_type`
- `source_id`
- `page_number`
- `text`
- `snippet`
- `metadata`

This is important because it gives BM25, FAISS, and later extraction logic the same atomic evidence units.

Current evidence sources:

- sections from `sections.json`
- structured and fallback tables
- figures from caption/context
- chunks derived from `fulltext.md`

### 5. BM25 Index

The lexical index is built over the evidence items and persisted as inspectable artifacts:

- `indexes/bm25/evidence_items.json`
- `indexes/bm25/bm25_stats.json`

The implementation is deliberately simple:

- local tokenization
- BM25-style scoring
- explicit saved statistics

This makes debugging retrieval behavior straightforward.

### 6. FAISS Index

The dense index is also built over the same evidence items and persisted as:

- `indexes/faiss/index.faiss`
- `indexes/faiss/evidence_items.json`
- `indexes/faiss/embedding_meta.json`

The current embedding backend is intentionally lightweight and local:

- deterministic hash-based embeddings
- FAISS inner-product search

This is not meant to be the final semantic retrieval solution. It is a simple local dense layer that can be swapped later without changing the rest of the retrieval interface.

### 7. Structural Graph

`indexes/graph.json` stores a lightweight deterministic graph. It is not a full GraphRAG system.

It currently models relationships such as:

- section -> table
- section -> figure
- figure -> caption/context
- table -> caption/content

The goal is to preserve article structure in a minimal inspectable form.

### 8. Retrieval Layer

The retrieval interface is implemented in `mvp.retrieval` and currently exposes:

- `search_text(query, top_k=5)`
- `search_tables(query, top_k=5)`
- `search_figures(query, top_k=5)`
- `get_section(section_id)`
- `get_table(table_id)`
- `get_figure(figure_id)`

Retrieval uses a simple hybrid strategy:

- BM25 score
- FAISS score
- normalized weighted combination

This keeps searches field-oriented instead of flattening the entire article into one giant document.

## Why This Structure

The current implementation is shaped around a specific MVP objective: make the article evidence stable, local, and inspectable before introducing any extraction agent.

The main reasons for the current design are:

- **Auditability:** every important step writes artifacts that can be inspected directly on disk
- **Determinism:** the parser and indexer are based on fixed heuristics and local processing
- **Field-oriented retrieval:** later extraction will need targeted evidence like dimensions, substrate, feed type, or solver setup, not just a generic article summary
- **Low complexity:** the code avoids framework-heavy abstractions and keeps the data flow easy to inspect
- **Swapability:** the dense embedding backend can change later without forcing a redesign of bundle artifacts or retrieval functions

## What Is Not Implemented Yet

The following are intentionally out of scope at this stage:

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
4. retrieving relevant local evidence by query

That gives a solid foundation for the next sprint, which can focus on field-by-field extraction on top of the existing bundle and retrieval layers.
