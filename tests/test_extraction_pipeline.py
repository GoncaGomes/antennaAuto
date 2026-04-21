from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

try:
    import pymupdf
except ImportError:  # pragma: no cover
    import fitz as pymupdf  # type: ignore[no-redef]

from mvp.config import RetrievalConfig
from mvp.extraction.agent import gather_retrieval_context
from mvp.extraction.pipeline import extract_run
from mvp.index import index_run
from mvp.llm.client import StructuredGenerationResult
from mvp.pipeline import run_pipeline
from mvp.retrieval import BundleRetriever
from mvp.schemas.extraction_spec import validate_spec_payload
from mvp.schemas.interpretation_map import validate_interpretation_map_payload

TEST_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+X2ioAAAAASUVORK5CYII="
)


class FakeAgentsClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def generate_structured_via_agent(
        self,
        *,
        agent_name: str,
        model: str,
        reasoning_effort: str,
        instructions: str,
        input_text: str,
        response_model,
    ) -> StructuredGenerationResult:
        self.calls.append(
            {
                "agent_name": agent_name,
                "model": model,
                "reasoning_effort": reasoning_effort,
                "instructions": instructions,
                "input_text": input_text,
                "response_model": response_model,
            }
        )
        if not self.responses:
            raise AssertionError("No fake responses remaining")
        payload = self.responses.pop(0)
        parsed = payload if isinstance(payload, response_model) else response_model.model_validate(payload)
        return StructuredGenerationResult(parsed=parsed, raw_text=parsed.model_dump_json())


class FakeLLMClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def generate_structured(self, *, model: str, messages: list[dict[str, str]], response_model) -> StructuredGenerationResult:
        self.calls.append({"model": model, "messages": messages, "response_model": response_model})
        if not self.responses:
            raise AssertionError("No fake responses remaining")
        payload = self.responses.pop(0)
        parsed = payload if isinstance(payload, response_model) else response_model.model_validate(payload)
        return StructuredGenerationResult(parsed=parsed, raw_text=parsed.model_dump_json())


def create_extraction_fixture_pdf(path: Path) -> None:
    image_path = path.with_suffix(".png")
    image_path.write_bytes(TEST_PNG)

    document = pymupdf.open()
    page_one = document.new_page()
    page_one.insert_text(
        (72, 72),
        (
            "Abstract\n\n"
            "This work proposes a rectangular microstrip patch antenna for 28 GHz operation. "
            "Rogers RT5880 substrate and copper ground are used. "
            "The antenna uses an inset feed and shows VSWR below 1.8 with bandwidth of 280 MHz. "
            "Input impedance remains between 51 ohm and 55 ohm."
        ),
    )
    page_one.insert_image(pymupdf.Rect(72, 170, 180, 250), filename=str(image_path))
    page_one.insert_text(
        (72, 280),
        "Figure 1. Proposed antenna geometry\nThe figure caption only provides context, not raw geometry facts.",
    )

    page_two = document.new_page()
    page_two.insert_text(
        (72, 72),
        (
            "Table 1. Dimensions of proposed antenna\n"
            "Parameter Value(mm)\n"
            "Lpatch 5.3\n"
            "Wpatch 4.8\n"
            "InsetDepth 1.1\n"
            "2. Materials\n"
            "Rogers RT5880 substrate and copper patch are used.\n"
        ),
    )

    document.save(path)
    document.close()


