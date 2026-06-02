# Current Extraction Pipeline: Detailed Q&A

Repository root used for this audit:

- `C:\Users\Lenovo\SynologyDrive\PhD\antennaAuto`

Last reviewed against the checked-out code on 2026-05-18.

This document describes the current extraction path implemented in code. It focuses on the path that starts from an already ingested, parsed, and indexed run bundle and produces `antenna_architecture_spec_mvp_v2.json`.

## 1. What Is The Current Default Extraction Flow?

The default extraction path is:

```text
prepared run bundle
-> Phase 1 paper-map / interpretation-map, optional but reused when present
-> second-stage retrieval
-> LLM2 canonicalization
-> optional bounded LLM2 repair with retrieval tools
-> LLM3 schema construction
-> deterministic validation and minimal cleanup
-> final antenna_architecture_spec_mvp_v2.json
```

The main files are:

- `src/mvp/extract.py`
- `src/mvp/interpretation/pipeline.py`
- `src/mvp/extraction/agent.py`
- `src/mvp/extraction/pipeline.py`
- `src/mvp/extraction/prompting.py`
- `src/mvp/llm/client.py`

The default CLI command is:

```powershell
uv run python -m mvp.extract --run-dir runs/<run_id>
```

The legacy direct extraction path is still available, but only behind:

```powershell
uv run python -m mvp.extract --run-dir runs/<run_id> --legacy-direct-extraction
```

## 2. What Must Already Exist Before Extraction Runs?

`src/mvp/extraction/pipeline.py::_validate_run_inputs` requires:

- `metadata.json`
- `bundle/sections.json`
- `indexes/bm25/evidence_items.json`
- `indexes/faiss/index.faiss`

That means extraction does not parse PDFs or build indexes by itself. It expects ingestion, parsing, and indexing to have already produced the run bundle.

The parser is currently Docling-first and writes a structured bundle, including:

- `bundle/fulltext.md`
- `bundle/sections.json`
- `bundle/parse_report.json`
- `bundle/page_objects.json`
- `bundle/figures/*.png`
- `bundle/tables/table_*.md`

## 3. How Does Phase 1 Work?

Phase 1 is run with:

```powershell
uv run python -m mvp.extract --run-dir runs/<run_id> --phase1-only
```

Implemented in:

- `src/mvp/interpretation/pipeline.py::run_phase1`
- `src/mvp/interpretation/discovery.py::build_paper_map`
- `src/mvp/interpretation/prompting.py::build_interpretation_messages`

It writes:

- `outputs/paper_map.json`
- `outputs/interpretation_map.json`
- `outputs/extraction_run_report.json`

Phase 1 has two parts:

1. Deterministic paper-map construction.
2. One structured LLM call that produces an `InterpretationMap`.

The Phase 1 model default is:

```text
gpt-5.4-mini
```

## 4. What Is The Phase 1 Prompt?

Phase 1 uses chat-completions structured output through `OpenAIJsonClient.generate_structured`.

System prompt in `src/mvp/interpretation/prompting.py`:

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

User prompt shape:

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

## 5. How Does Phase 1 Influence Extraction?

Extraction loads Phase 1 guidance in:

- `src/mvp/extraction/pipeline.py::_load_phase1_guidance`

The second-stage retrieval call is:

- `src/mvp/extraction/agent.py::gather_retrieval_context_with_phase1`

Only `interpretation_map.search_queries` are injected into second-stage retrieval. Phase 1 also appears in the LLM2 prompt as compact advisory context:

- `has_multiple_variants`
- `has_final_design_signal`
- `search_queries`
- `open_uncertainties`

Phase 1 does not directly write final schema fields.

## 6. What Is The Base Retrieval Plan?

The base retrieval plan is in `src/mvp/extraction/agent.py::RETRIEVAL_PLAN`.

Current blocks and queries:

| Block | Search queries |
|---|---|
| `classification` | text: `antenna type`, `proposed design`, `final design`, `configuration` |
| `materials` | text: `substrate material`, `dielectric material`, `conductor material`; tables: `material` |
| `layers` | text: `layer stack`, `substrate thickness`, `metal thickness`, `ground plane`; tables: `thickness` |
| `parameters` | tables: `dimensions`, `design parameters`; text: `geometrical parameters`, `table of dimensions`, `operating frequency` |
| `entities` | text: `antenna geometry`, `radiating element`, `slot geometry`, `ground plane geometry`; figures: `antenna geometry` |
| `feeds` | text: `feeding method`, `feed type`, `feed location`, `input port`, `input impedance` |
| `quality` | text: `bandwidth`, `gain`, `return loss`, `reflection coefficient`, `VSWR` |

