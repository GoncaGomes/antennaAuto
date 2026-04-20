# Implemented So Far

Last updated:
- `2026-04-20`

## Purpose Of This Document

This document is the current ground-truth project snapshot for the repository.

It is written so that another engineer or another LLM can understand:
- what the repository does
- what the current runtime architecture is
- what artifacts are produced at each stage
- which code paths are authoritative today
- what has already been changed from the older design
- what is currently working
- what is currently failing
- where the main technical risks and next-change targets are

This document describes the project as it is currently implemented in code, not as an intended future design.

---

## Repository Identity

Repository path:
- `C:\Users\Lenovo\SynologyDrive\PhD\02.antennaAuto`

Project type:
- local, auditable MVP extraction pipeline for antenna papers

Primary goal:
- take one antenna paper PDF
- parse it into local artifacts
- index the evidence deterministically
- run a lightweight Phase 1 interpretation step
- run a second retrieval pass guided by Phase 1
- run a multistage LLM extraction path
- write a strict final `antenna_architecture_spec_mvp_v2.json`

The project is intentionally bounded.
It is not trying to be a general autonomous research agent.

Out of scope for the current implementation:
- OCR
- multimodal vision extraction from raw images
- CST script generation
- simulation setup generation
- optimization loops
- free-form model browsing/tool use
- production orchestration

---

## Current End-To-End Architecture

The current default runtime flow is:

1. ingest one PDF into a run folder
2. parse the PDF into bundle artifacts
3. build deterministic local indexes over unified evidence items
4. run Phase 1 discovery to write `paper_map.json`
5. run Phase 1 LLM planning to write `interpretation_map.json`
6. run deterministic retrieval round 2 using the existing block plan plus Phase 1 search queries
7. run LLM2 canonicalization to write `canonical_design_record.json`
8. run LLM3 schema construction to write `antenna_architecture_spec_mvp_v2.json`
9. run minimal deterministic cleanup and validation
10. write `phase2_retrieval_context.json` and `extraction_run_report.json`

The current default extraction path is:
- `retrieval -> LLM2 -> LLM3`

The older direct single-call extraction path:
- still exists
- is isolated behind an explicit legacy flag
- is not the default runtime path

---

## High-Level Mental Model

A compact mental model of the repository is:

- the pipeline first turns the PDF into deterministic local evidence
- Phase 1 does paper-level understanding and retrieval planning, not final extraction
- the extraction stage then performs a second retrieval pass using both its base block plan and Phase 1 guidance
- LLM2 decides what the dominant design is and writes a canonical design record
- LLM3 converts that canonical design record into the final strict schema
- after LLM3, the code performs only minimal cleanup and integrity validation

The intended semantic center of gravity is now LLM2 plus LLM3, not deterministic semantic rebinding code.

---

## Top-Level Repository Layout

Important folders:

- `data/raw/`
  - source PDFs used for validation and development
- `runs/`
  - self-contained run folders, one per paper/run
- `docs/`
  - project documentation and audit notes
- `src/mvp/`
  - runtime code
- `tests/`
  - unit and integration tests
- `scripts/`
  - helper scripts

Main runtime modules:

- `src/mvp/cli.py`
  - ingestion/parsing/indexing entrypoint
- `src/mvp/extract.py`
  - Phase 1-only or extraction entrypoint for an existing run
- `src/mvp/pipeline.py`
  - ingest/parse orchestration
- `src/mvp/bundle.py`
  - run-folder creation and path resolution
- `src/mvp/parsers.py`
  - Docling-first PDF parsing into a structured page-object IR, then bundle exports
- `src/mvp/index.py`
  - evidence construction and retrieval index building
- `src/mvp/retrieval.py`
  - unified retrieval surface
- `src/mvp/llm/client.py`
  - OpenAI Structured Outputs client and OpenAI Agents SDK client

Phase 1 modules:

- `src/mvp/interpretation/discovery.py`
  - deterministic `paper_map` construction
- `src/mvp/interpretation/prompting.py`
  - LLM1 prompt construction
- `src/mvp/interpretation/pipeline.py`
  - Phase 1 orchestration
- `src/mvp/schemas/paper_map.py`
  - strict `PaperMap` schema
- `src/mvp/schemas/interpretation_map.py`
  - strict `InterpretationMap` schema

Extraction modules:

- `src/mvp/extraction/agent.py`
  - deterministic retrieval-by-block plan plus Phase 1 query augmentation
- `src/mvp/extraction/prompting.py`
  - LLM2 and LLM3 multistage prompt builders
- `src/mvp/extraction/legacy/prompting.py`
  - isolated legacy direct-extraction prompt builders and prompt-budget rules
- `src/mvp/extraction/pipeline.py`
  - current default multistage extraction path and isolated legacy path
- `src/mvp/schemas/canonical_design_record.py`
  - strict schema for the LLM2 canonical record
- `src/mvp/schemas/extraction_spec.py`
  - strict final `antenna_architecture_spec_mvp_v2` schema and validation

---

## Run Folder Structure

Every processed paper lives in:
- `runs/<run_id>/`

Current run layout:

- `input/`
  - original PDF copied into the run
- `bundle/`
  - parsed text, section, figure, and table artifacts
- `indexes/`
  - BM25, dense, graph, and retrieval config artifacts
- `outputs/`
  - Phase 1 outputs, Phase 2 artifact, canonical record, final spec, and extraction report

Important bundle artifacts:

- `bundle/metadata.json`
- `bundle/fulltext.md`
- `bundle/sections.json`
- `bundle/page_objects.json`
- `bundle/parse_report.json`
- `bundle/figures/*.png`
- `bundle/tables/table_XXX.md`

Important index artifacts:

- `indexes/bm25/evidence_items.json`
- `indexes/faiss/index.faiss`
- `indexes/index_config.json`
- `indexes/index_report.json`
- `indexes/graph.json`

Important output artifacts:

- `outputs/paper_map.json`
- `outputs/interpretation_map.json`
- `outputs/canonical_design_record.json`
- `outputs/phase2_retrieval_context.json`
- `outputs/antenna_architecture_spec_mvp_v2.json`
- `outputs/extraction_run_report.json`

---

## Evidence Model

The whole system operates on unified evidence items, not directly on raw source files.

Indexed evidence items carry fields such as:
- `evidence_id`
- `source_type`
- `source_id`
- `page_number`
- `text`
- `snippet`
- `metadata`
- `source_payload`

Current evidence source types include:
- `chunk`
- `section`
- `table`
- `figure`

Evidence IDs are critical.
They are used throughout retrieval, prompt building, canonicalization, final schema generation, and validation.

Current evidence-ID style examples:
- `chunk:chunk_028`
- `section:page_003`
- `table:table_001`
- `figure:fig_005`

The pipeline expects evidence IDs to keep this prefixed form.

---

## Deterministic Ingest / Parse / Index Stages

### 1. Ingest

Main code areas:
- `src/mvp/cli.py`
- `src/mvp/pipeline.py`
- `src/mvp/bundle.py`

Behavior:
- create a new run folder
- copy the input PDF into the run
- write base metadata

### 2. Parse

Main code area:
- `src/mvp/parsers.py`