def test_extract_run_multistage_writes_outputs_and_uses_agents_models(tmp_path: Path) -> None:
    run_paths, retrieval_context = _prepare_retrieval_context(tmp_path)
    client = FakeAgentsClient([
        _build_canonical_payload(retrieval_context),
        _build_valid_payload(run_paths, retrieval_context),
    ])

    spec, report = extract_run(run_paths.run_dir, top_k=3, llm_client=client)

    assert validate_spec_payload(spec)
    assert len(client.calls) == 2
    assert client.calls[0]["agent_name"] == "phase2_canonicalization"
    assert client.calls[1]["agent_name"] == "phase3_schema_construction"
    assert all(call["model"] == "gpt-5.4-mini" for call in client.calls)
    assert all(call["reasoning_effort"] == "medium" for call in client.calls)
    assert report["extraction_path"] == "retrieval_llm2_llm3"
    assert report["llm2_model_name"] == "gpt-5.4-mini"
    assert report["llm3_model_name"] == "gpt-5.4-mini"
    assert report["legacy_direct_path_used"] is False
    assert (run_paths.outputs_dir / "canonical_design_record.json").exists()

    phase2_artifact = json.loads((run_paths.outputs_dir / "phase2_retrieval_context.json").read_text(encoding="utf-8"))
    assert phase2_artifact["llm2_model_name"] == "gpt-5.4-mini"
    assert phase2_artifact["llm3_model_name"] == "gpt-5.4-mini"
    assert phase2_artifact["default_path_replaced_old_single_call"] is True
    classification_query = phase2_artifact["retrieval_queries_executed_per_block"]["classification"][0]
    assert "result_evidence_ids" not in classification_query
    assert {"retrieved_count", "sample_result_evidence_ids"} <= set(classification_query)
    classification_ids = phase2_artifact["retrieved_evidence_ids_per_block"]["classification"]
    assert {"count", "sample_evidence_ids"} <= set(classification_ids)
    assert len(classification_ids["sample_evidence_ids"]) <= 10
    llm2_ids = phase2_artifact["llm2_input_evidence_ids_per_block"]["classification"]
    assert {"count", "sample_evidence_ids"} <= set(llm2_ids)
    usefulness = report["query_usefulness_per_block"]["classification"][0]
    assert "prompt_survival_evidence_ids" not in usefulness
    assert "prompt_survival_evidence_id_samples" in usefulness


def test_extract_run_multistage_uses_phase1_queries_and_writes_artifact(tmp_path: Path) -> None:
    run_paths, retrieval_context = _prepare_retrieval_context(tmp_path)
    interpretation_map = validate_interpretation_map_payload(
        {
            "has_multiple_variants": True,
            "has_final_design_signal": True,
            "search_queries": [{"query_id": "Q1", "query_text": "final selected antenna design", "priority": "high", "why": "Phase 1 guidance"}],
            "open_uncertainties": ["Whether a final selected design is explicit."],
        }
    )
    run_paths.outputs_dir.joinpath("interpretation_map.json").write_text(interpretation_map.model_dump_json(indent=2), encoding="utf-8")
    client = FakeAgentsClient([
        _build_canonical_payload(retrieval_context),
        _build_valid_payload(run_paths, retrieval_context),
    ])

    _, report = extract_run(run_paths.run_dir, top_k=3, llm_client=client)

    assert report["validation_success"] is True
    assert "final selected antenna design" in client.calls[0]["input_text"]
    phase2_artifact = json.loads((run_paths.outputs_dir / "phase2_retrieval_context.json").read_text(encoding="utf-8"))
    assert phase2_artifact["phase1_guidance_found"] is True
    assert phase2_artifact["phase1_search_queries_used"][0]["query_text"] == "final selected antenna design"
    assert any(
        entry["query_source"] == "phase1_interpretation_map"
        for entry in phase2_artifact["retrieval_queries_executed_per_block"]["classification"]
    )


def test_extract_run_multistage_writes_failure_report_for_invalid_evidence_ids(tmp_path: Path) -> None:
    run_paths, retrieval_context = _prepare_retrieval_context(tmp_path)
    invalid_payload = _build_valid_payload(run_paths, retrieval_context)
    invalid_payload["evidence_used"] = ["chunk:not_retrieved"]
    client = FakeAgentsClient([
        _build_canonical_payload(retrieval_context),
        invalid_payload,
    ])

    with pytest.raises(RuntimeError):
        extract_run(run_paths.run_dir, top_k=3, llm_client=client)

    saved_report = json.loads(run_paths.extraction_report_path.read_text(encoding="utf-8"))
    assert saved_report["validation_success"] is False
    assert saved_report["extraction_status"] == "failed_llm3_schema_extraction"


