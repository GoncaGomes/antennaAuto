# Current Extraction Pipeline: Detailed Q&A

Repository root used for this audit:

- `C:\Users\Lenovo\SynologyDrive\PhD\02.antennaAuto`

This document describes the current code and current validation artifacts as they exist today. When a behavior is not directly observable from saved artifacts, that is stated explicitly.

## 1. End-to-end flow

### CLI entrypoint to final output

**Exact file paths**

- `src/mvp/extract.py`
- `src/mvp/interpretation/pipeline.py`
- `src/mvp/extraction/pipeline.py`
- `src/mvp/bundle.py`

**Exact function names**

- `src/mvp/extract.py::main`
- `src/mvp/interpretation/pipeline.py::run_phase1`
- `src/mvp/extraction/pipeline.py::extract_run`
- `src/mvp/bundle.py::load_run_paths`
- `src/mvp/bundle.py::save_structured_output`

**Current behavior**

1. `python -m mvp.extract --run-dir <run_dir> --phase1-only`
   - enters `main`
   - calls `run_phase1`
   - writes:
     - `outputs/paper_map.json`
     - `outputs/interpretation_map.json`
     - `outputs/extraction_run_report.json`
   - stops

2. `python -m mvp.extract --run-dir <run_dir> --model gpt-4o`
   - enters `main`
   - calls `extract_run`
   - writes:
     - `outputs/antenna_architecture_spec_mvp_v2.json`
     - `outputs/extraction_run_report.json`
     - `outputs/phase2_retrieval_context.json`

3. `extract_run`
   - resolves paths with `load_run_paths`
   - validates that the run bundle and indexes already exist
   - loads Phase 1 guidance if present
   - runs second-stage deterministic retrieval
   - compacts evidence for the final prompt
   - calls the existing structured extraction path
   - applies deterministic post-checks and semantic validation
   - writes the final JSON and report

**Main orchestration point for Phase 1 plus second-stage extraction**

- There is no single current function that runs both phases in one continuous call.
- Current orchestration is split:
  - Phase 1 orchestration: `src/mvp/interpretation/pipeline.py::run_phase1`
  - Final extraction orchestration: `src/mvp/extraction/pipeline.py::extract_run`
- The current extraction CLI reuses Phase 1 artifacts from disk when `extract_run` executes.

**Exact point where Phase 1 begins influencing second-stage extraction**

Phase 1 starts influencing second-stage extraction inside:

- `src/mvp/extraction/pipeline.py::extract_run`

The influence begins at two specific points:

1. `phase1_guidance, interpretation_note = _load_phase1_guidance(run_paths, target_dir)`
   - loads `interpretation_map.json`
2. `gather_retrieval_context_with_phase1(..., phase1_search_queries=phase1_guidance.get("search_queries"))`
   - injects `interpretation_map.search_queries` into second-stage retrieval
3. `build_extraction_messages(..., interpretation_note=interpretation_note)`
   - adds a compact advisory note to the final extraction prompt with:
     - `has_multiple_variants`
     - `has_final_design_signal`
     - `open_uncertainties`

**Behavior type**

- CLI routing: deterministic code
- Phase 1 loading: deterministic code
- final schema generation: LLM behavior plus deterministic validation/post-processing
- output writing: deterministic code

## 2. Phase 1 integration

### Where `interpretation_map.search_queries` are loaded and injected

**Exact file paths**

- `src/mvp/extraction/pipeline.py`
- `src/mvp/extraction/agent.py`
- `src/mvp/schemas/interpretation_map.py`

**Exact function names**

- `src/mvp/extraction/pipeline.py::_load_phase1_guidance`
- `src/mvp/extraction/pipeline.py::extract_run`
- `src/mvp/extraction/agent.py::gather_retrieval_context_with_phase1`
- `src/mvp/extraction/agent.py::_normalize_phase1_search_queries`
- `src/mvp/extraction/agent.py::_block_query_entries`

**Current behavior**

- `_load_phase1_guidance` looks for `interpretation_map.json` under:
  - the target output directory
  - or the run’s default `outputs/`
- it validates the JSON with `validate_interpretation_map_payload`
- it returns:
  - the full interpretation payload as a dict
  - a compact `interpretation_note`

`interpretation_map.search_queries` are then passed to:

- `gather_retrieval_context_with_phase1(... phase1_search_queries=...)`

### How Phase 1 queries are merged with the base retrieval plan

**Exact file path**

- `src/mvp/extraction/agent.py`

**Exact function name**

- `_block_query_entries`

**Current merge logic**

- block base queries are added first
- then Phase 1 queries are appended for each search type already used by that block
- example:
  - if a block uses `text` and `tables`, each Phase 1 query is executed twice for that block:
    - once through `search_text`
    - once through `search_tables`
