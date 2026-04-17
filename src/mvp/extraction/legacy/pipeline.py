from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ...bundle import load_run_paths, save_structured_output
from ...interpretation.pipeline import extract_existing_phase1_payload
from ...llm.client import OpenAIJsonClient, StructuredGenerationResult
from ...retrieval import BundleRetriever
from ...schemas.extraction_spec import AntennaArchitectureSpecMvpV2
from ...utils import ensure_dir, write_json
from ..agent import gather_retrieval_context_with_phase1
from ..pipeline import (
    DEFAULT_STRUCTURED_MAX_ATTEMPTS,
    _build_report,
    _error_payload,
    _load_phase1_guidance,
    _validate_generation,
    _validate_run_inputs,
    _write_phase2_retrieval_context,
)
from .prompting import PromptBudgetError, build_extraction_messages, prepare_prompt_evidence


def _extract_run_legacy_direct(
    *,
    run_dir: str | Path,
    model: str,
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
    phase1_guidance, interpretation_note = _load_phase1_guidance(run_paths, target_dir)
    retrieval_context = gather_retrieval_context_with_phase1(
        retriever,
        top_k=top_k,
        phase1_search_queries=(phase1_guidance.get("search_queries") if phase1_guidance else None),
    )
    client = llm_client or OpenAIJsonClient.from_env()

    warnings: list[str] = []
    prompt_budget: dict[str, Any] = {}
    prompt_evidence_by_block: dict[str, list[dict[str, Any]]] = {}
    phase2_artifact_path = target_dir / "phase2_retrieval_context.json"
    attempt_count = 0

    try:
        prompt_evidence_by_block, prompt_budget = prepare_prompt_evidence(
            retrieval_context["run_context"],
            retrieval_context["evidence_by_block"],
        )
        _write_phase2_retrieval_context(
            phase2_artifact_path=phase2_artifact_path,
            retrieval_context=retrieval_context,
            phase1_guidance=phase1_guidance,
            llm2_input_evidence_by_block={},
            extraction_path="legacy_direct_single_call",
            canonical_design_record_path=None,
            llm2_model_name=None,
            llm3_model_name=None,
            llm2_reasoning_effort=None,
            llm3_reasoning_effort=None,
            legacy_direct_path_used=True,
            legacy_model_name=model,
        )
        messages = build_extraction_messages(
            retrieval_context["run_context"],
            prompt_evidence_by_block,
            interpretation_note=interpretation_note,
        )
        if debug_dir is not None:
            write_json(
                debug_dir / "extraction_messages_initial.json",
                {
                    "messages": messages,
                    "prompt_evidence_by_block": prompt_evidence_by_block,
                    "prompt_budget": prompt_budget,
                    "interpretation_note": interpretation_note,
                },
            )
        result, attempt_count = _generate_structured_with_retries(
            client,
            model,
            messages,
            max_attempts=DEFAULT_STRUCTURED_MAX_ATTEMPTS,
            debug_dir=debug_dir,
        )
        spec = _validate_generation(result.parsed, retrieval_context)
    except Exception as exc:
        if isinstance(exc, PromptBudgetError):
            prompt_budget = exc.budget
        attempt_count = int(getattr(exc, "attempt_count", attempt_count))
        extraction_status = "failed_prompt_budget" if isinstance(exc, PromptBudgetError) else "failed_structured_parse"
        report = _build_report(
            run_paths=run_paths,
            extraction_path="legacy_direct_single_call",
            validation_success=False,
            extraction_status=extraction_status,
            schema_errors=_error_payload(exc),
            warnings=warnings,
            retrieval_context=retrieval_context,
            prompt_evidence_by_block=prompt_evidence_by_block,
            final_evidence_ids_used=[],
            structural_bound_evidence_ids=[],
            attempt_count=attempt_count,
            prompt_budget=prompt_budget,
            phase1_payload=phase1_payload,
            llm2_model_name=None,
            llm3_model_name=None,
            llm2_reasoning_effort=None,
            llm3_reasoning_effort=None,
            canonical_design_record_path=None,
            legacy_direct_path_used=True,
            legacy_model_name=model,
        )
        write_json(target_dir / "extraction_run_report.json", report)
        raise RuntimeError(
            f"Extraction failed during legacy direct extraction. See report at {target_dir / 'extraction_run_report.json'}"
        ) from exc

    spec_json = spec.to_clean_dict()
    report = _build_report(
        run_paths=run_paths,
        extraction_path="legacy_direct_single_call",
        validation_success=True,
        extraction_status="completed",
        schema_errors=[],
        warnings=warnings,
        retrieval_context=retrieval_context,
        prompt_evidence_by_block=prompt_evidence_by_block,
        final_evidence_ids_used=spec.evidence_used,
        structural_bound_evidence_ids=[],
        attempt_count=attempt_count,
        prompt_budget=prompt_budget,
        phase1_payload=phase1_payload,
        llm2_model_name=None,
        llm3_model_name=None,
        llm2_reasoning_effort=None,
        llm3_reasoning_effort=None,
        canonical_design_record_path=None,
        legacy_direct_path_used=True,
        legacy_model_name=model,
    )
    save_structured_output(run_paths.run_dir, spec_json, report, output_dir=target_dir)
    return spec_json, report


def _generate_structured(client: Any, model: str, messages: list[dict[str, str]]) -> StructuredGenerationResult:
    result = client.generate_structured(
        model=model,
        messages=messages,
        response_model=AntennaArchitectureSpecMvpV2,
    )
    if isinstance(result, StructuredGenerationResult):
        return result
    if isinstance(result, dict) and "parsed" in result and "raw_text" in result:
        return StructuredGenerationResult(parsed=result["parsed"], raw_text=result["raw_text"])
    raise TypeError("LLM client must return StructuredGenerationResult or an equivalent payload")


def _generate_structured_with_retries(
    client: Any,
    model: str,
    initial_messages: list[dict[str, str]],
    *,
    max_attempts: int,
    debug_dir: Path | None,
) -> tuple[StructuredGenerationResult, int]:
    messages = [dict(message) for message in initial_messages]
    attempt_count = 0

    while True:
        attempt_count += 1
        try:
            result = _generate_structured(client, model, messages)
            if debug_dir is not None:
                write_json(
                    debug_dir / f"extraction_response_attempt_{attempt_count}.json",
                    {
                        "raw_text": result.raw_text,
                        "parsed": result.parsed.model_dump(exclude_none=True),
                    },
                )
            return result, attempt_count
        except ValidationError as exc:
            setattr(exc, "attempt_count", attempt_count)
            if debug_dir is not None:
                write_json(
                    debug_dir / f"extraction_validation_error_attempt_{attempt_count}.json",
                    {"errors": _error_payload(exc)},
                )
            if attempt_count >= max_attempts:
                raise
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous JSON failed strict validation with this error: "
                        f"{exc}. Please correct the JSON so it strictly passes the schema."
                    ),
                }
            )
        except Exception as exc:
            setattr(exc, "attempt_count", attempt_count)
            raise
