# Implemented So Far

Last updated:
- `2026-05-18`

Repository path:
- `C:\Users\Lenovo\SynologyDrive\PhD\antennaAuto`

This document is the current project snapshot. It describes what is implemented in code today, not a future plan.

## Project Purpose

This repository is a local, auditable MVP pipeline for extracting antenna architecture information from scientific PDF papers.

The current goal is to process one paper per run folder, produce deterministic local evidence artifacts, retrieve relevant evidence, and use structured LLM calls to generate a strict final schema:

- `antenna_architecture_spec_mvp_v2.json`

The project is intentionally bounded.

Current non-goals:
- OCR
- raw-image multimodal figure interpretation
- CST script generation
- simulation setup generation
- optimization loops
- free browsing or open-ended autonomous research
- production orchestration

## Current Architecture

The current default runtime flow is:

```text
PDF
-> ingest
-> Docling-first parse into structured bundle artifacts
-> index evidence with BM25 + FAISS
-> optional Phase 1 paper-map / interpretation-map
-> retrieval round 2
-> LLM2 canonicalization
-> optional bounded LLM2 repair with retrieval tools
-> LLM3 schema construction
-> deterministic validation and minimal cleanup
-> final antenna_architecture_spec_mvp_v2.json
```

The current default extraction path is:

```text
retrieval -> LLM2 canonicalization -> optional LLM2 repair -> LLM3 schema construction
```

The legacy direct single-call extraction path still exists, but only behind:

```powershell
uv run python -m mvp.extract --run-dir runs/<run_id> --legacy-direct-extraction
```

## Important Runtime Modules

Top-level runtime:
- `src/mvp/cli.py`
- `src/mvp/extract.py`
- `src/mvp/pipeline.py`
- `src/mvp/bundle.py`

Parsing and indexing:
- `src/mvp/parsers.py`
- `src/mvp/index.py`
- `src/mvp/retrieval.py`

Phase 1:
- `src/mvp/interpretation/discovery.py`
- `src/mvp/interpretation/prompting.py`
- `src/mvp/interpretation/pipeline.py`
- `src/mvp/schemas/paper_map.py`
- `src/mvp/schemas/interpretation_map.py`

Extraction:
- `src/mvp/extraction/agent.py`
- `src/mvp/extraction/prompting.py`
- `src/mvp/extraction/pipeline.py`
- `src/mvp/extraction/legacy/prompting.py`
- `src/mvp/extraction/legacy/pipeline.py`
- `src/mvp/schemas/canonical_design_record.py`
- `src/mvp/schemas/extraction_spec.py`

LLM clients:
- `src/mvp/llm/client.py`

Prompt text files:
- `src/mvp/prompts/canonicalization_system.md`
- `src/mvp/prompts/schema_construction_system.md`
- `src/mvp/prompts/legacy_direct_system.md`

## Dependencies

Current project dependencies include:
- `docling`
- `grobid-client-python`
- `pymupdf`
- `pymupdf4llm`
- `faiss-cpu`
- `sentence-transformers`
- `openai`
- `openai-agents`
- `pydantic`
- `tenacity`

Docling is the primary parser. GROBID is optional enrichment. `pymupdf4llm` remains in the dependency list, but it is not the current primary parser backbone.

## Run Folder Structure

Each paper run lives under:

- `runs/<run_id>/`

Current important artifacts:

```text
runs/<run_id>/
  input/
    article.pdf
  bundle/
    metadata.json
    fulltext.md
    sections.json
    page_objects.json
    parse_report.json
    figures/*.png
    tables/table_*.md
  indexes/
    bm25/evidence_items.json
    faiss/index.faiss
    graph.json
    index_config.json
    index_report.json
  outputs/
    paper_map.json
    interpretation_map.json
    canonical_design_record.json
    phase2_retrieval_context.json
    antenna_architecture_spec_mvp_v2.json
    extraction_run_report.json
```

Debug mode may also write:

```text
outputs/debug/
  phase1_interpretation_messages.json
  phase1_interpretation_response.json
  llm2_canonicalization_request.json
  llm2_canonicalization_response.json
  llm2_repair_request.json
  llm2_repair_response.json
  llm2_repair_status.json
  llm3_schema_request.json
  llm3_schema_response.json
  phase2_retrieval_context_verbose.json
```

## Parser State

The parser is now Docling-first and structured-IR-first.

Primary file:
- `src/mvp/parsers.py`

Parse orchestration:
- `src/mvp/pipeline.py::parse_run`

Primary parser behavior:
- uses Docling `DocumentConverter`
- disables OCR
- enables table structure extraction
- generates page and picture images
- creates a normalized per-page object IR
- writes `bundle/page_objects.json`
- derives `fulltext.md`, `sections.json`, table markdown files, figure PNGs, and `parse_report.json`

GROBID behavior:
- optional only
- enabled only when `MVP_GROBID_URL` is set
- used for metadata/section enrichment
- parsing still succeeds without it
- failures are reported as warnings instead of failing the parse

Current normalized page-object types:
- `heading`
- `paragraph`
- `table`
- `figure`
- `caption`
- `formula`
- `list_item`
- `footer_or_header_noise`

Current parser guarantees:
- no OCR path
- no `pdfplumber` parser path
- no parser-stage LLM calls
- no parser-stage image understanding
- markdown is a derived export, not the parser's source of truth

## Bundle Contract

The outward bundle contract is stable:

- `bundle/fulltext.md`
- `bundle/sections.json`
- `bundle/page_objects.json`
- `bundle/parse_report.json`
- `bundle/figures/*.png`
- `bundle/tables/table_*.md`

`sections.json` remains lean. Each section has exactly:
- `section_id`
- `title`
- `text_excerpt`

Tables are exported as markdown files. The expected file format is:

```text
Optional table caption

| Markdown | table |
| --- | --- |
```

Figures are flat PNG files under:

- `bundle/figures/`

No figure sidecar folders are used.

## Parse Report Diagnostics

`parse_report.json` keeps compatibility fields and structured-parser diagnostics.

Important fields include:
- `status`
- `message`
- `page_count`
- `extracted_image_count`
- `extracted_table_count`
- `fulltext_generated`
- `sections_generated`
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
- `table_summaries`
- `figure_summaries`
- `page_summaries`
- `parser_versions`
- `warnings`

## Indexing And Evidence

Indexing is implemented in:
- `src/mvp/index.py`

Retrieval is implemented in:
- `src/mvp/retrieval.py`

Evidence item source types:
- `chunk`
- `section`
- `table`
- `figure`

Evidence IDs use prefixed forms:
- `chunk:chunk_001`
- `section:section_001`
- `table:table_001`
- `figure:figure_001`

The indexer consumes the markdown-native bundle:
- sections from `sections.json`
- tables from `tables/table_*.md`
- figures from `parse_report.figure_summaries`
- chunks from `fulltext.md` / page summaries

Retrieval supports:
- `BundleRetriever.search_text`
- `BundleRetriever.search_tables`
- `BundleRetriever.search_figures`
- `BundleRetriever.get_evidence_by_id`
- `BundleRetriever.get_table`
- `BundleRetriever.get_figure`

Retrieval uses BM25 plus FAISS dense retrieval. Current supported fusion strategies are:
- `weighted`
- `rrf`

## Phase 1

Phase 1 is a bounded paper-understanding and retrieval-planning step.

Command:

```powershell
uv run python -m mvp.extract --run-dir runs/<run_id> --phase1-only
```

Main function:
- `src/mvp/interpretation/pipeline.py::run_phase1`

Outputs:
- `outputs/paper_map.json`
- `outputs/interpretation_map.json`
- `outputs/extraction_run_report.json`

Current Phase 1 model:
- `gpt-5.4-mini`

Phase 1 does not extract the final schema. It produces guidance for later retrieval.

`paper_map.json` is deterministic. It includes:
- title
- abstract
- top-level section headings
- key design signals
- candidate design mentions
- key table references
- key figure references