## 7. How Are Phase 1 Queries Routed?

Implemented in:

- `src/mvp/extraction/agent.py::_block_query_entries`
- `src/mvp/extraction/agent.py::_phase1_search_types_for_block`
- `src/mvp/extraction/agent.py::_phase1_query_supports_tables`
- `src/mvp/extraction/agent.py::_phase1_query_supports_figures`

Current behavior:

- Base-plan queries run unchanged.
- Phase 1 queries always route to `text` when that block has text search.
- Phase 1 queries route to `tables` only when they contain generic table cues:
  - `table`
  - `parameter`
  - `parameters`
  - `dimension`
  - `dimensions`
  - `thickness`
  - `material`
- Phase 1 queries route to `figures` only when they contain explicit figure/layout cues:
  - `figure`
  - `fig`
  - `diagram`
  - `schematic`
  - `layout`
  - `geometry`
- Phase 1 queries use `min(3, top_k)`.
- Base-plan queries use the requested `top_k`.

This keeps Phase 1 from being sprayed across every modality.

## 8. How Does Retrieval Rank Candidates?

Implemented in:

- `src/mvp/retrieval.py::BundleRetriever`
- `src/mvp/retrieval.py::_hybrid_search`

Search boundaries:

- `search_text`: evidence types `section`, `chunk`
- `search_tables`: evidence type `table`
- `search_figures`: evidence type `figure`

Ranking uses BM25 plus FAISS dense retrieval over the allowed evidence subset. Supported fusion modes are:

- `weighted`
- `rrf`

The returned retrieval result includes:

- `evidence_id`
- `source_type`
- `source_id`
- `page_number`
- `score`
- `snippet`
- BM25 / dense diagnostics
- final rank metadata

## 9. What Evidence Is Sent Toward LLM2?

Retrieval-side records are built in:

- `src/mvp/extraction/agent.py::_build_prompt_record`
- `src/mvp/extraction/agent.py::_compact_source_payload`

Each record contains:

- `evidence_id`
- `source_type`
- `source_id`
- `page_number`
- `score`
- `snippet`
- `content`
- `source_payload`

Current payload compaction:

- generic evidence `content`: `700` chars
- figure context: `350` chars
- section excerpt: `500` chars
- generic text payload: `500` chars
- tables keep full reconstructed `rows`
- tables also include `markdown`

Table payloads currently preserve:

```json
{
  "table_id": "...",
  "caption": "...",
  "page_number": 3,
  "rows": [["Parameter", "Value"], ["L", "10"]],
  "markdown": "| Parameter | Value | ...",
  "structured": true
}
```

## 10. How Is LLM2 Input Capped?

Implemented in:

- `src/mvp/extraction/pipeline.py::_prepare_llm2_evidence_by_block`
- `src/mvp/extraction/pipeline.py::_select_llm2_evidence_for_block`

Block caps:

| Block | Max LLM2 records |
|---|---:|
| `classification` | 8 |
| `materials` | 8 |
| `layers` | 8 |
| `feeds` | 8 |
| `quality` | 8 |
| `parameters` | 10 |
| `entities` | 10 |

The first pass respects light source-type caps. A second pass fills remaining slots by rank regardless of source type.

LLM2 prompt payload is compacted in:

- `src/mvp/extraction/prompting.py::_compact_evidence_for_llm2`

The LLM2 prompt drops:

- `score`
- `snippet`

It keeps:

- `evidence_id`
- `source_type`
- `source_id`
- `page_number`
- `content`
- `source_payload`

Retrieval diagnostics still keep the fuller records.

## 11. What Is The LLM2 Canonicalization Prompt?

LLM2 is called through:

- `src/mvp/llm/client.py::OpenAIAgentsStructuredClient.generate_structured_via_agent`

The agent is:

```text
agent_name = phase2_canonicalization
model = gpt-5.4-mini
reasoning_effort = medium
max_turns = 1
response_model = CanonicalDesignRecord
```

System prompt file:

- `src/mvp/prompts/canonicalization_system.md`

System prompt:

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

User prompt shape from `build_canonicalization_input`:

```text
You are given:
- Phase 1 guidance
- retrieved evidence records from text, tables, figures, and sections
- evidence IDs and metadata

Build a compact canonical design record for the dominant antenna design in the paper.
Do not output the final schema.
Do not output explanations outside the structured result.

{JSON payload}
```

The JSON payload contains:

- `run_context`
- compact Phase 1 guidance
- `retrieved_evidence_by_block`

## 12. What Does CanonicalDesignRecord Add Before LLM3?

The canonical record is defined in:

- `src/mvp/schemas/canonical_design_record.py`