Behavior:
- use Docling as the primary layout-aware PDF parser
- produce a normalized per-page object IR in `page_objects.json`
- derive `fulltext.md` from ordered non-noise page objects
- derive `sections.json` from heading objects while preserving the exact lean shape
- export figure PNG artifacts under `bundle/figures/`
- export table markdown artifacts under `bundle/tables/`
- write parser diagnostics and table/figure summaries into `parse_report.json`
- optionally use GROBID only when `MVP_GROBID_URL` is set

Current properties:
- deterministic
- PDF-native
- no OCR
- no vision model
- no `pdfplumber` parser path
- no parser-stage LLM calls
- GROBID is enrichment-only and parsing succeeds without it

### 3. Index

Main code areas:
- `src/mvp/index.py`
- `src/mvp/retrieval.py`

Behavior:
- build BM25 artifacts
- build dense retrieval artifacts
- build lightweight graph artifacts
- persist index configuration

Current retrieval defaults include:
- paragraph chunking
- MiniLM dense embeddings
- weighted fusion for general retrieval

---

## Phase 1

## Purpose

Phase 1 is a bounded paper-understanding and retrieval-planning stage.
It does not fill the final architecture schema.

Phase 1 produces:
- `paper_map.json`
- `interpretation_map.json`

Main code path:
- `src/mvp/interpretation/pipeline.py::run_phase1`

### `paper_map.json`

This is deterministic and validated by `PaperMap`.

Current top-level fields:
- `title`
- `abstract`
- `section_headings_top_level`
- `key_design_signals`
- `candidate_design_mentions`
- `key_table_refs`
- `key_figure_refs`

Main builder:
- `src/mvp/interpretation/discovery.py::build_paper_map`

### `candidate_design_mentions`

This is the most important dynamic field inside `paper_map`.

Current discovery behavior:
- uses deterministic seed buckets
- retrieves through `BundleRetriever.search_text(...)`
- uses local RRF only for this discovery pass
- uses `top_k = 5` per seed
- preserves retrieval `score`
- only hard-rejects:
  - missing `evidence_id`
  - empty cleaned text
  - obvious reference/bibliography junk
- no longer hard-rejects organization snippets
- no longer hard-rejects based on bucket-scope gating
- merges primarily by `evidence_id`
- secondarily dedupes only by exact normalized full-text equality
- per-bucket sort is retrieval-led:
  - retrieval `score` descending
  - `evidence_id` stable tie-break
- per-bucket cap: `3`
- global cap: `9`

Current limitation:
- `candidate_design_mentions` are still text-retrieval-led and do not directly search figure or table evidence for that field.

### `interpretation_map.json`

This is the only LLM-generated Phase 1 artifact.

Current schema fields:
- `has_multiple_variants`
- `has_final_design_signal`
- `search_queries`
- `open_uncertainties`

Main code areas:
- `src/mvp/interpretation/prompting.py`
- `src/mvp/interpretation/pipeline.py`

Current Phase 1 model:
- `gpt-5.4-mini`

Current Phase 1 role:
- retrieval planner only
- not final schema extraction
- not canonicalization
- not tool-using

---

## Retrieval Round 2

## Purpose

The second retrieval pass is still deterministic and block-based.
It is not free-form retrieval.

Main code area:
- `src/mvp/extraction/agent.py`

The extraction retriever keeps its base plan and augments that plan with:
- `interpretation_map.search_queries`

Current extraction blocks:
- `classification`
- `materials`
- `layers`
- `parameters`
- `entities`
- `feeds`
- `quality`

Current behavior per block:
1. execute the existing base-plan queries
2. additionally execute Phase 1 search queries
3. merge retrieval results
4. dedupe by `evidence_id`
5. preserve retrieval provenance into the Phase 2 artifact
6. feed the merged evidence surface into LLM2

Important point:
- retrieval round 2 is not itself deciding which design stage is final
- it is just constructing a richer evidence surface

---

## Current Default Extraction Path

Main code entrypoint:
- `src/mvp/extract.py`

Default CLI path:
- `uv run python -m mvp.extract --run-dir runs/<run_id>`

Current default extraction function:
- `src/mvp/extraction/pipeline.py::extract_run`

Current default branch:
- `src/mvp/extraction/pipeline.py::_extract_run_multistage`

Legacy direct path:
- `src/mvp/extraction/pipeline.py::_extract_run_legacy_direct`
- enabled only with `--legacy-direct-extraction`

### Current default flow in code

`extract_run(...)` does:
- if `legacy_direct=True`, call legacy direct path
- otherwise call `_extract_run_multistage(...)`

`_extract_run_multistage(...)` does:
1. validate that the run has the required bundle/index inputs
2. load existing Phase 1 guidance if present
3. call `gather_retrieval_context_with_phase1(...)`
4. sort the retrieved evidence for LLM2 input
5. build LLM2 request with `build_canonicalization_input(...)`
6. call the Agents SDK structured client for LLM2
7. validate the returned canonical record and write `canonical_design_record.json`
8. collect linked evidence records from the canonical record’s evidence IDs
9. build LLM3 request with `build_schema_construction_input(...)`
10. call the Agents SDK structured client for LLM3
11. validate the final schema
12. apply minimal cleanup
13. validate again
14. write `phase2_retrieval_context.json`
15. write `antenna_architecture_spec_mvp_v2.json`
16. write `extraction_run_report.json`

---

## LLM2: Canonicalization

## Purpose

LLM2 is the semantic arbitration step.
It does not output the final extraction schema.

Its job is to:
- decide which design in the paper is dominant
- separate dominant design facts from intermediate or secondary material
- preserve important structured facts for downstream schema construction
- keep conflicts explicit when unresolved

### Code path

Prompt builder:
- `src/mvp/extraction/prompting.py::build_canonicalization_input`

Prompt string:
- `src/mvp/extraction/prompting.py::CANONICALIZATION_SYSTEM_PROMPT`

Structured call path:
- `src/mvp/extraction/pipeline.py::_generate_agents_structured`
- `src/mvp/llm/client.py::OpenAIAgentsStructuredClient.generate_structured_via_agent`

Output schema:
- `src/mvp/schemas/canonical_design_record.py::CanonicalDesignRecord`

### Current model configuration

Defined in:
- `src/mvp/extraction/pipeline.py`

Current constants:
- `DEFAULT_LLM2_MODEL = "gpt-5.4-mini"`
- `DEFAULT_AGENTS_REASONING_EFFORT = "medium"`

### LLM2 input contents

Current `build_canonicalization_input(...)` input payload contains:
- `run_context`
- compact Phase 1 guidance
- `retrieved_evidence_by_block`

Important current property:
- tables are preserved more structurally into LLM2 than in the old direct extraction path
- the code does not flatten LLM2 table evidence into the old compact prompt-record format before LLM2 sees it

---

## Current `canonical_design_record.json` Shape

This artifact is the LLM2 output.

Current schema file:
- `src/mvp/schemas/canonical_design_record.py`

Current top-level fields:
- `selected_design_summary`
- `selected_design_rationale`
- `has_multiple_variants`
- `dominant_evidence_ids`
- `secondary_evidence_ids`
- `final_design`
- `design_evolution_notes`
- `unresolved_conflicts`

Current `final_design` fields:
- `classification`
- `patch`
- `feed`
- `ground`
- `slots`
- `materials`
- `layers`
- `performance_targets`
- `extra_parameters`

### `final_design.classification`

Fields:
- `primary_family`
- `topology_tags`

### `final_design.patch`

Type:
- `CanonicalComponent`

