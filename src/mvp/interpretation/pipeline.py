from __future__ import annotations

from pathlib import Path
from typing import Any

from ..bundle import load_run_paths
from ..llm.client import OpenAIJsonClient, StructuredGenerationResult
from ..schemas.interpretation_map import InterpretationMap
from ..utils import ensure_dir, read_json, utc_timestamp, write_json
from .discovery import build_paper_map
from .prompting import build_interpretation_messages

DEFAULT_PHASE1_MODEL = "gpt-5.4-mini"


def run_phase1(
    run_dir: str | Path,
    *,
    model: str = DEFAULT_PHASE1_MODEL,
    output_dir: str | Path | None = None,
    debug: bool = False,
    llm_client: Any | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Run deterministic paper-map generation plus one strict LLM interpretation-map call."""

    run_paths = load_run_paths(Path(run_dir))
    target_dir = ensure_dir(Path(output_dir)) if output_dir else ensure_dir(run_paths.outputs_dir)
    debug_dir = ensure_dir(target_dir / "debug") if debug else None
    report_path = target_dir / "extraction_run_report.json"
    paper_map_path = target_dir / "paper_map.json"
    interpretation_map_path = target_dir / "interpretation_map.json"

    warnings: list[str] = []
    errors: list[dict[str, Any]] = []
    paper_map_status = "not_run"
    interpretation_map_status = "not_run"

    try:
        paper_map = build_paper_map(run_paths.run_dir)
        paper_map_status = "completed"
        write_json(paper_map_path, paper_map.to_clean_dict())

        client = llm_client or OpenAIJsonClient.from_env()
        messages = build_interpretation_messages(paper_map)
        if debug_dir is not None:
            write_json(debug_dir / "phase1_interpretation_messages.json", {"messages": messages})

        result = _generate_interpretation_map(client, model, messages)
        interpretation_map = result.parsed
        interpretation_map_status = "completed"
        write_json(interpretation_map_path, interpretation_map.model_dump(exclude_none=True))
        if debug_dir is not None:
            write_json(
                debug_dir / "phase1_interpretation_response.json",
                {
                    "raw_text": result.raw_text,
                    "parsed": interpretation_map.model_dump(exclude_none=True),
                },
            )
    except Exception as exc:
        if paper_map_status == "completed":
            warnings.append("paper_map_generated_before_phase1_failure")
        errors = _error_payload(exc)
        report = _write_phase1_report(
            report_path=report_path,
            run_id=run_paths.run_id,
            phase1_payload={
                "run": True,
                "paper_map_status": paper_map_status if paper_map_status != "not_run" else "failed",
                "interpretation_map_status": "failed",
                "model_name": model,
                "warnings": warnings,
                "errors": errors,
                "paper_map_path": str(paper_map_path),
                "interpretation_map_path": str(interpretation_map_path),
            },
        )
        raise RuntimeError(f"Phase 1 failed. See report at {report_path}") from exc

    report = _write_phase1_report(
        report_path=report_path,
        run_id=run_paths.run_id,
        phase1_payload={
            "run": True,
            "paper_map_status": paper_map_status,
            "interpretation_map_status": interpretation_map_status,
            "model_name": model,
            "warnings": warnings,
            "errors": errors,
            "paper_map_path": str(paper_map_path),
            "interpretation_map_path": str(interpretation_map_path),
        },
    )
    return paper_map.to_clean_dict(), interpretation_map.model_dump(exclude_none=True), report


def _generate_interpretation_map(
    client: Any,
    model: str,
    messages: list[dict[str, str]],
) -> StructuredGenerationResult:
    result = client.generate_structured(
        model=model,
        messages=messages,
        response_model=InterpretationMap,
    )
    if isinstance(result, StructuredGenerationResult):
        return result
    if isinstance(result, dict) and "parsed" in result and "raw_text" in result:
        return StructuredGenerationResult(parsed=result["parsed"], raw_text=result["raw_text"])
    raise TypeError("LLM client must return StructuredGenerationResult or an equivalent payload")


def _write_phase1_report(*, report_path: Path, run_id: str, phase1_payload: dict[str, Any]) -> dict[str, Any]:
    if report_path.exists():
        report = read_json(report_path)
    else:
        report = {
            "run_id": run_id,
            "timestamp_utc": utc_timestamp(),
            "model_name": None,
            "extraction_status": "not_run",
            "retrieval_queries_used": {},
            "evidence_ids_retrieved_per_block": {},
            "final_evidence_ids_used": [],
            "validation_success": None,
            "schema_errors": [],
            "warnings": [],
            "attempt_count": 0,
            "prompt_evidence_ids_per_block": {},
            "query_usefulness_per_block": {},
            "prompt_budget": {},
        }
    report["timestamp_utc"] = utc_timestamp()
    report["phase1"] = phase1_payload
    write_json(report_path, report)
    return report


def extract_existing_phase1_payload(report_path: Path) -> dict[str, Any] | None:
    if not report_path.exists():
        return None
    report = read_json(report_path)
    phase1 = report.get("phase1")
    if isinstance(phase1, dict):
        return phase1
    return None


def _error_payload(exc: Exception) -> list[dict[str, Any]]:
    if hasattr(exc, "errors") and callable(exc.errors):
        try:
            return [error for error in exc.errors(include_url=False)]
        except TypeError:
            return [error for error in exc.errors()]
    return [{"loc": [], "msg": str(exc), "type": exc.__class__.__name__}]