It explicitly includes pre-selection fields:

- `identified_antennas`
- `proposed_final_antenna_rationale`

These force LLM2 to enumerate candidate antennas/variants and justify the dominant final design before filling `final_design`.

Validation checks that all canonical evidence IDs are from retrieved evidence:

- `src/mvp/extraction/pipeline.py::_validate_canonical_generation`

## 13. When Does Optional LLM2 Repair Run?

After the initial LLM2 canonical record validates, the pipeline calls:

- `src/mvp/extraction/pipeline.py::_canonical_record_needs_repair`

The repair trigger is intentionally small. It checks for obvious missing build-critical areas:

- feed exists but location is missing
- feed exists but dimensions are empty
- patch exists but dimensions are empty
- ground exists but dimensions are empty
- slot components exist but have no dimensions
- layers are empty
- materials are empty
- unresolved conflicts mention geometry/feed/layer/slot/patch/ground/material issues

If repair is not needed, extraction proceeds directly to LLM3.

If repair is needed, exactly one bounded tool-enabled LLM2 repair call is attempted.

Repair failure is non-fatal. The pipeline records the error and continues with the initial validated canonical record.

## 14. What Retrieval Tools Can Repair Use?

Tool construction lives in:

- `src/mvp/extraction/pipeline.py::_build_canonical_repair_tools`

Exposed tools:

- `search_text(query, top_k=3)`
- `search_tables(query, top_k=3)`
- `search_figures(query, top_k=2)`
- `get_evidence_by_id(evidence_id)`

Caps are enforced inside the tools:

- text max `3`
- tables max `3`
- figures max `2`

Every returned or fetched evidence record is recorded in `repair_evidence_by_id`.

After repair:

- repair evidence is merged into `retrieval_context["evidence_by_block"]["canonical_repair"]`
- repair evidence IDs are merged into `retrieval_context["all_retrieved_evidence_ids"]`
- repaired canonical validation uses the expanded evidence set
- LLM3 linked evidence is built from the expanded evidence set

This matters because LLM3 is allowed to cite evidence discovered during repair only after it has been merged into the valid evidence universe.

## 15. What Is The LLM2 Repair Prompt?

Repair uses the same canonicalization system prompt as LLM2:

- `src/mvp/prompts/canonicalization_system.md`

The repair user prompt is built by:

- `src/mvp/extraction/prompting.py::build_canonical_repair_input`

Prompt shape:

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

{JSON payload}
```

The JSON payload contains:

- `run_context`
- compact Phase 1 guidance
- `missing_requirements`
- original `canonical_design_record`

Repair is called through:

- `src/mvp/llm/client.py::OpenAIAgentsStructuredClient.generate_structured_via_agent_with_tools`

Agent settings:

```text
agent_name = phase2_canonical_repair
model = gpt-5.4-mini
reasoning_effort = medium
max_turns = 4
response_model = CanonicalDesignRecord
tools = bounded retrieval tools
```

## 16. What Is The LLM3 Schema Construction Prompt?

LLM3 is called through:

- `src/mvp/llm/client.py::OpenAIAgentsStructuredClient.generate_structured_via_agent`

The agent is:

```text
agent_name = phase3_schema_construction
model = gpt-5.4-mini
reasoning_effort = medium
max_turns = 1
response_model = AntennaArchitectureSpecMvpV2
```

System prompt file:

- `src/mvp/prompts/schema_construction_system.md`

System prompt:

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

User prompt shape from `build_schema_construction_input`:

```text
You are given:
- a canonical design record for one antenna paper
- linked evidence IDs and minimal supporting evidence context
- the target schema definition antenna_architecture_spec_mvp_v2

Produce antenna_architecture_spec_mvp_v2.
Output only the structured schema result.