def test_extract_run_multistage_dedupes_exact_duplicate_parameters(tmp_path: Path) -> None:
    run_paths, retrieval_context = _prepare_retrieval_context(tmp_path)
    payload = _build_valid_payload(run_paths, retrieval_context)
    table_evidence = _first_matching_evidence(retrieval_context, "parameters", prefix="table:")
    payload["parameters"] = [
        {
            "param_id": "param_patch_length_a",
            "symbol": "Lpatch",
            "semantic_name": "patch_length",
            "status": "extracted",
            "value": "5.3",
            "unit": "mm",
            "evidence_ids": [table_evidence],
        },
        {
            "param_id": "param_patch_length_b",
            "symbol": "Lpatch",
            "semantic_name": "patch_length",
            "status": "extracted",
            "value": "5.3",
            "unit": "mm",
            "evidence_ids": [table_evidence],
        },
    ]
    payload["entities"][0]["geometry"]["dimensions"] = [{"name": "length", "status": "extracted", "param_ref": "param_patch_length_b", "evidence_ids": [table_evidence]}]
    client = FakeAgentsClient([
        _build_canonical_payload(retrieval_context),
        payload,
    ])

    spec, report = extract_run(run_paths.run_dir, top_k=3, llm_client=client)

    assert report["validation_success"] is True
    assert len(spec["parameters"]) == 1
    assert spec["entities"][0]["geometry"]["dimensions"][0]["param_ref"] == "param_patch_length_a"


def test_extract_run_legacy_path_isolated_behind_flag(tmp_path: Path) -> None:
    run_paths, retrieval_context = _prepare_retrieval_context(tmp_path)
    client = FakeLLMClient([_build_valid_payload(run_paths, retrieval_context)])

    spec, report = extract_run(run_paths.run_dir, model="gpt-4o", top_k=3, llm_client=client, legacy_direct=True)

    assert validate_spec_payload(spec)
    assert len(client.calls) == 1
    assert client.calls[0]["model"] == "gpt-4o"
    assert report["extraction_path"] == "legacy_direct_single_call"
    assert report["legacy_direct_path_used"] is True
    assert report["legacy_model_name"] == "gpt-4o"


def _prepare_retrieval_context(tmp_path: Path):
    source_pdf = tmp_path / "article.pdf"
    create_extraction_fixture_pdf(source_pdf)
    run_paths, _, _ = run_pipeline(source_pdf, base_dir=tmp_path)
    index_run(run_paths, config=RetrievalConfig(chunking_mode="paragraph", embedding_backend="hash", fusion_strategy="weighted"))
    retriever = BundleRetriever(run_paths.run_dir)
    retrieval_context = gather_retrieval_context(retriever, top_k=3)
    return run_paths, retrieval_context


def _build_canonical_payload(retrieval_context: dict) -> dict:
    fallback = retrieval_context["all_retrieved_evidence_ids"][0]
    materials_evidence = _first_evidence(retrieval_context, "materials") or fallback
    table_evidence = _first_matching_evidence(retrieval_context, "parameters", prefix="table:") or fallback
    feed_evidence = _first_evidence(retrieval_context, "feeds") or table_evidence
    dominant = _dedupe_preserve_order([table_evidence, materials_evidence, feed_evidence])
    secondary = [evidence_id for evidence_id in retrieval_context["all_retrieved_evidence_ids"] if evidence_id not in dominant][:2]
    return {
        "selected_design_summary": "Rectangular microstrip patch antenna with inset feed.",
        "selected_design_rationale": "The retrieved evidence consistently presents this as the dominant proposed design.",
        "has_multiple_variants": False,
        "dominant_evidence_ids": dominant,
        "secondary_evidence_ids": secondary,
        "identified_antennas": [
            "Rectangular microstrip patch reference geometry",
            "Rectangular microstrip patch antenna with inset feed",
        ],
        "proposed_final_antenna_rationale": "The inset-fed rectangular microstrip patch is the only design treated as the proposed antenna in the retrieved evidence.",
        "final_design": {
            "classification": {
                "primary_family": "microstrip_patch",
                "topology_tags": ["rectangular_patch", "inset_feed"],
            },
            "patch": {
                "label": "main patch",
                "shape_mode": "rectangular",
                "dimensions": [
                    {"name": "length", "value": "5.3", "unit": "mm"},
                    {"name": "width", "value": "4.8", "unit": "mm"},
                ],
                "material_name": "copper",
                "layer_role": "radiator",
                "evidence_ids": [table_evidence],
            },
            "feed": {
                "feed_family": "microstrip",
                "matching_style": "inset",
                "driven_target": "main patch",
                "dimensions": [],
                "location": None,
                "evidence_ids": [feed_evidence],
            },
            "ground": None,
            "slots": [],
            "materials": [{"name": "Rogers RT5880", "category": "dielectric", "roles": ["substrate"], "evidence_ids": [materials_evidence]}],
            "layers": [],
            "performance_targets": [],
            "extra_parameters": [],
        },
        "design_evolution_notes": [],
        "unresolved_conflicts": [],
    }