Fields:
- `label`
- `shape_mode`
- `dimensions`
- `material_name`
- `layer_role`
- `evidence_ids`

### `final_design.feed`

Type:
- `CanonicalFeed`

Fields:
- `feed_family`
- `matching_style`
- `driven_target`
- `dimensions`
- `location`
- `evidence_ids`

### `final_design.ground`

Type:
- `CanonicalComponent`

Fields:
- `label`
- `shape_mode`
- `dimensions`
- `material_name`
- `layer_role`
- `evidence_ids`

### `final_design.slots`

Type:
- list of `CanonicalComponent`

### `final_design.materials`

Type:
- list of `CanonicalMaterial`

Fields:
- `name`
- `category`
- `roles`
- `evidence_ids`

### `final_design.layers`

Type:
- list of `CanonicalLayer`

Fields:
- `role`
- `material_name`
- `thickness_value`
- `thickness_unit`
- `evidence_ids`

### `final_design.performance_targets`

Type:
- list of `CanonicalMetric`

Fields:
- `name`
- `value`
- `unit`
- `evidence_ids`

### `final_design.extra_parameters`

Type:
- list of `CanonicalParameter`

Fields:
- `semantic_name`
- `symbol`
- `value`
- `unit`
- `target_component`
- `evidence_ids`

### `design_evolution_notes`

Type:
- list of `DesignEvolutionNote`

Fields:
- `label`
- `description`
- `evidence_ids`

### `unresolved_conflicts`

Type:
- list of `CanonicalConflict`

Fields:
- `topic`
- `description`
- `preferred_evidence_ids`
- `conflicting_evidence_ids`
- `status`

### Important canonical-shape detail

The canonical schema was recently changed.
The older shape used top-level fields like:
- `canonical_patch`
- `canonical_feed`
- `canonical_ground`
- `canonical_slots`
- `canonical_materials`
- `canonical_layers`
- `canonical_operating_targets`
- `canonical_parameters`

That is no longer the current shape.
The authoritative current shape is the `final_design` wrapper plus `design_evolution_notes`.

### Evidence ID behavior in the canonical record

Current evidence IDs are preserved on:
- components
- feed
- materials
- layers
- metrics
- extra parameters
- evolution notes
- conflicts
- top-level `dominant_evidence_ids`
- top-level `secondary_evidence_ids`

Current evidence IDs are not carried on:
- `CanonicalDimension`
- `CanonicalLocation`

The canonical schema’s helper `collect_canonical_evidence_ids(...)` recursively collects:
- `evidence_ids`
- `dominant_evidence_ids`
- `secondary_evidence_ids`
- `preferred_evidence_ids`
- `conflicting_evidence_ids`

Those collected IDs are then used to resolve linked evidence for LLM3.

---

## LLM3: Schema Construction

## Purpose

LLM3 is the final schema-construction step.
It does not decide the dominant design from raw mixed retrieval.
It is meant to convert the already-selected canonical design record into the final extraction schema.

### Code path

Prompt builder:
- `src/mvp/extraction/prompting.py::build_schema_construction_input`

Prompt string:
- `src/mvp/extraction/prompting.py::SCHEMA_CONSTRUCTION_SYSTEM_PROMPT`

Structured call path:
- `src/mvp/extraction/pipeline.py::_generate_agents_structured`
- `src/mvp/llm/client.py::OpenAIAgentsStructuredClient.generate_structured_via_agent`

Output schema:
- `src/mvp/schemas/extraction_spec.py::AntennaArchitectureSpecMvpV2`

### Current model configuration

Defined in:
- `src/mvp/extraction/pipeline.py`

Current constants:
- `DEFAULT_LLM3_MODEL = "gpt-5.4-mini"`
- `DEFAULT_AGENTS_REASONING_EFFORT = "medium"`

### LLM3 input contents

Current `build_schema_construction_input(...)` payload contains:
- `run_context`
- `canonical_design_record`
- `linked_evidence_records`

### How linked evidence is built

Main code area:
- `src/mvp/extraction/pipeline.py::_build_linked_evidence_records`

Behavior:
- collect evidence IDs from the canonical record
- resolve those evidence IDs back to the retrieved evidence records
- pass the matched records forward into LLM3

So LLM3 receives:
- the canonical record itself
- a resolved subset of the original retrieval surface, filtered to only evidence explicitly referenced by the canonical record

---

## Minimal Deterministic Cleanup And Validation

After LLM3, the current default path keeps only minimal deterministic processing.

Main code areas:
- `src/mvp/extraction/pipeline.py::_validate_canonical_generation`
- `src/mvp/extraction/pipeline.py::_validate_generation`
- `src/mvp/extraction/pipeline.py::_apply_minimal_cleanup`

Current behavior that remains:
- strict Pydantic validation for `CanonicalDesignRecord`
- strict Pydantic validation for `AntennaArchitectureSpecMvpV2`
- evidence ID integrity checks against retrieval
- nested evidence ID integrity checks against retrieval
- exact `evidence_used` dedupe
- exact duplicate parameter dedupe
- unit literal normalization

Important current non-behavior:
- the new default path is not relying on the older semantic rebinding / semantic rescue layer as its main interpretation mechanism

---

## Legacy Direct Path

The older direct single-call schema extraction path still exists for compatibility.

Main code areas:
- `src/mvp/extract.py`
- `src/mvp/extraction/pipeline.py::_extract_run_legacy_direct`

CLI flag:
- `--legacy-direct-extraction`

Legacy model default:
- `gpt-4o`

Important note:
- this path is not the default
- the main active architecture is the multistage `retrieval_llm2_llm3` path

---

## Current CLI Surface

Prepare a run:

```powershell
uv run python -m mvp.cli --input data/raw/paper_001/article.pdf --index
```

Run Phase 1 only:

```powershell
uv run python -m mvp.extract --run-dir runs/<run_id> --phase1-only
```

Run the current default multistage extraction path:

```powershell
uv run python -m mvp.extract --run-dir runs/<run_id>
```

Run the isolated legacy direct path:

```powershell
uv run python -m mvp.extract --run-dir runs/<run_id> --legacy-direct-extraction --model gpt-4o
```

Phase 1 validation helper:

```powershell
uv run python scripts/run_phase1_validation.py
```

---

## Current Phase 2 Audit Artifact

Artifact:
- `outputs/phase2_retrieval_context.json`

Current recorded fields include:
- `phase1_guidance_found`
- `phase1_interpretation_map_path`
- `phase1_search_queries_used`
- `retrieval_queries_executed_per_block`
- `retrieved_evidence_ids_per_block`
- `llm2_input_evidence_ids_per_block`
- `canonical_design_record_path`
- `llm2_model_name`
- `llm3_model_name`
- `llm2_reasoning_effort`
- `llm3_reasoning_effort`
- `default_path_replaced_old_single_call`
- `legacy_direct_path_available`
- `legacy_direct_path_used`
- `legacy_model_name`
- `extraction_path`

This file is the main compact audit artifact for the retrieval-to-LLM2 handoff.

---

## Current Extraction Report

Artifact:
- `outputs/extraction_run_report.json`