- deduplication key is:
  - `(query_source, search_type, query)`

That means:

- exact duplicate base-plan queries are removed
- exact duplicate Phase 1 queries within the same search type are removed
- a base query and a Phase 1 query with the same text are not treated as the same source

**Are Phase 1 queries appended, weighted, deduplicated, or conditional?**

- appended: yes
- weighted: no
- deduplicated: only exact duplicates by `(query_source, search_type, query)`
- conditional: no, if Phase 1 guidance exists they are executed for all compatible block search types

### Priority difference between base-plan and Phase 1 queries

**Current behavior**

- there is no ranking or weighting difference in retrieval candidate generation based on `query_source`
- both query families produce raw retrieval results
- candidates are deduplicated by `evidence_id` at the block level
- first-seen evidence survives if the same evidence appears again from a later query

This means the current ordering of executed queries matters for deduplication:

- base-plan queries run first
- Phase 1 queries run after base-plan queries
- if the same `evidence_id` is already seen from a base-plan query, the Phase 1 copy is skipped when building block records

### Where `SearchPriority.HIGH / MEDIUM / LOW` is used

**Exact file paths**

- `src/mvp/schemas/interpretation_map.py`
- `src/mvp/extraction/agent.py`
- `src/mvp/extraction/pipeline.py`
- `outputs/phase2_retrieval_context.json`

**Exact function names**

- `src/mvp/schemas/interpretation_map.py::SearchPriority`
- `src/mvp/extraction/agent.py::_normalize_phase1_search_queries`
- `src/mvp/extraction/agent.py::_block_query_entries`
- `src/mvp/extraction/pipeline.py::_write_phase2_retrieval_context`

**Current behavior**

- `SearchPriority` is preserved as metadata
- it is logged in:
  - `retrieval_queries_used`
  - `phase2_retrieval_context.json`
- it is not used in:
  - retrieval score computation
  - prompt packing
  - block ranking
  - post-processing

**Behavior type**

- loading, merging, logging: deterministic code
- semantic meaning of the queries: produced by Phase 1 LLM

## 3. Retrieval and candidate generation

### Query generation per block

**Exact file path**

- `src/mvp/extraction/agent.py`

**Exact function names**

- `RETRIEVAL_PLAN`
- `gather_retrieval_context_with_phase1`
- `_block_query_entries`
- `_dispatch_search`

**Current block query plan**

- `classification`
  - text: `antenna type`, `proposed design`, `final design`, `configuration`
- `materials`
  - text: `substrate material`, `dielectric material`, `conductor material`
  - tables: `material`
- `layers`
  - text: `layer stack`, `substrate thickness`, `metal thickness`, `ground plane`
  - tables: `thickness`
- `parameters`
  - tables: `dimensions`, `design parameters`
  - text: `geometrical parameters`, `table of dimensions`, `operating frequency`
- `entities`
  - text: `antenna geometry`, `radiating element`, `slot geometry`, `ground plane geometry`
  - figures: `antenna geometry`
- `feeds`
  - text: `feeding method`, `feed type`, `feed location`, `input port`, `input impedance`
- `quality`
  - text: `bandwidth`, `gain`, `return loss`, `reflection coefficient`, `VSWR`

With Phase 2 active, every Phase 1 search query is additionally run for the block’s existing search types.

### Retrieval sources used per block

**Exact file path**

- `src/mvp/retrieval.py`

**Exact function names**

- `search_text`
- `search_tables`
- `search_figures`

**Current per-source search boundary**

- `search_text`
  - allowed evidence types: `chunk`, `section`
- `search_tables`
  - allowed evidence type: `table`
- `search_figures`
  - allowed evidence type: `figure`

### Candidate ranking before prompt selection

**Exact file path**

- `src/mvp/retrieval.py`

**Exact function names**

- `_hybrid_search`
- `_normalize_scores`
- `_rank_map`
- `_rrf_component`

**Current ranking logic**

`_hybrid_search` computes:

1. BM25 results over the allowed evidence subset
2. dense vector results over the same evidence subset
3. final fused score

Supported fusion strategies in current code:

- `weighted`
  - `final_score = alpha * normalized_bm25 + beta * normalized_dense`
- `rrf`
  - `final_score = 1/(k + bm25_rank) + 1/(k + dense_rank)`

**Current sort key in retrieval**

- primary: higher fused `score`
- tie-break 1: earlier page
- tie-break 2: `source_id`

The return payload per retrieved result includes:

- `evidence_id`
- `source_type`
- `source_id`
- `page_number`
- `score`
- `snippet`
- `bm25_score`
- `dense_score`
- `bm25_rank`
- `dense_rank`
- `final_rank`
- metadata fields

### Explicit preference for table evidence in `parameters`

**Exact file path**

- `src/mvp/extraction/prompting.py`

**Exact function name**