`interpretation_map.json` is LLM-generated and includes:
- `has_multiple_variants`
- `has_final_design_signal`
- `search_queries`
- `open_uncertainties`

## Phase 1 Prompt

Phase 1 uses `OpenAIJsonClient.generate_structured`.

System prompt in:
- `src/mvp/interpretation/prompting.py`

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

User prompt wrapper:

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

## Retrieval Round 2

Retrieval round 2 is deterministic and block-based.

Main file:
- `src/mvp/extraction/agent.py`

Current blocks:
- `classification`
- `materials`
- `layers`
- `parameters`
- `entities`
- `feeds`
- `quality`

Base retrieval plan:

| Block | Queries |
|---|---|
| `classification` | text: `antenna type`, `proposed design`, `final design`, `configuration` |
| `materials` | text: `substrate material`, `dielectric material`, `conductor material`; tables: `material` |
| `layers` | text: `layer stack`, `substrate thickness`, `metal thickness`, `ground plane`; tables: `thickness` |
| `parameters` | tables: `dimensions`, `design parameters`; text: `geometrical parameters`, `table of dimensions`, `operating frequency` |
| `entities` | text: `antenna geometry`, `radiating element`, `slot geometry`, `ground plane geometry`; figures: `antenna geometry` |
| `feeds` | text: `feeding method`, `feed type`, `feed location`, `input port`, `input impedance` |
| `quality` | text: `bandwidth`, `gain`, `return loss`, `reflection coefficient`, `VSWR` |

Phase 1 query routing:
- Phase 1 queries always route to text when the block has text retrieval.
- Phase 1 queries route to tables only when table cues are present.
- Phase 1 queries route to figures only when explicit figure/layout cues are present.
- Phase 1 queries use `min(3, top_k)`.
- Base-plan queries use the requested `top_k`.

Current table cues:
- `table`
- `parameter`
- `parameters`
- `dimension`
- `dimensions`
- `thickness`
- `material`

Current figure cues:
- `figure`
- `fig`
- `diagram`
- `schematic`
- `layout`
- `geometry`

## LLM2 Evidence Selection

Full retrieval diagnostics are preserved, but LLM2 receives a capped evidence subset.

Implemented in:
- `src/mvp/extraction/pipeline.py::_prepare_llm2_evidence_by_block`
- `src/mvp/extraction/pipeline.py::_select_llm2_evidence_for_block`
- `src/mvp/extraction/prompting.py::_compact_evidence_for_llm2`

LLM2 block caps:

| Block | Cap |
|---|---:|
| `classification` | 8 |
| `materials` | 8 |
| `layers` | 8 |
| `feeds` | 8 |
| `quality` | 8 |
| `parameters` | 10 |
| `entities` | 10 |

The first selection pass respects light modality caps. A second pass fills remaining block capacity by retrieval rank.

LLM2 prompt records keep:
- `evidence_id`
- `source_type`
- `source_id`
- `page_number`
- `content`
- `source_payload`

LLM2 prompt records drop:
- `score`
- `snippet`

Table payloads now keep full reconstructed rows and markdown:

```json
{
  "table_id": "table_001",
  "caption": "Table 1. Parameters",
  "page_number": 2,
  "rows": [["Parameter", "Value"], ["L", "10"]],
  "markdown": "| Parameter | Value | ...",
  "structured": true
}
```

## LLM2 Canonicalization

LLM2 is the semantic arbitration stage.

Purpose:
- identify the dominant antenna design
- separate final design facts from variants/intermediate/reference content
- preserve build-critical geometry/material/layer/feed facts
- preserve evidence IDs
- surface unresolved conflicts
- output `CanonicalDesignRecord`, not the final schema

Main files:
- `src/mvp/extraction/prompting.py`
- `src/mvp/extraction/pipeline.py`
- `src/mvp/schemas/canonical_design_record.py`

Current model:
- `gpt-5.4-mini`

Reasoning effort:
- `medium`

Client:
- `OpenAIAgentsStructuredClient.generate_structured_via_agent`