Current report records include:
- `run_id`
- `timestamp_utc`
- `model_name`
- `llm2_model_name`
- `llm3_model_name`
- `llm2_reasoning_effort`
- `llm3_reasoning_effort`
- `canonical_design_record_path`
- `extraction_path`
- `old_single_gpt4o_path_replaced`
- `legacy_direct_path_available`
- `legacy_direct_path_used`
- `legacy_model_name`
- `extraction_status`
- `retrieval_queries_used`
- `evidence_ids_retrieved_per_block`
- `final_evidence_ids_used`
- `validation_success`
- `schema_errors`
- `warnings`
- `attempt_count`
- `prompt_evidence_ids_per_block`
- `query_usefulness_per_block`
- `prompt_budget`
- optional embedded `phase1` section

---

## Current Prompting State

Main multistage prompt builder file:
- `src/mvp/extraction/prompting.py`

External prompt text files:
- `src/mvp/prompts/canonicalization_system.md`
- `src/mvp/prompts/schema_construction_system.md`
- `src/mvp/prompts/legacy_direct_system.md`

Current multistage prompt-builder functions:
- `build_canonicalization_input(...)`
  - LLM2
- `build_schema_construction_input(...)`
  - LLM3

Legacy direct-extraction prompt file:
- `src/mvp/extraction/legacy/prompting.py`

Current legacy prompt-builder functions:
- `build_extraction_messages(...)`
- `build_repair_messages(...)`

Current prompt design summary:
- LLM2 is told to arbitrate dominant design identity and preserve structurally useful facts
- LLM3 is told to faithfully transfer canonical facts into the final schema without silently dropping canonical geometry/feed/layer/material facts

---

## Current Test State

Recent targeted tests after the canonical-record shape update:

```powershell
uv run python -m pytest -q tests/test_canonical_design_record.py tests/test_extraction_prompting.py tests/test_extraction_pipeline.py
```

Result:
- `14 passed, 3 warnings`

These tests currently cover:
- canonical schema validation
- canonical prompt/input building
- default multistage extraction wiring
- report/artifact writing behavior tied to the multistage path

Earlier focused extraction validation also passed for:
- prompt builders
- CLI routing
- LLM client configuration
- default-path wiring

---

## Current Validation Runs

These are the current latest reference runs after the canonical-record shape change.

### 1. `paper_001/article.pdf`

Run:
- `runs/run_20260414T171322129447Z`

Status:
- Phase 1: completed
- extraction path: `retrieval_llm2_llm3`
- validation success: `true`
- LLM2: `gpt-5.4-mini`, `medium`
- LLM3: `gpt-5.4-mini`, `medium`

Outputs:
- `paper_map.json`
- `interpretation_map.json`
- `canonical_design_record.json`
- `phase2_retrieval_context.json`
- `antenna_architecture_spec_mvp_v2.json`
- `extraction_run_report.json`

### 2. `paper_002/engproc-46-00010.pdf`

Run:
- `runs/run_20260414T171710649495Z`

Status:
- Phase 1: completed
- extraction path: `retrieval_llm2_llm3`
- validation success: `true`
- LLM2: `gpt-5.4-mini`, `medium`
- LLM3: `gpt-5.4-mini`, `medium`

Outputs:
- `paper_map.json`
- `interpretation_map.json`
- `canonical_design_record.json`
- `phase2_retrieval_context.json`
- `antenna_architecture_spec_mvp_v2.json`
- `extraction_run_report.json`

### 3. `paper_003/IJETT-V4I4P340.pdf`

Run:
- `runs/run_20260414T172032791688Z`

Status:
- Phase 1: completed
- extraction path: `retrieval_llm2_llm3`
- validation success: `false`
- extraction status: `failed_llm3_schema_extraction`
- LLM2: `gpt-5.4-mini`, `medium`
- LLM3: `gpt-5.4-mini`, `medium`

Outputs present:
- `paper_map.json`
- `interpretation_map.json`
- `canonical_design_record.json`
- `phase2_retrieval_context.json`
- `extraction_run_report.json`

Current failure point:
- LLM2 succeeded
- failure occurs during LLM3 final-schema validation

---

## Current Solution State

The current implemented solution is:

- deterministic ingest, parse, and index layers are in place
- Phase 1 is in place and producing `paper_map.json` and `interpretation_map.json`
- second-stage deterministic retrieval with Phase 1 query augmentation is in place
- LLM2 canonicalization is in place and writing `canonical_design_record.json`
- LLM3 schema construction is in place and writing the final schema when validation succeeds
- the default path now uses explicit multistage extraction instead of the old direct single-call path
- both LLM2 and LLM3 are explicitly configured to:
  - `gpt-5.4-mini`
  - reasoning effort `medium`
- a compact Phase 2 retrieval audit artifact is in place
- minimal deterministic cleanup and validation remain in place

In practical terms, the current system can already complete end-to-end multistage extraction successfully on at least two of the three current validation papers after the canonical-record shape update.

---

## Current Problems

This section documents the main currently observed problems in the current code and current latest validation runs.

### Problem 1: LLM3 can still emit invalid evidence IDs

Current concrete failure:
- the latest `IJETT` run failed in LLM3 validation
- the failure is not retrieval and not LLM2
- LLM3 generated evidence IDs like:
  - `chunk_001`
  - `page_001`
- but the schema expects prefixed evidence IDs like:
  - `chunk:chunk_001`
  - `section:page_001`

Observed result in the report:
- `failed_llm3_schema_extraction`
- `29` schema validation errors
- the errors occur across:
  - `classification.evidence_ids`
  - `units.*.evidence_ids`
  - `parameters[*].evidence_ids`
  - `materials[*].evidence_ids`
  - `layers[*].evidence_ids`
  - `entities[*].evidence_ids`
  - `feeds[*].evidence_ids`
  - `evidence_used`

This is currently the most concrete blocking issue in the multistage path.

### Problem 2: Intermediate design-evolution facts can still leak into the canonical final-design record

Current structural reason:
- retrieval round 2 mixes dominant, intermediate, and secondary evidence into the same per-block evidence lists
- LLM2 is responsible for separating final dominant design from intermediate or secondary evidence
- the canonical schema now has `design_evolution_notes`, which helps, but `final_design` can still absorb facts from intermediate steps if LLM2 does not separate them cleanly

Current most likely failure area:
- LLM2 prompt/contract
- not retrieval ranking alone
- not minimal cleanup code

### Problem 3: Final schema fidelity still depends on LLM3 not silently dropping or distorting canonical details

This is improved relative to the older direct path, but still a real risk.

Current sensitive areas include:
- feed coordinates
- slot geometry
- patch dimensions
- ground-plane dimensions
- layer/material assignments
- carrying all nested evidence IDs into `evidence_used`

### Problem 4: Some legacy prompt-compaction and scoring code still exists in the repository

Examples in `src/mvp/extraction/prompting.py`:
- `prepare_prompt_evidence(...)`
- `_prompt_priority_score(...)`

Current state:
- these are still present for the isolated legacy path
- they are not the authoritative default multistage path
- but they remain in the codebase and can still confuse readers because both the legacy and multistage architectures coexist in the same module

### Problem 5: Some heuristics remain upstream of the multistage extraction path

Examples:
- Phase 1 title extraction can still be noisy
- figure-role guessing remains heuristic
- table extraction is still dependent on parser success and fallback quality
- `candidate_design_mentions` remain text-led

These are not new failures, but they remain part of the project’s current limitations.

---

## Current Strengths

The current system’s strongest properties are:

- local, auditable run-folder architecture
- deterministic upstream ingest/parse/index/retrieval behavior
- explicit Phase 1 planning layer
- explicit LLM2 canonicalization layer
- explicit LLM3 schema-construction layer
- strict schema validation
- strong evidence provenance expectations
- explicit Phase 2 audit artifact
- ability to inspect intermediate outputs directly

The addition of `canonical_design_record.json` is especially important because it gives a visible semantic checkpoint between retrieval and final schema generation.

---

## Current Weaknesses / Risks

The current main technical risks are:

- LLM3 evidence-ID formatting drift can still break the final schema
- iterative papers still stress canonicalization because intermediate variants and final variants are mixed in retrieval
- table-vs-prose conflict handling is improved conceptually but still model-dependent
- evidence provenance remains strict, which is good, but brittle if the model emits near-valid IDs instead of exact IDs
- the coexistence of the legacy path and the multistage path increases codebase complexity even though the default runtime path is already settled

---

## Most Important Current Artifacts For Debugging

If a future engineer or LLM needs to inspect a run, the most important files are:

1. `outputs/paper_map.json`
   - deterministic Phase 1 paper view
2. `outputs/interpretation_map.json`
   - Phase 1 search/planning output
3. `outputs/phase2_retrieval_context.json`
   - exact retrieval round 2 audit artifact
4. `outputs/canonical_design_record.json`
   - semantic canonicalization output
5. `outputs/antenna_architecture_spec_mvp_v2.json`
   - final structured extraction output
6. `outputs/extraction_run_report.json`
   - overall status, schema errors, and evidence-use audit fields

When a run fails after LLM2, the first file to inspect is:
- `outputs/extraction_run_report.json`

When the question is whether the dominant design was chosen correctly, the first files to inspect are:
- `outputs/canonical_design_record.json`
- `outputs/phase2_retrieval_context.json`

---

## Current Recommended Mental Model For Future Changes

If someone reads only one section before changing the code, it should be this one.

Current architecture intent is:
- deterministic code should gather evidence and validate structure
- LLM2 should decide dominant design identity and canonicalize design facts
- LLM3 should faithfully transfer canonical facts into the final schema
- cleanup code should be minimal and should not re-interpret paper meaning

Therefore, when the multistage pipeline fails, the first question should be:
- is the failure in retrieval
- in LLM2 canonicalization
- in LLM3 transfer
- or in strict validation/integrity checks

The current latest failure on `IJETT` is clearly in:
- LLM3 output validation
- specifically evidence-ID formatting

The current likely next generic improvement area for iterative-paper handling is:
- LLM2 canonicalization contract and how it separates `final_design` from `design_evolution_notes`

---

## One-Paragraph Project Summary

This repository is a local, auditable MVP for extracting antenna architecture data from antenna papers. It processes one paper per run folder, parses the PDF into deterministic local evidence artifacts, indexes those artifacts, runs a bounded Phase 1 interpretation layer, performs a second deterministic retrieval pass augmented by Phase 1 search queries, uses LLM2 to canonicalize the dominant design into `canonical_design_record.json`, uses LLM3 to convert that canonical record into the strict final `antenna_architecture_spec_mvp_v2.json`, then runs minimal deterministic cleanup and validation. The default extraction path now uses `gpt-5.4-mini` with reasoning effort `medium` for both LLM2 and LLM3. The current system is working end-to-end on two of the three latest validation papers after the canonical-record shape update, while the main current blocking issue is that LLM3 can still emit invalid evidence IDs in the final schema for the `IJETT` paper.

---

## Addendum 2026-04-15: Exact Prompt Texts, Exact Deterministic Rules, And Latest Validation State

This addendum supersedes any earlier section in this document where there is a conflict about:
- latest validation status
- exact prompt text
- exact deterministic rule behavior
- the current interpretation of the IJETT failure mode

### Latest validation-state correction

The earlier section of this document that described the latest `IJETT` run as failed is now out of date.

Current latest status after a clean rerun:
- `paper_001/article.pdf`
  - `runs/run_20260414T171322129447Z`
  - completed
  - `validation_success = true`
- `paper_002/engproc-46-00010.pdf`
  - `runs/run_20260414T171710649495Z`
  - completed
  - `validation_success = true`
- `paper_003/IJETT-V4I4P340.pdf`
  - latest successful rerun: `runs/run_20260414T183441721436Z`
  - completed
  - `validation_success = true`

Important historical note:
- an earlier `IJETT` run, `runs/run_20260414T172032791688Z`, failed during LLM3 validation because the model emitted malformed evidence IDs such as `chunk_001` instead of `chunk:chunk_001`
- that failure is still a real observed failure mode and should be treated as a stability risk, but it is not the current latest run status

### Exact implemented Phase 1 prompt texts

Prompt file:
- `src/mvp/interpretation/prompting.py`

#### LLM1 system prompt

```text
You are an antenna-paper retrieval planner.

You will receive a lightweight paper_map.json.

Your job is only to decide what should be searched next.

You are not summarizing the paper.
You are not extracting the final antenna architecture.
You do NOT execute retrieval.
You do NOT emit tool calls.
You do NOT emit backend-specific commands.

Use only the information in the provided paper_map.json.
Do not invent facts.
If the paper may contain multiple variants, stages, or candidate final designs, preserve that uncertainty.

Search queries must be simple natural-language retrieval queries.
Search queries must be article-targeted.
Search queries must be:
- short
- simple natural-language retrieval queries
- retrieval-friendly
- article-targeted
- phrased with the document's own wording when possible

Prioritize:
1. final / selected / optimized / fabricated design signals
2. variants, stages, or design evolution
3. geometry, feed, or materials only when still unresolved

Discourage generic queries such as fabrication details, simulation results, measured performance, optimization process, or comparison with prior work unless they are directly justified by the paper_map evidence.
```

#### LLM1 user prompt wrapper

```text
You will receive a lightweight paper_map.json for one antenna paper.

Produce the structured interpretation output required by the SDK schema.

Focus on:

whether the paper likely contains multiple variants or stages
whether there are signals of a final / optimized / selected / fabricated design and any supporting measured validation
a small set of useful search queries for deterministic retrieval
unresolved ambiguities that still need evidence

Important constraints:

do not extract the final architecture schema
do not invent facts
do not generate tool calls
do not generate backend-specific retrieval syntax
keep the output simple and operational
prefer 3 to 6 search queries maximum

search_queries must be short
search_queries must be retrieval-friendly
search_queries must be article-targeted
search_queries must use the paper's own wording when possible
search_queries must not be long questions
prioritize final selected design first
then variants, stages, or design evolution
only ask about geometry, feed, or materials if still unresolved
avoid generic queries like fabrication details, simulation results, optimization process, or comparison with existing designs unless directly justified by the paper_map

Here is the paper_map.json:

{paper_map_json}
```

### Exact implemented default-path prompt texts

Prompt builder file:
- `src/mvp/extraction/prompting.py`

External prompt text files:
- `src/mvp/prompts/canonicalization_system.md`
- `src/mvp/prompts/schema_construction_system.md`

#### LLM2 system prompt