- `_prompt_priority_score`

**Current behavior**

Yes. There is an explicit prompt-packing bonus for tables in the `parameters` block:

- if `source_type == "table"` then `+0.55`

Additional parameter-like wording bonus:

- if text contains terms like `dimension`, `parameter`, `length`, `width`, `radius`, `thickness`, etc. then `+0.25`

Comparison/reference-like penalty:

- if text contains `comparison table`, `literature work`, or `reference` then `-0.45`

### Explicit preference for figure evidence in `entities` or `feeds`

**Entities**

- yes, but smaller than the table bonus for parameters
- `_prompt_priority_score` gives `+0.12` to `source_type == "figure"`
- it also gives `+0.28` for geometry words such as:
  - `geometry`
  - `radiating element`
  - `slot`
  - `ground plane`
  - `rectangular`
  - `triangular`
  - `circular`

**Feeds**

- no explicit figure bonus exists
- feed scoring uses text-term bonus only:
  - `feed`, `feeding`, `input port`, `connector`, `port`, `input impedance`, `location`

### Deduplication location and key

**Exact file paths**

- `src/mvp/extraction/agent.py`
- `src/mvp/extraction/prompting.py`

**Exact function names**

- `gather_retrieval_context_with_phase1`
- `_compact_block_records`
- `_dedupe_signature`

**Current behavior**

1. Retrieval-stage dedupe
   - key: `evidence_id`
   - location: `gather_retrieval_context_with_phase1`
   - effect: only the first occurrence of an `evidence_id` per block survives into `evidence_by_block`

2. Prompt-stage dedupe
   - key: `_dedupe_signature(record)`
   - signature:
     - `type`
     - `page`
     - normalized title prefix
     - normalized excerpt prefix
   - effect: two different `evidence_id` values can still collapse if they normalize to the same prompt signature

**Behavior type**

- retrieval generation and ranking: deterministic code
- final field interpretation from prompt evidence: LLM behavior
## 4. Prompt evidence packing

### Which function converts retrieved evidence into `prompt_records`

**Exact file paths**

- `src/mvp/extraction/agent.py`
- `src/mvp/extraction/prompting.py`

**Exact function names**

- `src/mvp/extraction/agent.py::_build_prompt_record`
- `src/mvp/extraction/prompting.py::_compact_prompt_record`

**Current behavior**

`_build_prompt_record` creates the full retrieval-side record:

- `evidence_id`
- `source_type`
- `source_id`
- `page_number`
- `score`
- `snippet`
- `content`
- `source_payload`

Then `_compact_prompt_record` turns that into the smaller prompt-facing record:

- `evidence_id`
- `block`
- `type`
- `excerpt`
- optional `page`
- optional `score`
- optional `title`

### Which function decides `prompt_evidence_ids_per_block`

**Exact file paths**

- `src/mvp/extraction/prompting.py`
- `src/mvp/extraction/pipeline.py`

**Exact function names**

- `prepare_prompt_evidence`
- `_compact_block_records`
- `_build_report`
- `_write_phase2_retrieval_context`

**Current behavior**

The actual decision happens in:

- `prepare_prompt_evidence`
- `_compact_block_records`

The selected `evidence_id` values are then persisted into:

- `extraction_run_report.json`
- `phase2_retrieval_context.json`

### Logic that limits the number of prompt records per block

**Exact file path**

- `src/mvp/extraction/prompting.py`

**Exact function names**

- `DEFAULT_PROMPT_MAX_ITEMS_PER_BLOCK`
- `_compact_block_records`
- `_trim_lowest_priority_item`

**Current per-block caps**

- `classification`: 2
- `materials`: 2
- `quality`: 2
- `entities`: 3
- `feeds`: 3
- `layers`: 3
- `parameters`: 4

There is also a global character budget:

- `DEFAULT_PROMPT_CHAR_BUDGET = 40_000`

If the prompt exceeds budget:

- `_trim_lowest_priority_item` removes records from blocks with more than one record
- the record removed is the last item in the already-sorted block list

### When both a table and prose describe the same parameter

**Current decision logic**

The code does not directly decide “same parameter” semantically at prompt packing time.

It only sorts individual records by:

1. `_prompt_priority_score`
2. retrieval `score`
3. `page_number`
4. `evidence_id`

For the `parameters` block this makes tables more likely to survive because they get:

- a larger explicit source-type bonus
- a larger excerpt limit

But the decision is still record-level, not parameter-object-level.

### Are prompt records scored only by retrieval rank?

No.

They are ranked by a mix of:

- retrieval `score`
- evidence type
- block-specific term bonuses and penalties
- page order

They are not ranked by:

- Phase 1 priority
- query source (`base_plan` vs `phase1_interpretation_map`)

### Why a table can be retrieved and logged but not survive into `prompt_evidence_ids_per_block`