{JSON payload}
```

The JSON payload contains:

- `run_context`
- `canonical_design_record`
- `linked_evidence_records`

Linked evidence is built by:

- `src/mvp/extraction/pipeline.py::_build_linked_evidence_records`

Only evidence IDs cited by the canonical record are passed to LLM3.

## 17. What Deterministic Cleanup Happens After LLM3?

After LLM3 returns, the pipeline validates and minimally cleans the output:

- `src/mvp/extraction/pipeline.py::_validate_generation`
- `src/mvp/extraction/pipeline.py::_apply_minimal_cleanup`

Current cleanup:

- ensures nested evidence IDs appear in top-level `evidence_used`
- normalizes common unit spellings, such as `ohms` to `ohm`
- deduplicates exact duplicate parameter payloads and remaps geometry references

The current code does not run a broad deterministic topology repair or CST sufficiency validator.

## 18. What Evidence IDs Are Considered Valid?

For LLM2 canonical validation:

- all canonical evidence IDs must be inside `retrieval_context["all_retrieved_evidence_ids"]`

For LLM3 final schema validation:

- top-level `evidence_used` must be inside `all_retrieved_evidence_ids`
- all nested `evidence_ids` must also be inside `all_retrieved_evidence_ids`

Repair evidence is valid only because `_merge_repair_evidence_into_context` adds it to:

- `evidence_by_block["canonical_repair"]`
- `evidence_ids_by_block["canonical_repair"]`
- `all_retrieved_evidence_ids`

## 19. What Is Written To Outputs?

Default extraction writes:

- `outputs/canonical_design_record.json`
- `outputs/antenna_architecture_spec_mvp_v2.json`
- `outputs/extraction_run_report.json`
- `outputs/phase2_retrieval_context.json`

When `--debug` is used, debug artifacts may include:

- `outputs/debug/llm2_canonicalization_request.json`
- `outputs/debug/llm2_canonicalization_response.json`
- `outputs/debug/llm2_repair_request.json`
- `outputs/debug/llm2_repair_response.json`
- `outputs/debug/llm2_repair_status.json`
- `outputs/debug/llm3_schema_request.json`
- `outputs/debug/llm3_schema_response.json`
- `outputs/debug/phase2_retrieval_context_verbose.json`

The normal report includes repair status fields:

- `repair_stage_considered`
- `repair_stage_executed`
- `missing_requirements`
- `repaired_canonical_record_used`
- `repair_evidence_ids`
- `repair_stage_error`

## 20. What Is In `phase2_retrieval_context.json`?

Written by:

- `src/mvp/extraction/pipeline.py::_write_phase2_retrieval_context`

The default artifact is compact. It keeps top-level names but stores counts and samples instead of full long lists:

- `retrieval_queries_executed_per_block`
- `retrieved_evidence_ids_per_block`
- `llm2_input_evidence_ids_per_block`
- `canonical_design_record_path`
- model names and reasoning effort
- legacy-path flags
- extraction path

For each query entry, it keeps:

- `search_type`
- `query`
- `query_source`
- `retrieved_count`
- `sample_result_evidence_ids`
- optional Phase 1 metadata

## 21. What Is The Legacy Direct Prompt?

The legacy direct path is isolated under:

- `src/mvp/extraction/legacy/pipeline.py`
- `src/mvp/extraction/legacy/prompting.py`
- `src/mvp/prompts/legacy_direct_system.md`

It is not the default path. It runs only with `--legacy-direct-extraction`.

Legacy system prompt:

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

Legacy user prompt shape:

```text
Build a valid antenna_architecture_spec_mvp_v2 object.

Required top-level keys:
- schema_name
- schema_version
- document_context
- classification
- units
- parameters
- materials
- layers
- entities
- feeds
- instances
- quality
- evidence_used

Status values:
- extracted, partially_extracted, missing, assumed_local_origin

Document context:
{run_context}

Interpretation guidance (advisory, not ground truth):
{interpretation_note}

Retrieved evidence by block:
{evidence_by_block}
```

Legacy mode still has its own validation repair messages, but this path is separate from the current default `retrieval -> LLM2 -> optional repair -> LLM3` path.

## 22. What Are The Main Failure Points Today?

### Wrong dominant design

The dominant design is decided by LLM2 using the canonicalization prompt. Deterministic retrieval and Phase 1 can influence what evidence reaches LLM2, but there is no hard-coded final-design selector.

### Missing feed location or feed dimensions

The repair trigger detects missing feed location/dimensions and may attempt bounded retrieval. The final schema can still remain partial if the retrieved evidence does not cleanly support a schema-compatible field.

### Tables contain the answer but final schema misses it

LLM2 now receives full table rows and markdown for table evidence. The remaining risk is semantic: LLM2/repair/LLM3 must decide which rows matter and map them into the canonical record and final schema.

### Figure evidence is weak

The parser provides figure summaries and image artifacts, and retrieval can surface figure evidence. The extraction path does not run image vision. Figure content is caption/context based unless later code adds selected multimodal analysis.

### Repair fails or exceeds turns

Repair is optional. If repair fails, extraction continues with the initial canonical record and records the failure under `repair_stage_error`.

## 23. Current Validation Runs Referenced

Recent extraction validation was run on:

- `runs/run_20260421T091405157638Z`
- `runs/run_20260421T091437985264Z`
- `runs/run_20260421T091510556541Z`

All three completed with:

- `extraction_status = completed`
- `validation_success = true`

Repair was considered and executed in those runs. Repair evidence was merged into the valid evidence set before downstream validation/linking.