```text
You are the semantic canonicalization layer for scientific antenna extraction.

You are NOT building the final schema.

Your task is to read mixed retrieved evidence from one paper and produce a canonical design record for the dominant antenna design described by that paper.

Your goal is not to minimize content. Your goal is to resolve the design identity while preserving all structurally useful facts needed later for schema construction.

You must:
- identify the dominant antenna design target of the paper, if one exists
- distinguish dominant evidence from intermediate design steps, contextual discussion, comparison content, literature comparison, deployment context, and side remarks
- reconcile evidence across prose, tables, figures, and sections
- treat final parameter tables as potentially highly authoritative, but do not apply rigid hard-coded rules
- preserve evidence IDs
- preserve geometrically useful details even when they may later be awkward to map into the final schema
- avoid inventing missing geometry
- avoid copying all evidence blindly
- preserve unresolved ambiguity explicitly instead of guessing

Preserve, whenever supported:
- patch geometry
- slot/notch geometry
- feed geometry
- feed location / coordinates
- ground-plane geometry
- substrate and layer information
- material assignments
- operating targets
- performance metrics
- explicit conflicts between sources

When prose and table content disagree:
- do not resolve the conflict silently
- state which evidence appears more authoritative and why
- preserve the conflict if it is not fully resolved

When multiple design variants exist:
- identify which one is the dominant target of the paper
- mark others as intermediate or secondary
- do not let secondary variants overwrite the dominant design record

Important:
- do not output the final schema
- do not compress away useful structural facts
- do not omit canonical details just because they may be difficult to place later
- separate clearly:
  - resolved design facts
  - unresolved conflicts
  - missing information

Output only the canonical design record in the required structured format.
```

#### LLM2 input wrapper

```text
You are given:
- Phase 1 guidance
- retrieved evidence records from text, tables, figures, and sections
- evidence IDs and metadata

Build a compact canonical design record for the dominant antenna design in the paper.
Do not output the final schema.
Do not output explanations outside the structured result.

{payload_json}
```

Where `payload_json` is a pretty-printed JSON object with exactly these top-level keys:
- `run_context`
- `phase1_guidance`
- `retrieved_evidence_by_block`

#### LLM3 system prompt

```text
You are the final schema-construction layer for scientific antenna extraction.

You do NOT need to decide the dominant design from mixed raw evidence.
That decision has already been made upstream and is provided to you as a canonical design record.

Your task is to convert the canonical design record into the final schema: antenna_architecture_spec_mvp_v2.

Your primary goal is faithful transfer of canonical facts into the final schema.
Clean output matters, but fidelity matters more.

You must:
- preserve every canonical fact that the schema can represent
- preserve evidence IDs
- include every nested evidence_id again in the top-level evidence_used list
- use only valid internal ids matching `^[a-z][a-z0-9_]*$`
- never use colons, dots, spaces, or hyphens inside internal ids
- avoid inventing facts
- avoid duplicated parameters
- avoid noisy aliases
- keep unresolved ambiguity explicit rather than silently filling gaps
- represent the antenna architecture faithfully for downstream use

Critical rule:
Do NOT silently drop canonical geometric or feed details.

When a canonical fact maps directly to the schema:
- include it

When a canonical fact does not have a perfect one-to-one schema field:
- place it in the closest schema-compatible location that preserves meaning faithfully
- if it still cannot be represented cleanly, surface that loss explicitly in ambiguity, missing_required_for_build, or another schema-compatible uncertainty field
- never omit it silently just to keep the JSON cleaner

This applies especially to:
- feed coordinates
- feed geometry
- slot dimensions
- patch dimensions
- ground-plane dimensions
- layer thickness
- material assignments
- operating targets
- performance metrics

Only use facts supported by the canonical design record and linked evidence.
Do not semantically reinterpret discarded secondary evidence.
Do not create extra junk fields.
Do not create redundant parameter aliases unless required by the schema.

Important:
- cleanliness is secondary to faithful transfer
- omission is worse than explicit uncertainty
- when in doubt, preserve the fact and mark the uncertainty

Output only the structured schema result.
```

#### LLM3 input wrapper

```text
You are given:
- a canonical design record for one antenna paper
- linked evidence IDs and minimal supporting evidence context
- the target schema definition antenna_architecture_spec_mvp_v2

Produce antenna_architecture_spec_mvp_v2.
Output only the structured schema result.

{payload_json}
```

Where `payload_json` is a pretty-printed JSON object with exactly these top-level keys:
- `run_context`
- `canonical_design_record`
- `linked_evidence_records`

### Exact implemented legacy direct-path prompt text

This section is included for completeness because the prompt still exists in the repository, even though it is not the default path.

#### Legacy direct-path system prompt

```text
You extract an antenna_architecture_spec_mvp_v2 JSON document from retrieved evidence.

Rules:
- Use only the evidence provided in the prompt.
- Prefer evidence describing the proposed antenna over references, comparisons, or cited prior work.
- For classification, prioritize title, abstract, proposed-design, geometry, and direct design-description evidence.
- Use only evidence IDs that appear in the provided evidence records.
- Do not invent geometry, parameters, materials, layers, feeds, ports, placements, or IDs.
- Preserve explicit design parameters and units from the provided evidence when they are directly available.
- Bind explicit physical dimensions to the appropriate object type when the evidence makes the target object clear.
- Do not leave extractable structural dimensions orphaned in the global parameters list when they belong to entity geometry or layer thickness.
- If a physical feed property can only be represented globally under the current schema, keep it evidence-grounded and do not invent unsupported numeric placement fields.
- Strict ID Formatting for Assumed Entities: If the schema requires a referenced entity or material but the specific name is omitted in the evidence, you may instantiate a generic placeholder with status `assumed_local_origin`, but every internal id MUST strictly match `^[a-z][a-z0-9_]*$`. Never use dotted or system-like ids such as `.default_conductor`. Use valid ids like `material_assumed_1`.
- Contextual Anchoring for Ambiguous Dimensions: If a table provides dimensional parameters with generic names (e.g., 'Length', 'Width', 'd', 'r') without explicitly naming the target entity, DO NOT guess based purely on the variable name, and DO NOT ignore them. You MUST use your internal reasoning_scratchpad to cross-reference the provided text chunks, figure captions, or table context to deduce which physical entity (e.g., radiator, slot, ground, feed) is described by those values. Bind the dimension to the correct entity's geometry based on this contextual evidence.
- Generic Shape Inference: If an entity has explicit extracted dimensions but the geometric shape name is omitted, do not leave the geometry object empty. Infer a generic `shape_mode` strictly from the dimensional evidence available. For example, `radius` supports `circular`, while `length` and `width` support `rectangular`. If the shape still cannot be inferred safely, use `unspecified_polygon`.
- Every microstrip feed line or feed structure MUST be represented as an entity with its own geometry if dimensions are provided.
- A ground plane MUST be represented as an entity if its dimensions are provided.
- Implicit Port/Connector Handling: If a port/connector is implicitly required to feed the antenna but omitted in the text, do not leave `port_type` missing. Use status `assumed_local_origin` with a generic value such as `generic_port`.
- Do not copy snippets or evidence text into the final JSON.
- Do not include an evidence_registry object.
- Use evidence_ids on fields and objects, and a flat evidence_used list at top level.
- Mark unknowns with explicit status values instead of guessing.
- Avoid mixing design variants; prefer the final, proposed, optimized, selected, or best-supported design described in the evidence.
- Do not infer raw visual geometry from figures; use only the provided figure caption/context evidence.
- Keep the result solver-agnostic.
- Do not include CST commands, simulation setup, or operations trees.
- Slots and notches must be represented as entities, not boolean operations.
- Return one JSON object only.
```

#### Legacy extraction user prompt wrapper