This happens when:

- the table is retrieved into `retrieval_queries_used`
- but another record ranks higher under `_record_sort_key`
- or another record collapses it by prompt dedupe signature
- or prompt budget trimming removes it

So the retrieval log and the prompt evidence list represent different pipeline stages.

**Behavior type**

- prompt record construction and compaction: deterministic code
- interpretation of surviving evidence into schema fields: LLM behavior

## 5. Final-design resolution

### Is there code that explicitly distinguishes design stage types?

**Exact file paths**

- `src/mvp/extraction/prompting.py`
- `src/mvp/interpretation/discovery.py`
- `src/mvp/interpretation/prompting.py`

**Exact function names**

- `src/mvp/extraction/prompting.py::_prompt_priority_score`
- `src/mvp/interpretation/discovery.py::_select_candidate_design_mentions`
- `src/mvp/interpretation/prompting.py::build_interpretation_messages`

**Current behavior**

There is no deterministic final-stage resolver in the final extraction pipeline that explicitly labels evidence as:

- early design
- intermediate design step
- final/optimized/fabricated design
- contextual or deployment discussion

What does exist:

1. prompt-side hints in `SYSTEM_PROMPT`
   - “avoid mixing design variants”
   - “prefer the final, proposed, optimized, selected, or best-supported design”
2. classification prompt-priority boost for terms such as:
   - `proposed design`
   - `final design`
   - `optimized design`
   - `configuration`
3. Phase 1 interpretation note
   - `has_multiple_variants`
   - `has_final_design_signal`
   - `open_uncertainties`

These are advisory signals. They do not deterministically resolve the final design.

### Is the choice of final design mostly left to the LLM?

Yes.

Current code uses:

- deterministic retrieval and prompt packing
- deterministic advisory note
- then the LLM chooses what design variant the final schema represents

### Is there deterministic preference for final parameter tables over earlier prose?

No.

There is:

- table preference in prompt packing for `parameters`
- generic wording hints

There is not:

- deterministic “final table” detection
- deterministic “prefer final-stage table over earlier prose” logic

**Behavior type**

- retrieval/prompt hints: deterministic code
- final design choice: primarily LLM behavior

## 6. Entity construction and parameter binding

### Which function builds the final `entities` array

There is no single deterministic function that builds the full `entities` array from scratch.

**Current behavior**

- the LLM produces the initial `entities` array under the `AntennaArchitectureSpecMvpV2` schema
- deterministic post-processing then modifies it

**Exact file paths**

- `src/mvp/extraction/pipeline.py`
- `src/mvp/schemas/extraction_spec.py`

**Exact function names**

- `extract_run`
- `_apply_semantic_post_checks`
- `_fill_main_entity_shape`
- `_attach_entity_dimensions`
- `_bind_structural_parameters`
- `_bind_parameter_to_entity_geometry`

### Which function maps scalar parameters to entity geometry

**Exact file path**

- `src/mvp/extraction/pipeline.py`

**Exact function names**

- `_attach_entity_dimensions`
- `_bind_structural_parameters`
- `_bind_parameter_to_entity_geometry`

**Current behavior**

1. `_attach_entity_dimensions`
   - patch-only fallback
   - attaches `length`, `width`, `radius` from matching parameters if:
     - `entity_type == "patch"`
     - matching semantic/symbol aliases are found

2. `_bind_structural_parameters`
   - classifies every parameter with `classify_parameter_payload`
   - dispatches to:
     - `_bind_parameter_to_entity_geometry`
     - `_bind_parameter_to_layer`
     - `_bind_parameter_to_feed`

3. `_bind_parameter_to_entity_geometry`
   - finds a target entity by semantic role hint
   - binds only when `classification.property_hint` is not `None` and not `"dimension"`

### Is there a deterministic post-binding step after LLM output?

Yes.

That deterministic post-binding lives inside:

- `_apply_semantic_post_checks`

### Why a parameter can appear in `parameters` but fail to appear in an entity or feed

This occurs when any of these conditions happen:

- the LLM kept the value as a global parameter and did not place it structurally
- `classify_parameter_payload` returns `unknown` or low-confidence non-structural
- the target entity cannot be found
- `property_hint == "dimension"` so `_bind_parameter_to_entity_geometry` exits early
- `_bind_parameter_to_feed` currently only supports `reference_impedance`
- feed position or feedline dimensions have no deterministic feed-object binding path

**Concrete current example: slot radius**

- file: `runs/run_20260407T163054725157Z/outputs/antenna_architecture_spec_mvp_v2.json`
- parameter exists:
  - `param_radiusofcircularslot`
- final slot entity exists:
  - `entity_2`
- slot dimensions array is empty

Current likely code reason:

- `semantic_name = "radiusofcircularslot"`
- `classify_parameter_payload` token matching expects separated keywords
- `radiusofcircularslot` is not split into `radius` + `slot`
- classification therefore does not reliably produce `target_hint="slot", property_hint="radius"`
- no deterministic structural binding occurs

### How the code decides `entity_type` and `shape_mode`

**Current behavior**

- primarily decided by the LLM
- deterministic shape fill is limited

**Exact function names**

- `_fill_main_entity_shape`
- `_find_target_entity`

`_fill_main_entity_shape` currently:

- only tries to set `shape_mode` if it is missing or generic
- scans text for:
  - `rectangular`
  - `triangular`
  - `circular`

`_find_target_entity` maps target hints to acceptable role/entity-type sets:

- `patch` -> `patch`, `radiator`, `radiating_element`
- `slot` -> `slot`, `notch`, `aperture`
- `ground` -> `ground`, `ground_plane`

### Deterministic mapping from phrases to schema-level shapes/entity types

Only partially.

There is some deterministic normalization for:

- shape words:
  - `rectangular`
  - `triangular`
  - `circular`
- target matching:
  - patch/radiator/radiating element
  - slot/notch/aperture
  - ground/ground plane

There is no broad deterministic mapper for phrases such as:

- `triangular patch`
- `circular slot`
- `partial ground plane`

into a complete schema object beyond those limited shape and target hints.

**Behavior type**

- base entity creation: LLM behavior
- post-binding and shape fill: deterministic post-processing
## 7. Feed extraction

### Which function builds the `feeds` block

There is no deterministic constructor for the full `feeds` block.

**Current behavior**

- the LLM creates `feeds`
- deterministic post-processing enriches some missing details

**Exact file paths**

- `src/mvp/extraction/pipeline.py`
- `src/mvp/schemas/extraction_spec.py`

**Exact function names**

- `_apply_semantic_post_checks`
- `_enrich_feed_details`
- `_bind_parameter_to_feed`

### How `feed_family` is inferred

**Current behavior**

- mostly by the LLM from the prompt evidence
- there is no deterministic post-processing function that derives `feed_family` from scratch

### How `matching_style` is inferred

**Exact function name**

- `_find_matching_style`

**Current logic**

- if the current `matching_style` is empty or generic:
  - `inset` in text -> `inset`
  - `edge feed` or `edge-fed` -> `edge`
  - `apex` -> `apex`
  - `coaxial` or `probe feed` -> `probe`

### Code that binds feedline dimensions or feed coordinates

**Feedline dimensions**

- no deterministic binding from parameter list into `FeedSpec`

**Feed coordinates**

- `_find_feed_location` can detect text patterns such as:
  - `feeding location of X mm by Y mm`
  - `feed point ... X mm by Y mm`
- but `_enrich_feed_details` only applies this when:
  - `feed_family == "coaxial"`

Even then, the coordinates are written as global parameters:

- `feed_location_x`
- `feed_location_y`

They are not written into `FeedSpec`.

### For probe-fed antennas, where should X/Y feed position be extracted and stored?

**Current schema reality**

- current code stores them only as global parameters if coaxial feed location is found
- `FeedSpec` has no explicit coordinate fields

### Can the schema represent microstrip-line feed geometry and coaxial probe coordinates cleanly?

**Microstrip-line geometry**

- only indirectly
- the prompt requires microstrip feed lines to be represented as entities when dimensions are available

**Coaxial probe coordinates**

- not cleanly inside `FeedSpec`
- only as global parameters under current post-processing

**Behavior type**

- base feed creation: LLM behavior
- impedance/matching-style/location enrichment: deterministic post-processing

## 8. Tables

### How table rows/columns are represented before prompting

**Exact file paths**

- `src/mvp/extraction/agent.py`
- `src/mvp/extraction/prompting.py`

**Exact function names**

- `_compact_source_payload`
- `_build_excerpt_for_block`

**Current behavior**

Before prompt serialization, a table record keeps:

- `table_id`
- `caption`
- `page_number`
- `rows`
- `structured`

The `rows` field is preserved as a list of row arrays, up to 12 rows.

### Are tables flattened or preserved?

Both, at different stages.

- retrieval-side prompt record:
  - structured rows are still preserved in `source_payload["rows"]`
- prompt-side excerpt:
  - rows are flattened to text

### Which function transforms table JSON into prompt text

**Exact function name**

- `_build_excerpt_for_block`

**Current logic**

- take `caption`
- take up to:
  - 8 rows for `parameters`
  - 5 rows for `layers` and `feeds`
  - 4 rows otherwise
- each row becomes:
  - `"cell1 | cell2 | cell3"`
- rows are joined with:
  - `"; "`

### Does the pipeline preserve column identity, row identity, and step semantics?

Only partially, before prompt flattening.

What is preserved:

- row order
- cell order within each row
- table caption