def _build_valid_payload(run_paths, retrieval_context: dict) -> dict:
    materials_evidence = _first_evidence(retrieval_context, "materials")
    table_evidence = _first_matching_evidence(retrieval_context, "parameters", prefix="table:")
    feed_evidence = _first_evidence(retrieval_context, "feeds")
    quality_evidence = _first_evidence(retrieval_context, "quality")
    used = _dedupe_preserve_order([item for item in [materials_evidence, table_evidence, feed_evidence, quality_evidence] if item])
    return {
        "schema_name": "antenna_architecture_spec_mvp_v2",
        "schema_version": "2.0",
        "document_context": {"run_id": run_paths.run_id, "original_filename": "article.pdf", "page_count": 2},
        "classification": {"primary_family": "microstrip_patch", "topology_tags": ["rectangular_patch"], "status": "extracted", "confidence": 0.82, "evidence_ids": [materials_evidence or used[0]]},
        "units": {
            "length": {"status": "extracted", "value": "mm", "evidence_ids": [table_evidence or used[0]]},
            "frequency": {"status": "extracted", "value": "GHz", "evidence_ids": [materials_evidence or used[0]]},
            "impedance": {"status": "extracted", "value": "Ohm", "evidence_ids": [feed_evidence or used[0]]},
        },
        "parameters": [{"param_id": "param_patch_length", "symbol": "Lpatch", "semantic_name": "patch_length", "status": "extracted", "value": "5.3", "unit": "mm", "evidence_ids": [table_evidence or used[0]]}],
        "materials": [
            {"material_id": "material_substrate", "name": "Rogers RT5880", "category": "dielectric", "roles": ["substrate"], "status": "extracted", "evidence_ids": [materials_evidence or used[0]]},
            {"material_id": "material_conductor", "name": "copper", "category": "conductor", "roles": ["ground", "patch"], "status": "extracted", "evidence_ids": [materials_evidence or used[0]]},
        ],
        "layers": [
            {"layer_id": "layer_substrate", "role": "substrate", "material_ref": "material_substrate", "thickness": {"status": "missing", "evidence_ids": []}, "z_order": 1, "evidence_ids": [materials_evidence or used[0]]},
            {"layer_id": "layer_patch", "role": "radiator", "material_ref": "material_conductor", "thickness": {"status": "missing", "evidence_ids": []}, "z_order": 2, "evidence_ids": [materials_evidence or used[0]]},
        ],
        "entities": [{"entity_id": "entity_patch", "entity_type": "patch", "role": "radiator", "layer_ref": "layer_patch", "geometry": {"shape_mode": "rectangular", "dimensions": [{"name": "length", "status": "extracted", "param_ref": "param_patch_length", "evidence_ids": [table_evidence or used[0]]}], "outline_points": []}, "placement": {"status": "missing"}, "evidence_ids": [table_evidence or used[0]]}],
        "feeds": [{"feed_id": "feed_main", "feed_family": "microstrip", "matching_style": "inset", "driven_entity_ref": "entity_patch", "reference_impedance": {"status": "extracted", "value": "50", "unit": "Ohm", "evidence_ids": [feed_evidence or used[0]]}, "port_type": {"status": "missing"}, "evidence_ids": [feed_evidence or used[0]]}],
        "instances": [],
        "quality": {"build_readiness": "partial", "missing_required_for_build": ["exact placement anchor"], "ambiguities": ["geometry remains text-grounded only"], "confidence": 0.64},
        "evidence_used": used,
    }


def _first_evidence(retrieval_context: dict, block: str) -> str | None:
    evidence_ids = retrieval_context["evidence_ids_by_block"].get(block, [])
    return evidence_ids[0] if evidence_ids else None


def _first_matching_evidence(retrieval_context: dict, block: str, *, prefix: str) -> str | None:
    for evidence_id in retrieval_context["evidence_ids_by_block"].get(block, []):
        if evidence_id.startswith(prefix):
            return evidence_id
    return _first_evidence(retrieval_context, block)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