`build_extraction_messages(...)` builds a user prompt with these exact sections:
- `Build a valid antenna_architecture_spec_mvp_v2 object.`
- required top-level keys list
- allowed `status` values list
- `Document context:` followed by compact JSON
- optional `Interpretation guidance (advisory, not ground truth):` followed by compact JSON
- `Retrieved evidence by block:` followed by compact JSON

#### Legacy repair user prompt wrapper

`build_repair_messages(...)` builds a repair prompt with these exact sections:
- `Repair the JSON so it validates as antenna_architecture_spec_mvp_v2.`
- `Do not add unsupported facts.`
- `Use only the provided evidence IDs.`
- `Document context:` + compact JSON
- `Retrieved evidence by block:` + compact JSON
- `Previous invalid JSON:` + compact JSON
- `Validation errors:` + compact JSON

### Exact deterministic Phase 1 discovery constants and rules that were missing above

Prompt and discovery file coverage lives in:
- `src/mvp/interpretation/discovery.py`

Important exact constants:
- `DISCOVERY_TOP_K = 5`
- `DISCOVERY_MAX_TOTAL = 9`
- `DISCOVERY_MAX_PER_BUCKET = {"proposal": 3, "final": 3, "variants": 3}`

Exact discovery query buckets:
- `proposal`
  - `proposed antenna`
  - `proposed design`
  - `antenna configuration`
- `final`
  - `final design`
  - `selected design`
  - `optimized design`
  - `fabricated prototype`
  - `measured prototype`
- `variants`
  - `design steps`
  - `design variants`
  - `reference antenna`
  - `modified design`

Current `candidate_design_mentions` hard rejections in the active main path:
- missing `evidence_id`
- empty cleaned text
- text containing `references`, `related work`, or `you may also like`
- anything rejected by `_looks_like_reference_snippet(...)`

Current exact non-behavior:
- `_looks_like_organization_snippet(...)` exists but is not currently used for hard rejection in the active path
- `_has_bucket_scope_signal(...)` exists but is not currently used for hard rejection in the active path

Current exact bucket selection rule:
- sort by retrieval `score` descending
- then `evidence_id` as stable tie-break

Current exact fallback scoring rules:
- phrase weights from `DESIGN_MENTION_PATTERNS`
- `+1.0` if text contains any of `design`, `antenna`, `prototype`, `variant`, `configuration`
- `-6.0` if text contains `references`, `related work`, or `you may also like`
- `+0.75` if `page_number <= 3`
- `+0.25` if source type is `chunk`
- discard if total score <= `0`

### Exact deterministic extraction retrieval plan

Main file:
- `src/mvp/extraction/agent.py`

Exact `RETRIEVAL_PLAN`:
- `classification`
  - `("text", "antenna type")`
  - `("text", "proposed design")`
  - `("text", "final design")`
  - `("text", "configuration")`
- `materials`
  - `("text", "substrate material")`
  - `("text", "dielectric material")`
  - `("text", "conductor material")`
  - `("tables", "material")`
- `layers`
  - `("text", "layer stack")`
  - `("text", "substrate thickness")`
  - `("text", "metal thickness")`
  - `("text", "ground plane")`
  - `("tables", "thickness")`
- `parameters`
  - `("tables", "dimensions")`
  - `("tables", "design parameters")`
  - `("text", "geometrical parameters")`
  - `("text", "table of dimensions")`
  - `("text", "operating frequency")`
- `entities`
  - `("text", "antenna geometry")`
  - `("text", "radiating element")`
  - `("text", "slot geometry")`
  - `("text", "ground plane geometry")`
  - `("figures", "antenna geometry")`
- `feeds`
  - `("text", "feeding method")`
  - `("text", "feed type")`
  - `("text", "feed location")`
  - `("text", "input port")`
  - `("text", "input impedance")`
- `quality`
  - `("text", "bandwidth")`
  - `("text", "gain")`
  - `("text", "return loss")`
  - `("text", "reflection coefficient")`
  - `("text", "VSWR")`

Exact query-merge rules:
- base-plan queries are added first
- Phase 1 queries are normalized and deduped only by exact `query_text`
- each Phase 1 query is then appended for every search type already used by the block
- dedupe key is `(query_source, search_type, query)`
- no extra numeric weighting is applied to Phase 1 queries beyond separate logging of `priority`

Exact block-level result merge rule:
- dedupe only by `evidence_id`
- first appearance wins inside the block

Exact compact source-payload rules:
- `table` source payload keeps first `12` rows plus `table_id`, `caption`, `page_number`, and `structured`
- `figure` source payload keeps `figure_id`, `caption`, `context` excerpted to `1200`, and `page_number`
- `section` source payload keeps `section_id`, `title`, `page_start`, `page_end`, and `text_excerpt` excerpted to `1200`
- `chunk/other` source payload keeps `text` excerpted to `1200` and `metadata`

Exact LLM2 evidence ordering rule:
- sort by retrieval `score` descending
- then page ascending
- then `evidence_id` ascending

### Exact deterministic validation and cleanup rules that were missing above

Canonical schema file:
- `src/mvp/schemas/canonical_design_record.py`

Final schema file:
- `src/mvp/schemas/extraction_spec.py`

Pipeline cleanup file:
- `src/mvp/extraction/pipeline.py`

Exact canonical evidence-id regex:
- `^[a-z_]+:[A-Za-z0-9_]+$`

Exact final-schema evidence-id regex:
- `^[a-z_]+:[A-Za-z0-9_]+$`

Exact internal-id regex for final schema ids and refs:
- `^[a-z][a-z0-9_]*$`

Exact final-schema consistency checks:
- all ids within each category must be unique
- every `layer.material_ref` must reference an existing material
- every `entity.layer_ref` must reference an existing layer
- every `entity.material_ref`, if present, must reference an existing material
- every `geometry.dimensions[*].param_ref`, if present, must reference an existing parameter
- every `feed.driven_entity_ref` must reference an existing entity
- every `instance.entity_ref` must reference an existing entity
- every nested `evidence_ids` entry anywhere in the model must also appear in top-level `evidence_used`

Exact `_validate_generation(...)` rules in the extraction pipeline:
- every `evidence_used` id must have come from retrieval
- every nested evidence id must also have come from retrieval

Exact `_apply_minimal_cleanup(...)` rules in the extraction pipeline:
1. merge nested evidence ids back into top-level `evidence_used`
2. dedupe `evidence_used` preserving order
3. normalize unit literals
4. remove exact duplicate parameters only
5. remap geometry `param_ref` pointers when exact duplicate parameters are removed
6. revalidate the full final schema

Exact unit normalization map:
- `?` -> `ohm`
- `ohm` -> `ohm`
- `ohms` -> `ohm`
- `ghz` -> `GHz`
- `mhz` -> `MHz`
- `khz` -> `kHz`
- `mm` -> `mm`
- otherwise keep stripped literal

Exact duplicate-parameter cleanup behavior:
- two parameters are considered duplicates only if their full JSON payload matches exactly after removing `param_id`
- this is exact duplicate cleanup, not semantic deduplication

### Exact legacy prompt-compaction rules that still exist in the codebase

Legacy prompt file:
- `src/mvp/extraction/legacy/prompting.py`

Exact constants:
- `DEFAULT_PROMPT_MAX_ITEMS_PER_BLOCK`
  - `classification: 2`
  - `materials: 2`
  - `quality: 2`
  - `entities: 3`
  - `feeds: 3`
  - `layers: 3`
  - `parameters: 4`