What is lost at prompt serialization:

- explicit named column identity as structured keys
- explicit row identity as labeled objects
- explicit step/column semantics beyond whatever text survives in the flattened row strings

### Deterministic identification of final column or final step

No.

There is no current deterministic code that:

- identifies the final column
- identifies the final step
- chooses the winning configuration in iterative design tables

**Behavior type**

- table packaging: deterministic code
- final semantic interpretation of table contents: LLM behavior

## 9. Quality and build readiness

### Which function computes the final `quality` block and `build_readiness`

**Exact file path**

- `src/mvp/extraction/pipeline.py`

**Exact function names**

- `_refresh_quality`
- `_structural_binding_issues`

**Current behavior**

`quality` is initially produced by the LLM.

Then `_refresh_quality` post-processes it by:

- removing stale missing items if units/geometry/impedance are now present
- appending missing items from `_structural_binding_issues`
- appending ambiguities from `_structural_binding_issues`
- downgrading `build_readiness` from `ready` to `partial` if `major_geometry_gap` is true

### Exact conditions that produce `build_readiness = "partial"`

Current deterministic code only explicitly forces:

- `ready -> partial` if `_structural_binding_issues(...).major_geometry_gap` is true

In many current runs, `partial` is already produced by the LLM before post-processing.

### Why `missing_required_for_build` can claim fields are missing even when values appear elsewhere

Because the check is structural, not just lexical.

Examples:

- a value may exist in `parameters` but not be bound into the relevant entity/layer/feed object
- a patch may have dimensions, but a required slot or feed position may still be unbound
- a ground entity may exist, but its dimensions may still be empty

### Deterministic validation of CST sufficiency

No.

Current deterministic validation checks:

- schema validity
- semantic binding consistency
- structural presence for some bound dimensions and layer thicknesses

It does not validate whether the architecture is actually sufficient to reconstruct in CST.

**Behavior type**

- base `quality` content: LLM behavior
- refinement and downgrade logic: deterministic post-processing

## 10. Schema and post-validation

### Where `antenna_architecture_spec_mvp_v2` is defined

**Exact file path**

- `src/mvp/schemas/extraction_spec.py`

**Exact class name**

- `AntennaArchitectureSpecMvpV2`

### Required vs optional fields

**Required top-level fields**

- `schema_name`
- `schema_version`
- `document_context`
- `classification`
- `units`
- `quality`

The following top-level fields are present but default to empty lists:

- `parameters`
- `materials`
- `layers`
- `entities`
- `feeds`
- `instances`
- `evidence_used`

Nested fields vary by class. Many are optional but become required when `status != "missing"`.

### Validators enforcing consistency between parameters, entities, feeds, and layers

**Exact function names**

- `AntennaArchitectureSpecMvpV2.validate_consistency`
- `validate_semantic_bindings`

**Current consistency checks**

- all internal IDs must match `^[a-z][a-z0-9_]*$`
- all evidence IDs must match `^[a-z_]+:[A-Za-z0-9_]+$`
- IDs within each collection must be unique
- `layer.material_ref` must exist
- `entity.layer_ref` and `entity.material_ref` must exist
- `geometry.dimension.param_ref` must reference an existing parameter
- `feed.driven_entity_ref` must reference an existing entity
- `instance.entity_ref` must reference an existing entity
- all nested `evidence_ids` must also appear in top-level `evidence_used`
- `validate_semantic_bindings` rejects orphaned high-confidence structural parameters when a matching target object exists

### Post-processing that normalizes duplicates or resolves synonymous fields

There is no general synonym resolver or duplicate-parameter normalizer.

There is:

- ID-level dedupe for some evidence lists
- semantic validation for structural bindings

There is not:

- a deterministic reconciliation pass that merges synonymous parameters

### Why duplicate parameters appear

Because parameters can come from more than one path:

1. LLM-generated parameters
2. deterministic table enrichment in `_enrich_parameters_from_tables`

The table-enrichment identity key is:

- `(symbol or "", semantic_name, str(value))`

So two parameters with the same value and evidence can still survive if they differ in `semantic_name`.

**Current concrete example**

`runs/run_20260407T162957585563Z/outputs/antenna_architecture_spec_mvp_v2.json`

- `param_lpat` with `semantic_name = "Patch Length"`
- `param_lpat_2` with `semantic_name = "lpat"`

Both point to the same table evidence and value, but they are treated as distinct parameters.

**Behavior type**

- schema definition and validators: deterministic code
- duplicate creation: mixed LLM output plus deterministic table enrichment
## 11. Observability and debugging

### Where `query_usefulness_per_block` is computed

**Exact file path**

- `src/mvp/extraction/pipeline.py`

**Exact function name**

- `_build_query_usefulness_by_block`

### How `contributed_to_bound_structural_field` is determined