Agent settings:
- `agent_name = phase2_canonicalization`
- `max_turns = 1`
- `response_model = CanonicalDesignRecord`

## LLM2 Prompt

System prompt file:
- `src/mvp/prompts/canonicalization_system.md`

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

User prompt wrapper:

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

`payload_json` contains:
- `run_context`
- `phase1_guidance`
- `retrieved_evidence_by_block`

## CanonicalDesignRecord Shape

Current schema:
- `src/mvp/schemas/canonical_design_record.py::CanonicalDesignRecord`

Top-level fields:
- `selected_design_summary`
- `selected_design_rationale`
- `has_multiple_variants`
- `dominant_evidence_ids`
- `secondary_evidence_ids`
- `identified_antennas`
- `proposed_final_antenna_rationale`
- `final_design`
- `design_evolution_notes`
- `unresolved_conflicts`

`identified_antennas` and `proposed_final_antenna_rationale` are intentionally present before `final_design`. They force LLM2 to enumerate candidate antennas/variants and justify the chosen dominant design before constructing the canonical final design.

`final_design` contains:
- `classification`
- `patch`
- `feed`
- `ground`
- `slots`
- `materials`
- `layers`
- `performance_targets`
- `extra_parameters`

Canonical evidence IDs are validated against retrieved evidence by:
- `src/mvp/extraction/pipeline.py::_validate_canonical_generation`

## Optional LLM2 Repair

Optional repair was added between LLM2 and LLM3.

Main functions:
- `src/mvp/extraction/pipeline.py::_canonical_record_needs_repair`
- `src/mvp/extraction/pipeline.py::_build_canonical_repair_tools`
- `src/mvp/extraction/pipeline.py::_merge_repair_evidence_into_context`
- `src/mvp/extraction/prompting.py::build_canonical_repair_input`
- `src/mvp/llm/client.py::OpenAIAgentsStructuredClient.generate_structured_via_agent_with_tools`

Repair trigger checks for obvious under-specification:
- feed exists but location is missing
- feed exists but dimensions are empty
- patch exists but dimensions are empty
- ground exists but dimensions are empty
- slots exist but one or more slot dimensions are empty
- layers are empty
- materials are empty
- unresolved conflicts mention geometry/feed/layer/slot/patch/ground/material issues

Repair is bounded:
- one repair pass only
- `max_turns = 4`
- no filesystem tools
- no browsing tools
- no parser/index redesign

Repair tool limits:
- `search_text(query, top_k)` capped at `3`
- `search_tables(query, top_k)` capped at `3`
- `search_figures(query, top_k)` capped at `2`
- `get_evidence_by_id(evidence_id)`

Repair evidence behavior:
- every returned/fetched repair evidence record is captured in `repair_evidence_by_id`
- repair evidence is merged into `retrieval_context["evidence_by_block"]["canonical_repair"]`
- repair evidence IDs are merged into `retrieval_context["all_retrieved_evidence_ids"]`
- repaired canonical validation uses the expanded evidence set
- LLM3 linking also uses the expanded evidence set

Repair failure is non-fatal:
- the pipeline records the failure in `repair_stage_error`
- extraction continues with the initial validated canonical record

## LLM2 Repair Prompt

Repair uses the same canonicalization system prompt:
- `src/mvp/prompts/canonicalization_system.md`

Repair user prompt wrapper:

```text
You are repairing an existing canonical design record before final schema construction.

Rules:
- Keep the selected dominant design fixed unless the current record is clearly inconsistent with retrieved evidence.
- Retrieve only the evidence needed to repair the listed missing build-critical fields.
- Use as few retrieval queries as possible.
- Make no more than two tool calls total, then output the repaired full record.
- Prefer text and tables; use figures only when necessary for geometry or layout evidence.
- Output a complete CanonicalDesignRecord, not a patch fragment.
- Use only evidence IDs returned by the provided retrieval tools or already present in the canonical record.

{payload_json}
```

`payload_json` contains:
- `run_context`
- `phase1_guidance`
- `missing_requirements`
- `canonical_design_record`