- `DEFAULT_PROMPT_EXCERPT_CHARS = 280`
- `DEFAULT_PROMPT_CHAR_BUDGET = 40000`

Exact legacy prompt-record sort key:
1. `_prompt_priority_score(block, record)` descending
2. retrieval score descending
3. page ascending
4. `evidence_id` ascending

Exact legacy table excerpt row caps:
- `parameters` block -> first `8` rows
- `layers` or `feeds` block -> first `5` rows
- other blocks -> first `4` rows

Exact legacy prompt-budget trimming rule:
- trim from the block with the most remaining prompt records
- tie-break by lowest trailing record score
- then block name

Exact legacy structured retry rule:
- max attempts = `3`
- on validation failure, append a corrective user message asking the model to fix the JSON so it strictly passes the schema

### Current authoritative interpretation of these rules

The repository currently contains two prompt families and two extraction styles:
- the multistage default path, which is authoritative
- the legacy direct path, which still exists in the codebase

For current development and evaluation, the authoritative path is:
- retrieval round 2 -> LLM2 canonicalization -> LLM3 schema construction -> minimal cleanup/validation

The legacy prompt-compaction and prompt-priority scoring logic remains relevant only because it still exists in the repository, not because it is the main extraction architecture.

---

## Authoritative Parser Update - 2026-04-20

This section supersedes older parser descriptions elsewhere in this document.

### Current parser architecture

The parser is now Docling-first and structured-IR-first.

Primary parser file:
- `src/mvp/parsers.py`

Parse orchestration file:
- `src/mvp/pipeline.py`

Current parser dependencies:
- `docling`
- `grobid-client-python`
- `pymupdf`

Docling is the primary parser backbone.
It is used for:
- layout-aware reading order
- text objects
- headings
- tables
- figures
- formulas
- page-object provenance when available

GROBID is optional enrichment only.
It is enabled only when `MVP_GROBID_URL` is set.
If `MVP_GROBID_URL` is unset, the parser records `grobid_status = "disabled"` and continues with Docling alone.
If GROBID is configured but fails, parsing still succeeds with Docling and records a warning.

The parser remains deterministic.
It does not use OCR, image understanding, LLM calls, retrieval, or prompt logic.

### Internal page-object IR

The new internal source of truth is:
- `bundle/page_objects.json`

The IR is an ordered per-page object list.
Each object carries:
- `page_number`
- `object_id`
- `object_type`
- `order_index`
- `text`
- `bbox`
- `source_artifact_id`
- `meta`

Current normalized object types:
- `heading`
- `paragraph`
- `table`
- `figure`
- `caption`
- `formula`
- `list_item`
- `footer_or_header_noise`

Markdown is now a derived export, not the parser's authoritative substrate.

### Current bundle contract

The outward bundle contract is still compatible with downstream indexing and retrieval:
- `bundle/fulltext.md`
- `bundle/sections.json`
- `bundle/page_objects.json`
- `bundle/parse_report.json`
- `bundle/figures/*.png`
- `bundle/tables/table_XXX.md`

`sections.json` still contains exactly:
- `section_id`
- `title`
- `text_excerpt`

Tables are exported as Markdown files from Docling structured table output when available.
If a table cannot be rendered cleanly from structure, the parser writes a readable fallback table representation.

Figures are exported as flat PNG files under `bundle/figures/`.
Figure captions are associated from Docling objects and nearby caption objects, not from local Markdown line scans.
Grouped figures can share one caption object.
Figures are allowed to remain captionless when no reliable caption exists.

Formulas are preserved explicitly in `page_objects.json` as `object_type = "formula"`.

### Current parse-report diagnostics

`parse_report.json` keeps the existing compatibility fields and now also includes structured-parser diagnostics:
- `captionless_figure_count`
- `figure_kind_counts`
- `table_with_caption_count`
- `table_without_caption_count`
- `page_object_count`
- `object_counts_by_type`
- `tables_using_structured_export_count`
- `figures_with_explicit_caption_count`
- `figures_with_group_caption_count`
- `figures_with_missing_caption_count`
- `grobid_status`

`src/mvp/pipeline.py` initializes and persists these fields in `_initial_parse_report(...)` and `parse_run(...)`.

### Latest parse-only validation runs

These runs were generated with parse-only CLI commands.
Indexing, Phase 1, and extraction were not run for this validation.

Commands:
- `uv run python -m mvp.cli --input data/raw/paper_001/article.pdf`
- `uv run python -m mvp.cli --input data/raw/paper_002/engproc-46-00010.pdf`
- `uv run python -m mvp.cli --input data/raw/paper_003/IJETT-V4I4P340.pdf`

Run for `article.pdf`:
- `runs/run_20260417T201556516557Z`
- `extracted_image_count = 11`
- `extracted_table_count = 2`
- `captionless_figure_count = 3`
- `figure_kind_counts = {"labeled_figure": 8, "unknown": 3, "decorative_or_editorial": 0, "equation_like": 0}`
- `table_with_caption_count = 2`
- `table_without_caption_count = 0`
- `page_object_count = 107`
- `object_counts_by_type = {"caption": 10, "figure": 11, "footer_or_header_noise": 9, "formula": 10, "heading": 8, "list_item": 20, "paragraph": 37, "table": 2}`
- `grobid_status = "disabled"`

Run for `engproc-46-00010.pdf`:
- `runs/run_20260417T201626222854Z`
- `extracted_image_count = 10`
- `extracted_table_count = 3`
- `captionless_figure_count = 6`
- `figure_kind_counts = {"labeled_figure": 4, "unknown": 6, "decorative_or_editorial": 0, "equation_like": 0}`
- `table_with_caption_count = 3`
- `table_without_caption_count = 0`
- `page_object_count = 173`
- `object_counts_by_type = {"caption": 7, "figure": 10, "footer_or_header_noise": 26, "formula": 1, "heading": 9, "list_item": 34, "paragraph": 83, "table": 3}`
- `grobid_status = "disabled"`

Run for `IJETT-V4I4P340.pdf`:
- `runs/run_20260417T201656482602Z`
- `extracted_image_count = 9`
- `extracted_table_count = 1`
- `captionless_figure_count = 0`
- `figure_kind_counts = {"labeled_figure": 9, "unknown": 0, "decorative_or_editorial": 0, "equation_like": 0}`
- `table_with_caption_count = 0`
- `table_without_caption_count = 1`
- `page_object_count = 80`
- `object_counts_by_type = {"caption": 9, "figure": 9, "formula": 8, "heading": 12, "list_item": 7, "paragraph": 34, "table": 1}`
- `grobid_status = "disabled"`

### Current parser quality notes

Reading order is materially better than the previous Markdown-line-first parser.
The parser now uses layout objects and page provenance instead of local Markdown caption heuristics.

Known parser strengths:
- better multi-column reading order
- real `page_objects.json` audit surface
- explicit formula preservation
- structured table export where Docling succeeds
- object-level figure/caption association
- grouped figure-caption support

Known parser weaknesses:
- first-page editorial/front-matter noise is reduced but not fully eliminated
- some author/contact/front-matter headings can still appear as section headings
- the `IJETT` table is detected, but its caption is not populated in the latest run
- GROBID enrichment has been wired but has not been exercised in the latest validation runs because `MVP_GROBID_URL` was not set