**Exact function names**

- `_build_query_usefulness_by_block`
- `_collect_structural_bound_evidence_ids`

**Current logic**

1. `_collect_structural_bound_evidence_ids(spec)` gathers evidence IDs used by:
   - entity geometry dimensions
   - layer thickness
   - feed reference impedance
2. `_build_query_usefulness_by_block` intersects each query’s retrieved evidence IDs with that set
3. `contributed_to_bound_structural_field = bool(structural_hits)`

### Concrete end-to-end traces

The current saved artifacts do not include raw prompt messages or raw LLM response payloads unless extraction is run with `--debug`. The traces below therefore show:

- retrieval query
- retrieved evidence IDs
- prompt survival
- final schema field
- deterministic post-binding if observable
- and explicitly note where the raw LLM field is not directly observable

#### 11.1 Finalized patch dimensions

**Concrete current example**

- run: `runs/run_20260407T162957585563Z`
- paper: `article.pdf`

**Retrieval query**

- base block: `parameters`
- queries include:
  - `tables -> dimensions`
  - `tables -> design parameters`
  - Phase 1 query `Dimensions of proposed antenna` executed against tables and text

**Retrieved evidence IDs**

- `phase2_retrieval_context.json`
- `parameters` prompt evidence includes:
  - `table:table_001`
  - `chunk:chunk_028`
  - `chunk:chunk_038`
  - `chunk:chunk_036`

**Prompt survival**

- `table:table_001` survives into `prompt_evidence_ids_per_block.parameters`

**LLM output field**

- not directly observable from saved artifacts, because the raw model response was not persisted for this run

**Post-binding into final schema**

- final spec:
  - `entities[entity_patch].geometry.dimensions`
  - `length -> param_lpat -> evidence_ids [table:table_001]`
  - `width -> param_wpat -> evidence_ids [table:table_001]`

**Evidence ID flow**

- retrieval result -> prompt record -> `table:table_001`
- final parameter objects cite `table:table_001`
- final entity geometry dimensions cite `table:table_001`
- top-level `evidence_used` includes `table:table_001`

#### 11.2 Feed position

**Concrete current example**

- run: `runs/run_20260407T163054725157Z`
- paper: `engproc-46-00010.pdf`

**Retrieval query**

- base block: `feeds`
- queries include:
  - `feed location`
  - `feed type`
  - `feeding method`
  - plus Phase 1 search queries such as `Step 4 circular slot into the triangle patch`

**Retrieved evidence IDs**

- `phase2_retrieval_context.json`
- `prompt_evidence_ids_per_block.feeds`
  - `chunk:chunk_028`
  - `chunk:chunk_030`
  - `chunk:chunk_010`

**Prompt survival**

- those three survive into the feeds prompt block

**LLM output field**

- raw model feed field not directly observable for this run

**Post-binding into final schema**

- final `feeds[0]`
  - `feed_family = "microstrip"`
  - `matching_style = "altered_position"`
  - no coordinates
- final `quality.missing_required_for_build`
  - includes `feed position details`

**Current deterministic reason coordinates are not added**

- `_bind_parameter_to_feed` only binds `reference_impedance`
- `_find_feed_location` only writes global `feed_location_x` / `feed_location_y` parameters if `feed_family == "coaxial"`
- this final feed family is `microstrip`, so that deterministic path does not apply

#### 11.3 Ground-plane dimensions

**Concrete current example**

- run: `runs/run_20260407T163130273344Z`
- paper: `IJETT-V4I4P340.pdf`

**Retrieval query**

- base block: `entities`
- query:
  - `ground plane geometry`
- Phase 1 query:
  - `partial ground plane`

**Retrieved evidence IDs**

- `phase2_retrieval_context.json`
- `ground plane geometry` returns:
  - `chunk:chunk_028`
  - `section:page_003`
  - `chunk:chunk_046`
  - `chunk:chunk_010`
  - `chunk:chunk_013`

**Prompt survival**

- `prompt_evidence_ids_per_block.entities`
  - `chunk:chunk_008`
  - `chunk:chunk_028`
  - `chunk:chunk_010`

`chunk:chunk_028` survives, so ground-plane-related evidence reaches the final prompt.

**LLM output field**

- raw model entity field not directly observable

**Post-binding into final schema**

- final `entity_2`
  - `entity_type = "ground_plane"`
  - `role = "ground"`
  - `geometry.dimensions = []`

**Observed result**

- ground-plane existence survives
- ground-plane dimensions do not appear in the final schema

#### 11.4 Slot dimensions

**Concrete current example**

- run: `runs/run_20260407T163054725157Z`
- paper: `engproc-46-00010.pdf`

**Retrieval query**

- base block: `entities`
  - `slot geometry`
- base block: `parameters`
  - `tables -> dimensions`
  - `tables -> design parameters`

