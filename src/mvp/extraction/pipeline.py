from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from ..bundle import load_run_paths, save_structured_output
from ..interpretation.pipeline import extract_existing_phase1_payload
from ..llm.client import OpenAIAgentsStructuredClient, StructuredGenerationResult
from ..retrieval import BundleRetriever
from ..schemas.canonical_design_record import CanonicalDesignRecord, collect_canonical_evidence_ids
from ..schemas.extraction_spec import AntennaArchitectureSpecMvpV2, collect_nested_evidence_ids
from ..schemas.interpretation_map import validate_interpretation_map_payload
from ..utils import ensure_dir, read_json, utc_timestamp, write_json
from .agent import gather_retrieval_context_with_phase1
from .prompting import (
    build_canonicalization_input,
    build_schema_construction_input,
)

DEFAULT_LEGACY_MODEL = "gpt-4o"
DEFAULT_LLM2_MODEL = "gpt-5.4-mini"
DEFAULT_LLM3_MODEL = "gpt-5.4-mini"
DEFAULT_AGENTS_REASONING_EFFORT = "medium"
DEFAULT_STRUCTURED_MAX_ATTEMPTS = 3


def extract_run(
    run_dir: str | Path,
    model: str = DEFAULT_LEGACY_MODEL,
    top_k: int = 5,
    output_dir: str | Path | None = None,
    debug: bool = False,
    llm_client: Any | None = None,
    legacy_direct: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if legacy_direct:
        from .legacy.pipeline import _extract_run_legacy_direct

        return _extract_run_legacy_direct(
            run_dir=run_dir,
            model=model,
            top_k=top_k,
            output_dir=output_dir,
            debug=debug,
            llm_client=llm_client,
        )
    return _extract_run_multistage(
        run_dir=run_dir,
        top_k=top_k,
        output_dir=output_dir,
        debug=debug,
        llm_client=llm_client,
    )


def _extract_run_multistage(
    *,
    run_dir: str | Path,
    top_k: int,
    output_dir: str | Path | None,
    debug: bool,
    llm_client: Any | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    run_paths = load_run_paths(Path(run_dir))
    _validate_run_inputs(run_paths)
    retriever = BundleRetriever(run_paths.run_dir)
    target_dir = ensure_dir(Path(output_dir)) if output_dir else ensure_dir(run_paths.outputs_dir)
    debug_dir = ensure_dir(target_dir / "debug") if debug else None
    phase1_payload = extract_existing_phase1_payload(target_dir / "extraction_run_report.json")
    if phase1_payload is None and target_dir != run_paths.outputs_dir:
        phase1_payload = extract_existing_phase1_payload(run_paths.extraction_report_path)
    phase1_guidance, _ = _load_phase1_guidance(run_paths, target_dir)
    retrieval_context = gather_retrieval_context_with_phase1(
        retriever,
        top_k=top_k,
        phase1_search_queries=(phase1_guidance.get("search_queries") if phase1_guidance else None),
    )
    llm2_input_evidence_by_block = _prepare_llm2_evidence_by_block(retrieval_context["evidence_by_block"])
    client = llm_client or OpenAIAgentsStructuredClient.from_env()

    warnings: list[str] = []
    canonical_design_record_path = target_dir / "canonical_design_record.json"
    phase2_artifact_path = target_dir / "phase2_retrieval_context.json"
    attempt_count = 0
    stage = "retrieval"

    try:
        llm2_request = build_canonicalization_input(
            retrieval_context["run_context"],
            llm2_input_evidence_by_block,
            phase1_guidance=phase1_guidance,
        )
        if debug_dir is not None:
            write_json(debug_dir / "llm2_canonicalization_request.json", llm2_request)

        stage = "llm2"
        llm2_result = _generate_agents_structured(
            client,
            agent_name="phase2_canonicalization",
            model=DEFAULT_LLM2_MODEL,
            reasoning_effort=DEFAULT_AGENTS_REASONING_EFFORT,
            request=llm2_request,
            response_model=CanonicalDesignRecord,
        )
        attempt_count = 1
        if debug_dir is not None:
            write_json(
                debug_dir / "llm2_canonicalization_response.json",
                {"raw_text": llm2_result.raw_text, "parsed": llm2_result.parsed.model_dump(exclude_none=True)},
            )
        canonical_record = _validate_canonical_generation(llm2_result.parsed, retrieval_context)
        write_json(canonical_design_record_path, canonical_record.to_clean_dict())

        linked_evidence_records = _build_linked_evidence_records(canonical_record, retrieval_context["evidence_by_block"])
        llm3_request = build_schema_construction_input(
            retrieval_context["run_context"],
            canonical_record.to_clean_dict(),
            linked_evidence_records,
        )
        if debug_dir is not None:
            write_json(debug_dir / "llm3_schema_request.json", llm3_request)

        stage = "llm3"
        llm3_result = _generate_agents_structured(
            client,
            agent_name="phase3_schema_construction",
            model=DEFAULT_LLM3_MODEL,
            reasoning_effort=DEFAULT_AGENTS_REASONING_EFFORT,
            request=llm3_request,
            response_model=AntennaArchitectureSpecMvpV2,
        )
        attempt_count = 2
        if debug_dir is not None:
            write_json(
                debug_dir / "llm3_schema_response.json",
                {"raw_text": llm3_result.raw_text, "parsed": llm3_result.parsed.model_dump(exclude_none=True)},
            )
        spec = _validate_generation(llm3_result.parsed, retrieval_context)
        spec = _apply_minimal_cleanup(spec)
        spec = _validate_generation(spec, retrieval_context)
    except Exception as exc:
        extraction_status = {
            "retrieval": "failed_retrieval",
            "llm2": "failed_llm2_canonicalization",
            "llm3": "failed_llm3_schema_extraction",
        }.get(stage, "failed_extraction")
        _write_phase2_retrieval_context(
            phase2_artifact_path=phase2_artifact_path,
            retrieval_context=retrieval_context,
            phase1_guidance=phase1_guidance,
            llm2_input_evidence_by_block=llm2_input_evidence_by_block,
            extraction_path="retrieval_llm2_llm3",
            canonical_design_record_path=(str(canonical_design_record_path) if canonical_design_record_path.exists() else None),
            llm2_model_name=DEFAULT_LLM2_MODEL,
            llm3_model_name=DEFAULT_LLM3_MODEL,
            llm2_reasoning_effort=DEFAULT_AGENTS_REASONING_EFFORT,
            llm3_reasoning_effort=DEFAULT_AGENTS_REASONING_EFFORT,
            legacy_direct_path_used=False,
            legacy_model_name=None,
        )
        report = _build_report(
            run_paths=run_paths,
            extraction_path="retrieval_llm2_llm3",
            validation_success=False,
            extraction_status=extraction_status,
            schema_errors=_error_payload(exc),
            warnings=warnings,
            retrieval_context=retrieval_context,
            prompt_evidence_by_block=llm2_input_evidence_by_block,
            final_evidence_ids_used=[],
            structural_bound_evidence_ids=[],
            attempt_count=attempt_count,
            prompt_budget={},
            phase1_payload=phase1_payload,
            llm2_model_name=DEFAULT_LLM2_MODEL,
            llm3_model_name=DEFAULT_LLM3_MODEL,
            llm2_reasoning_effort=DEFAULT_AGENTS_REASONING_EFFORT,
            llm3_reasoning_effort=DEFAULT_AGENTS_REASONING_EFFORT,
            canonical_design_record_path=(str(canonical_design_record_path) if canonical_design_record_path.exists() else None),
            legacy_direct_path_used=False,
            legacy_model_name=None,
        )
        write_json(target_dir / "extraction_run_report.json", report)
        raise RuntimeError(
            f"Extraction failed during {stage}. See report at {target_dir / 'extraction_run_report.json'}"
        ) from exc

    spec_json = spec.to_clean_dict()
    _write_phase2_retrieval_context(
        phase2_artifact_path=phase2_artifact_path,
        retrieval_context=retrieval_context,
        phase1_guidance=phase1_guidance,
        llm2_input_evidence_by_block=llm2_input_evidence_by_block,
        extraction_path="retrieval_llm2_llm3",
        canonical_design_record_path=str(canonical_design_record_path),
        llm2_model_name=DEFAULT_LLM2_MODEL,
        llm3_model_name=DEFAULT_LLM3_MODEL,
        llm2_reasoning_effort=DEFAULT_AGENTS_REASONING_EFFORT,
        llm3_reasoning_effort=DEFAULT_AGENTS_REASONING_EFFORT,
        legacy_direct_path_used=False,
        legacy_model_name=None,
    )
    report = _build_report(
        run_paths=run_paths,
        extraction_path="retrieval_llm2_llm3",
        validation_success=True,
        extraction_status="completed",
        schema_errors=[],
        warnings=warnings,
        retrieval_context=retrieval_context,
        prompt_evidence_by_block=llm2_input_evidence_by_block,
        final_evidence_ids_used=spec.evidence_used,
        structural_bound_evidence_ids=[],
        attempt_count=attempt_count,
        prompt_budget={},
        phase1_payload=phase1_payload,
        llm2_model_name=DEFAULT_LLM2_MODEL,
        llm3_model_name=DEFAULT_LLM3_MODEL,
        llm2_reasoning_effort=DEFAULT_AGENTS_REASONING_EFFORT,
        llm3_reasoning_effort=DEFAULT_AGENTS_REASONING_EFFORT,
        canonical_design_record_path=str(canonical_design_record_path),
        legacy_direct_path_used=False,
        legacy_model_name=None,
    )
    save_structured_output(run_paths.run_dir, spec_json, report, output_dir=target_dir)
    return spec_json, report


def _load_phase1_guidance(run_paths, target_dir: Path) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    candidate_paths = [target_dir / "interpretation_map.json"]
    if target_dir != run_paths.outputs_dir:
        candidate_paths.append(run_paths.outputs_dir / "interpretation_map.json")

    for path in candidate_paths:
        if not path.exists():
            continue
        try:
            interpretation_map = validate_interpretation_map_payload(read_json(path))
        except Exception:
            continue
        guidance = interpretation_map.model_dump(exclude_none=True)
        note = {
            "has_multiple_variants": interpretation_map.has_multiple_variants,
            "has_final_design_signal": interpretation_map.has_final_design_signal,
            "open_uncertainties": interpretation_map.open_uncertainties[:5],
        }
        guidance["interpretation_map_path"] = str(path)
        return guidance, note
    return None, None


def _write_phase2_retrieval_context(
    *,
    phase2_artifact_path: Path,
    retrieval_context: dict[str, Any],
    phase1_guidance: dict[str, Any] | None,
    llm2_input_evidence_by_block: dict[str, list[dict[str, Any]]],
    extraction_path: str,
    canonical_design_record_path: str | None,
    llm2_model_name: str | None,
    llm3_model_name: str | None,
    llm2_reasoning_effort: str | None,
    llm3_reasoning_effort: str | None,
    legacy_direct_path_used: bool,
    legacy_model_name: str | None,
) -> None:
    payload = {
        "phase1_guidance_found": bool(phase1_guidance),
        "phase1_interpretation_map_path": phase1_guidance.get("interpretation_map_path") if phase1_guidance else None,
        "phase1_search_queries_used": [
            {
                "query_id": query.get("query_id"),
                "query_text": query.get("query_text"),
                "priority": query.get("priority"),
            }
            for query in retrieval_context.get("phase1_search_queries_used", [])
        ],
        "retrieval_queries_executed_per_block": retrieval_context["retrieval_queries_used"],
        "retrieved_evidence_ids_per_block": retrieval_context["evidence_ids_by_block"],
        "llm2_input_evidence_ids_per_block": {
            block: [record["evidence_id"] for record in records]
            for block, records in llm2_input_evidence_by_block.items()
        },
        "canonical_design_record_path": canonical_design_record_path,
        "llm2_model_name": llm2_model_name,
        "llm3_model_name": llm3_model_name,
        "llm2_reasoning_effort": llm2_reasoning_effort,
        "llm3_reasoning_effort": llm3_reasoning_effort,
        "default_path_replaced_old_single_call": True,
        "legacy_direct_path_available": True,
        "legacy_direct_path_used": legacy_direct_path_used,
        "legacy_model_name": legacy_model_name,
        "extraction_path": extraction_path,
    }
    write_json(phase2_artifact_path, payload)


def _validate_run_inputs(run_paths) -> None:
    missing_paths = [
        path
        for path in [
            run_paths.metadata_path,
            run_paths.sections_path,
            run_paths.bm25_dir / "evidence_items.json",
            run_paths.faiss_dir / "index.faiss",
        ]
        if not path.exists()
    ]
    if missing_paths:
        missing = ", ".join(str(path) for path in missing_paths)
        raise FileNotFoundError(
            "Run directory is not fully prepared for extraction. Missing required files: " + missing
        )


def _generate_agents_structured(
    client: Any,
    *,
    agent_name: str,
    model: str,
    reasoning_effort: str,
    request: dict[str, str],
    response_model: type[Any],
) -> StructuredGenerationResult:
    result = client.generate_structured_via_agent(
        agent_name=agent_name,
        model=model,
        reasoning_effort=reasoning_effort,
        instructions=request["instructions"],
        input_text=request["input_text"],
        response_model=response_model,
    )
    if isinstance(result, StructuredGenerationResult):
        return result
    if isinstance(result, dict) and "parsed" in result and "raw_text" in result:
        return StructuredGenerationResult(parsed=result["parsed"], raw_text=result["raw_text"])
    raise TypeError("LLM client must return StructuredGenerationResult or an equivalent payload")


def _prepare_llm2_evidence_by_block(evidence_by_block: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    return {
        block: [deepcopy(record) for record in sorted(records, key=_llm2_record_sort_key)]
        for block, records in evidence_by_block.items()
    }


def _llm2_record_sort_key(record: dict[str, Any]) -> tuple[float, int, str]:
    score = record.get("score")
    page = record.get("page_number")
    return (
        -(float(score) if isinstance(score, (int, float)) else 0.0),
        page if isinstance(page, int) else 10_000,
        str(record.get("evidence_id", "")),
    )


def _build_linked_evidence_records(
    canonical_record: CanonicalDesignRecord,
    evidence_by_block: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for records in evidence_by_block.values():
        for record in records:
            by_id.setdefault(record["evidence_id"], record)
    linked: list[dict[str, Any]] = []
    for evidence_id in collect_canonical_evidence_ids(canonical_record):
        record = by_id.get(evidence_id)
        if record is not None:
            linked.append(deepcopy(record))
    return linked


def _validate_canonical_generation(record: CanonicalDesignRecord, retrieval_context: dict[str, Any]) -> CanonicalDesignRecord:
    if not isinstance(record, CanonicalDesignRecord):
        raise TypeError("Structured parse did not return CanonicalDesignRecord")
    unexpected = sorted(set(collect_canonical_evidence_ids(record)) - set(retrieval_context["all_retrieved_evidence_ids"]))
    if unexpected:
        raise ValueError("Canonical record referenced evidence ids not returned by retrieval: " + ", ".join(unexpected))
    return record


def _validate_generation(spec: AntennaArchitectureSpecMvpV2, retrieval_context: dict[str, Any]) -> AntennaArchitectureSpecMvpV2:
    if not isinstance(spec, AntennaArchitectureSpecMvpV2):
        raise TypeError("Structured parse did not return AntennaArchitectureSpecMvpV2")
    valid_ids = set(retrieval_context["all_retrieved_evidence_ids"])
    unexpected = sorted(set(spec.evidence_used) - valid_ids)
    if unexpected:
        raise ValueError("Unknown evidence ids not returned by retrieval: " + ", ".join(unexpected))
    nested_unexpected = sorted(set(collect_nested_evidence_ids(spec)) - valid_ids)
    if nested_unexpected:
        raise ValueError("Nested evidence ids not returned by retrieval: " + ", ".join(nested_unexpected))
    return spec


def _apply_minimal_cleanup(spec: AntennaArchitectureSpecMvpV2) -> AntennaArchitectureSpecMvpV2:
    payload = spec.to_clean_dict()
    payload["evidence_used"] = _dedupe_preserve_order(list(payload.get("evidence_used", [])) + collect_nested_evidence_ids(spec))
    _normalize_units_in_payload(payload)
    _dedupe_exact_parameters(payload)
    return AntennaArchitectureSpecMvpV2.model_validate(payload)


def _normalize_units_in_payload(payload: dict[str, Any]) -> None:
    units = payload.get("units", {})
    if isinstance(units, dict):
        for unit_field in units.values():
            if isinstance(unit_field, dict) and isinstance(unit_field.get("value"), str):
                unit_field["value"] = _normalize_unit_literal(unit_field["value"])
    _normalize_nested_unit_literals(payload)


def _normalize_nested_unit_literals(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "unit" and isinstance(nested, str):
                value[key] = _normalize_unit_literal(nested)
            else:
                _normalize_nested_unit_literals(nested)
    elif isinstance(value, list):
        for item in value:
            _normalize_nested_unit_literals(item)


def _normalize_unit_literal(value: str) -> str:
    lowered = value.strip().lower()
    if lowered in {"?", "ohm", "ohms"}:
        return "ohm"
    if lowered == "ghz":
        return "GHz"
    if lowered == "mhz":
        return "MHz"
    if lowered == "khz":
        return "kHz"
    if lowered == "mm":
        return "mm"
    return value.strip()


def _dedupe_exact_parameters(payload: dict[str, Any]) -> None:
    parameters = payload.get("parameters")
    if not isinstance(parameters, list):
        return
    seen: dict[str, str] = {}
    deduped: list[dict[str, Any]] = []
    remap: dict[str, str] = {}
    for parameter in parameters:
        if not isinstance(parameter, dict):
            continue
        param_id = str(parameter.get("param_id", ""))
        identity = json.dumps({key: value for key, value in parameter.items() if key != "param_id"}, sort_keys=True, ensure_ascii=False)
        existing = seen.get(identity)
        if existing is not None:
            remap[param_id] = existing
            continue
        seen[identity] = param_id
        deduped.append(parameter)
    if remap:
        for entity in payload.get("entities", []):
            geometry = entity.get("geometry", {}) if isinstance(entity, dict) else {}
            dimensions = geometry.get("dimensions", []) if isinstance(geometry, dict) else []
            for dimension in dimensions:
                if isinstance(dimension, dict) and isinstance(dimension.get("param_ref"), str):
                    dimension["param_ref"] = remap.get(dimension["param_ref"], dimension["param_ref"])
    payload["parameters"] = deduped


def _build_report(
    *,
    run_paths,
    extraction_path: str,
    validation_success: bool,
    extraction_status: str,
    schema_errors: list[dict[str, Any]],
    warnings: list[str],
    retrieval_context: dict[str, Any],
    prompt_evidence_by_block: dict[str, list[dict[str, Any]]],
    final_evidence_ids_used: list[str],
    structural_bound_evidence_ids: list[str],
    attempt_count: int,
    prompt_budget: dict[str, Any],
    phase1_payload: dict[str, Any] | None,
    llm2_model_name: str | None,
    llm3_model_name: str | None,
    llm2_reasoning_effort: str | None,
    llm3_reasoning_effort: str | None,
    canonical_design_record_path: str | None,
    legacy_direct_path_used: bool,
    legacy_model_name: str | None,
) -> dict[str, Any]:
    report = {
        "run_id": run_paths.run_id,
        "timestamp_utc": utc_timestamp(),
        "model_name": llm3_model_name or legacy_model_name,
        "llm2_model_name": llm2_model_name,
        "llm3_model_name": llm3_model_name,
        "llm2_reasoning_effort": llm2_reasoning_effort,
        "llm3_reasoning_effort": llm3_reasoning_effort,
        "canonical_design_record_path": canonical_design_record_path,
        "extraction_path": extraction_path,
        "old_single_gpt4o_path_replaced": True,
        "legacy_direct_path_available": True,
        "legacy_direct_path_used": legacy_direct_path_used,
        "legacy_model_name": legacy_model_name,
        "extraction_status": extraction_status,
        "retrieval_queries_used": retrieval_context["retrieval_queries_used"],
        "evidence_ids_retrieved_per_block": retrieval_context["evidence_ids_by_block"],
        "final_evidence_ids_used": final_evidence_ids_used,
        "validation_success": validation_success,
        "schema_errors": schema_errors,
        "warnings": warnings,
        "attempt_count": attempt_count,
        "prompt_evidence_ids_per_block": {
            block: [record["evidence_id"] for record in records]
            for block, records in prompt_evidence_by_block.items()
        },
        "query_usefulness_per_block": _build_query_usefulness_by_block(
            retrieval_context=retrieval_context,
            prompt_evidence_by_block=prompt_evidence_by_block,
            final_evidence_ids_used=final_evidence_ids_used,
            structural_bound_evidence_ids=structural_bound_evidence_ids,
        ),
        "prompt_budget": prompt_budget,
    }
    if phase1_payload is not None:
        report["phase1"] = phase1_payload
    return report


def _error_payload(exc: Exception) -> list[dict[str, Any]]:
    if hasattr(exc, "errors") and callable(exc.errors):
        try:
            return [_json_safe(error) for error in exc.errors(include_url=False)]
        except TypeError:
            return [_json_safe(error) for error in exc.errors()]
    return [{"loc": [], "msg": str(exc), "type": exc.__class__.__name__}]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _build_query_usefulness_by_block(
    *,
    retrieval_context: dict[str, Any],
    prompt_evidence_by_block: dict[str, list[dict[str, Any]]],
    final_evidence_ids_used: list[str],
    structural_bound_evidence_ids: list[str],
) -> dict[str, list[dict[str, Any]]]:
    prompt_ids_by_block = {
        block: {record["evidence_id"] for record in records}
        for block, records in prompt_evidence_by_block.items()
    }
    final_ids = set(final_evidence_ids_used)
    structural_ids = set(structural_bound_evidence_ids)
    usefulness: dict[str, list[dict[str, Any]]] = {}
    for block, query_entries in retrieval_context["retrieval_queries_used"].items():
        block_prompt_ids = prompt_ids_by_block.get(block, set())
        block_entries: list[dict[str, Any]] = []
        for entry in query_entries:
            retrieved_ids = list(entry.get("result_evidence_ids", []))
            prompt_hits = [evidence_id for evidence_id in retrieved_ids if evidence_id in block_prompt_ids]
            final_hits = [evidence_id for evidence_id in retrieved_ids if evidence_id in final_ids]
            structural_hits = [evidence_id for evidence_id in retrieved_ids if evidence_id in structural_ids]
            block_entries.append(
                {
                    "search_type": entry["search_type"],
                    "query": entry["query"],
                    "retrieved_count": len(retrieved_ids),
                    "prompt_survival_count": len(prompt_hits),
                    "final_evidence_usage_count": len(final_hits),
                    "contributed_to_bound_structural_field": bool(structural_hits),
                    "prompt_survival_evidence_ids": prompt_hits,
                    "final_evidence_usage_ids": final_hits,
                    "bound_structural_evidence_ids": structural_hits,
                }
            )
        usefulness[block] = block_entries
    return usefulness


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