## LLM3 Schema Construction

LLM3 converts the canonical record into the final schema.

Purpose:
- transfer canonical facts into `AntennaArchitectureSpecMvpV2`
- preserve evidence IDs
- include nested evidence IDs in top-level `evidence_used`
- avoid inventing facts
- preserve uncertainty explicitly

Main files:
- `src/mvp/extraction/prompting.py`
- `src/mvp/extraction/pipeline.py`
- `src/mvp/schemas/extraction_spec.py`

Current model:
- `gpt-5.4-mini`

Reasoning effort:
- `medium`

Client:
- `OpenAIAgentsStructuredClient.generate_structured_via_agent`

Agent settings:
- `agent_name = phase3_schema_construction`
- `max_turns = 1`
- `response_model = AntennaArchitectureSpecMvpV2`

## LLM3 Prompt

System prompt file:
- `src/mvp/prompts/schema_construction_system.md`

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

User prompt wrapper:

```text
You are given:
- a canonical design record for one antenna paper
- linked evidence IDs and minimal supporting evidence context
- the target schema definition antenna_architecture_spec_mvp_v2

Produce antenna_architecture_spec_mvp_v2.
Output only the structured schema result.

{payload_json}
```

`payload_json` contains:
- `run_context`
- `canonical_design_record`
- `linked_evidence_records`

Linked evidence records are built by:
- `src/mvp/extraction/pipeline.py::_build_linked_evidence_records`

Only canonical evidence IDs are linked into LLM3.

## Final Schema Validation And Cleanup

Final schema:
- `src/mvp/schemas/extraction_spec.py::AntennaArchitectureSpecMvpV2`

Main validation and cleanup functions:
- `src/mvp/extraction/pipeline.py::_validate_generation`
- `src/mvp/extraction/pipeline.py::_apply_minimal_cleanup`

Validation requires:
- top-level `evidence_used` IDs must come from retrieval
- nested evidence IDs must come from retrieval
- nested evidence IDs must appear in top-level `evidence_used`
- internal IDs must match schema rules
- references must resolve to existing materials/layers/entities/parameters

Cleanup currently:
- merges nested evidence IDs into top-level `evidence_used`
- dedupes `evidence_used`
- normalizes common unit literals
- removes exact duplicate parameters
- remaps geometry `param_ref` values when exact duplicate parameters are removed

Cleanup does not perform broad deterministic antenna topology repair.

## Evidence-ID Auto-Correction

The final extraction schema includes evidence-ID normalization for common LLM formatting misses.

Implemented in:
- `src/mvp/schemas/extraction_spec.py`

Behavior:
- `chunk_001` can be normalized to `chunk:chunk_001`
- `page_001` can be normalized to `section:page_001`
- `table_001` can be normalized to `table:table_001`
- `fig_001` can be normalized to `figure:fig_001`

This is applied to nested `evidence_ids` and top-level `evidence_used`.

Validation remains strict after normalization.

## Legacy Direct Extraction

Legacy direct extraction is isolated under:
- `src/mvp/extraction/legacy/pipeline.py`
- `src/mvp/extraction/legacy/prompting.py`

It is not the default path.

Legacy prompt text:
- `src/mvp/prompts/legacy_direct_system.md`

Legacy mode still has:
- prompt-budget compaction
- direct final-schema generation
- validation repair messages
- `gpt-4o` default model when called through the legacy flag

## Legacy Direct Prompt

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

## CLI Commands

Ingest and parse only:

```powershell
uv run python -m mvp.cli --input data/raw/paper_001/article.pdf
```

Ingest, parse, and index:

```powershell
uv run python -m mvp.cli --input data/raw/paper_001/article.pdf --index
```

Index an existing run:

```powershell
uv run python -m mvp.cli --run-dir runs/<run_id> --index
```

Run Phase 1 only:

```powershell
uv run python -m mvp.extract --run-dir runs/<run_id> --phase1-only
```

Run default extraction:

```powershell
uv run python -m mvp.extract --run-dir runs/<run_id>
```

Run extraction with debug artifacts:

```powershell
uv run python -m mvp.extract --run-dir runs/<run_id> --debug
```

Run legacy direct extraction:

```powershell
uv run python -m mvp.extract --run-dir runs/<run_id> --legacy-direct-extraction
```

## Recent Validation Status

Recent focused tests run after the LLM2 repair and full-table changes:

```powershell
uv run python -m pytest -q tests/test_extraction_agent.py tests/test_extraction_prompting.py tests/test_extraction_pipeline.py tests/test_llm_client.py
```

Result:
- `24 passed`
- `3 warnings`

Recent extraction validation runs:
- `runs/run_20260421T091405157638Z`
- `runs/run_20260421T091437985264Z`
- `runs/run_20260421T091510556541Z`

All three completed with:
- `extraction_status = completed`
- `validation_success = true`

Repair was considered and executed on those runs. Repair evidence was merged into the valid evidence set before canonical validation and LLM3 linking.

Observed repair outcomes:

| Run | Missing requirements | Repair used | Validation |
|---|---|---:|---:|
| `run_20260421T091405157638Z` | `feed_location` | yes | true |
| `run_20260421T091437985264Z` | `feed_location` | yes | true |
| `run_20260421T091510556541Z` | `feed_dimensions`, `geometry_conflict` | yes | true |

Current practical note:
- repair can improve canonical evidence coverage, but it does not guarantee every build-critical gap becomes fully represented in the final schema.
- missing caption/context or weak source evidence can still limit reconstruction readiness.

## Current Strengths

The current system now has:
- Docling-first structured parsing
- explicit `page_objects.json` audit artifact
- deterministic local evidence indexing
- bounded Phase 1 retrieval planning
- modality-aware Phase 1 query routing
- compact LLM2 input selection
- full table rows and markdown passed to LLM2
- explicit LLM2 canonicalization checkpoint
- optional bounded LLM2 repair with retrieval tools
- repair evidence merged into the valid evidence set
- explicit LLM3 schema transfer layer
- strict Pydantic validation
- evidence-ID auto-correction for common prefix omissions
- compact audit artifacts plus debug-mode verbose artifacts
- isolated legacy direct extraction path

## Current Limitations

Known limitations:
- parser does not perform OCR or image understanding
- figure evidence is still caption/context based
- GROBID is optional and has not been exercised unless `MVP_GROBID_URL` is configured
- LLM2 still owns dominant design arbitration
- optional repair is bounded and may leave unresolved gaps
- final CST-readiness is not deterministically guaranteed
- schema compatibility can still force some facts into less-than-perfect locations
- legacy direct code still exists, though isolated

## Most Important Files To Inspect When Debugging

For parser quality:
- `bundle/page_objects.json`
- `bundle/fulltext.md`
- `bundle/sections.json`
- `bundle/parse_report.json`

For indexing:
- `indexes/bm25/evidence_items.json`
- `indexes/index_report.json`

For Phase 1:
- `outputs/paper_map.json`
- `outputs/interpretation_map.json`

For retrieval and LLM2 input:
- `outputs/phase2_retrieval_context.json`

For semantic arbitration:
- `outputs/canonical_design_record.json`

For final extraction:
- `outputs/antenna_architecture_spec_mvp_v2.json`
- `outputs/extraction_run_report.json`

For raw prompts/responses:
- rerun with `--debug`
- inspect `outputs/debug/`

## Current Ground Truth Summary

The repository currently implements a deterministic local ingestion, parsing, indexing, and retrieval stack with a multistage structured LLM extraction path. The parser is Docling-first and writes a page-object IR plus markdown-compatible bundle artifacts. Phase 1 creates retrieval guidance, not final schema fields. The default extraction path retrieves evidence by block, sends a capped but table-preserving evidence set to LLM2, canonicalizes the dominant design, optionally runs one bounded tool-enabled repair pass when build-critical canonical fields are weak, merges repair evidence into the valid evidence set, and then asks LLM3 to produce the final strict schema. The final output is validated with Pydantic and minimal deterministic cleanup.