**Retrieved evidence IDs**

- `phase2_retrieval_context.json`
- `prompt_evidence_ids_per_block.parameters`
  - includes `table:table_001`

**Prompt survival**

- the slot-related table survives into the parameters prompt block

**LLM output field**

- raw model slot field not directly observable

**Post-binding into final schema**

- final parameter exists:
  - `param_radiusofcircularslot`
  - `value = 3`
  - `evidence_ids = [table:table_001]`
- final slot entity exists:
  - `entity_2`
  - `shape_mode = circular`
  - `geometry.dimensions = []`

**Observed reason in current deterministic code**

- `_bind_parameter_to_entity_geometry` would bind a slot radius only if classification returns:
  - `role = entity_geometry`
  - `target_hint = slot`
  - `property_hint = radius`
- current parameter text is `radiusofcircularslot`
- the keyword classifier relies on normalized token boundaries
- that packed token is not deterministically split into separate `radius` and `slot` tokens
- therefore the parameter can remain global and unbound

## 12. Most likely failure points

This section answers the user’s question about the current code locations that most likely control the observed failure modes. This is not a redesign proposal; it is a statement of the current most influential locations.

### 12.1 Wrong design stage is chosen

**Most likely current code locations**

1. `src/mvp/extraction/prompting.py::_prompt_priority_score`
   - this is where prompt evidence gets stage-like text bonuses such as:
     - `proposed design`
     - `final design`
     - `optimized design`
     - `configuration`
   - it shapes which records survive into the final prompt

2. `src/mvp/extraction/prompting.py::SYSTEM_PROMPT`
   - this is where the final extractor is instructed to:
     - avoid mixing design variants
     - prefer final/proposed/optimized/selected/best-supported design

3. `src/mvp/extraction/pipeline.py::extract_run`
   - through `build_extraction_messages(... interpretation_note=...)`
   - this is where Phase 1’s advisory note reaches the final prompt

**Current behavior type**

- mixed:
  - deterministic retrieval/prompt shaping
  - final design choice by LLM

### 12.2 Table values are not preferred over prose

**Most likely current code locations**

1. `src/mvp/extraction/prompting.py::_prompt_priority_score`
   - this is the main explicit source-type preference layer
   - tables get strong preference only in certain blocks

2. `src/mvp/extraction/prompting.py::_compact_block_records`
   - this is where the actual capped prompt survivors are chosen

3. `src/mvp/extraction/prompting.py::_build_excerpt_for_block`
   - this is where structured table rows are flattened before the LLM sees them

**Current behavior type**

- deterministic prompt evidence selection and formatting
- LLM interpretation after the table is flattened

### 12.3 Parameters are extracted but not bound to physical entities

**Most likely current code locations**

1. `src/mvp/semantic_roles.py::classify_parameter_payload`
   - determines whether a parameter is treated as:
     - `entity_geometry`
     - `layer_property`
     - `feed_property`
     - `global_metric`
     - `unknown`

2. `src/mvp/extraction/pipeline.py::_bind_parameter_to_entity_geometry`
   - binds classified structural parameters into entity geometry
   - exits early when:
     - no target entity is found
     - `property_hint` is missing
     - `property_hint == "dimension"`

3. `src/mvp/extraction/pipeline.py::_bind_parameter_to_feed`
   - only handles `reference_impedance`
   - does not bind feedline dimensions or feed coordinates

**Current behavior type**

- deterministic post-processing

## Summary of evidence ID flow

The core evidence-ID path is:

1. retrieval result from `search_text` / `search_tables` / `search_figures`
   - includes `evidence_id`
2. `gather_retrieval_context_with_phase1`
   - stores it in:
     - `retrieval_queries_used`
     - `evidence_ids_by_block`
     - `evidence_by_block`
3. `prepare_prompt_evidence`
   - selects a subset into `prompt_evidence_ids_per_block`
4. final LLM extraction
   - must only emit evidence IDs already present in the prompt
5. post-processing
   - propagates those IDs into:
     - nested field `evidence_ids`
     - top-level `evidence_used`
6. final validation
   - rejects any nested evidence IDs not present in top-level `evidence_used`

## Current validation artifacts referenced in this document

- `runs/run_20260407T162957585563Z/outputs/phase2_retrieval_context.json`
- `runs/run_20260407T162957585563Z/outputs/antenna_architecture_spec_mvp_v2.json`
- `runs/run_20260407T163054725157Z/outputs/phase2_retrieval_context.json`
- `runs/run_20260407T163054725157Z/outputs/antenna_architecture_spec_mvp_v2.json`
- `runs/run_20260407T163130273344Z/outputs/phase2_retrieval_context.json`
- `runs/run_20260407T163130273344Z/outputs/antenna_architecture_spec_mvp_v2.json`
