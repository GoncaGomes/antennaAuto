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
from mvp.index import index_run
from mvp.interpretation import discovery as discovery_module
from mvp.interpretation.discovery import build_paper_map
from mvp.interpretation.pipeline import run_phase1
from mvp.llm.client import StructuredGenerationResult
from mvp import parsers
from mvp.pipeline import run_pipeline
from mvp.schemas.interpretation_map import InterpretationMap, validate_interpretation_map_payload
from tests.docling_test_stubs import (
    FakeDoc,
    FakePictureItem,
    FakeRef,
    FakeSectionHeaderItem,
    FakeTableCell,
    FakeTableItem,
    FakeTextItem,
    TEST_PNG,
    install_fake_docling,
)


class FakeInterpretationClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def generate_structured(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        response_model,
    ) -> StructuredGenerationResult:
        self.calls.append({"model": model, "messages": messages, "response_model": response_model})
        payload = self.responses.pop(0)
        parsed = response_model.model_validate(payload)
        return StructuredGenerationResult(parsed=parsed, raw_text=parsed.model_dump_json())


def create_interpretation_fixture_pdf(path: Path) -> None:
    image_path = path.with_suffix(".png")
    image_path.write_bytes(TEST_PNG)

    document = pymupdf.open()
    page_one = document.new_page()
    page_one.insert_text(
        (72, 72),
        (
            "A compact antenna configuration for dual-band operation\n\n"
            "Abstract. This proposed design studies two configurations. "
            "The final optimized design is fabricated and measured, while simulated results are used earlier in the paper.\n\n"
            "1. Antenna Design\n"
            "The proposed design uses a radiating element above a ground plane.\n\n"
            "Figure 1. Antenna geometry\n"
            "Top view of the proposed antenna layout.\n"
        ),
    )
    page_one.insert_image(pymupdf.Rect(72, 260, 180, 340), filename=str(image_path))

    page_two = document.new_page()
    page_two.insert_text(
        (72, 72),
        (
            "Table 1. Design parameters\n"
            "Parameter Value(mm)\n"
            "Length 10\n"
            "Width 8\n"
            "Thickness 1.6\n\n"
            "2. Measured Results\n"
            "The fabricated prototype shows measured bandwidth and return loss.\n"
        ),
    )

    document.save(path)
    document.close()


def _install_markdown_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    document = FakeDoc(
        [
            (
                FakeSectionHeaderItem(
                    self_ref="#/texts/1",
                    label="section_header",
                    text="A compact antenna configuration for dual-band operation",
                    page_no=1,
                    bbox=(40, 760, 420, 740),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/2",
                    label="text",
                    text="Abstract. This proposed design studies two configurations.",
                    page_no=1,
                    bbox=(40, 720, 420, 700),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/3",
                    label="text",
                    text="The final optimized design is fabricated and measured, while simulated results are used earlier in the paper.",
                    page_no=1,
                    bbox=(40, 690, 520, 670),
                ),
                0,
            ),
            (
                FakeSectionHeaderItem(
                    self_ref="#/texts/4",
                    label="section_header",
                    text="Antenna Design",
                    page_no=1,
                    bbox=(40, 650, 220, 630),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/5",
                    label="text",
                    text="The proposed design uses a radiating element above a ground plane.",
                    page_no=1,
                    bbox=(40, 620, 420, 600),
                ),
                0,
            ),
            (
                FakePictureItem(
                    self_ref="#/pictures/1",
                    label="picture",
                    page_no=1,
                    bbox=(40, 560, 220, 420),
                    captions=[FakeRef("#/texts/6")],
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/6",
                    label="caption",
                    text="Figure 1. Antenna geometry",
                    page_no=1,
                    bbox=(40, 400, 260, 385),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/7",
                    label="text",
                    text="Top view of the proposed antenna layout.",
                    page_no=1,
                    bbox=(40, 370, 320, 350),
                ),
                0,
            ),
            (
                FakeSectionHeaderItem(
                    self_ref="#/texts/8",
                    label="section_header",
                    text="Measured Results",
                    page_no=2,
                    bbox=(40, 760, 220, 740),
                ),
                0,
            ),
            (
                FakeTableItem(
                    self_ref="#/tables/1",
                    label="table",
                    page_no=2,
                    bbox=(40, 700, 340, 600),
                    captions=[FakeRef("#/texts/9")],
                    markdown="Table 1. Design parameters\n\n| Parameter | Value(mm) |\n| --- | --- |\n| Length | 10 |\n| Width | 8 |\n| Thickness | 1.6 |",
                    table_cells=[
                        FakeTableCell(0, 1, 0, 1, "Parameter"),
                        FakeTableCell(0, 1, 1, 2, "Value(mm)"),
                        FakeTableCell(1, 2, 0, 1, "Length"),
                        FakeTableCell(1, 2, 1, 2, "10"),
                        FakeTableCell(2, 3, 0, 1, "Width"),
                        FakeTableCell(2, 3, 1, 2, "8"),
                        FakeTableCell(3, 4, 0, 1, "Thickness"),
                        FakeTableCell(3, 4, 1, 2, "1.6"),
                    ],
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/9",
                    label="caption",
                    text="Table 1. Design parameters",
                    page_no=2,
                    bbox=(40, 720, 220, 705),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/10",
                    label="text",
                    text="The fabricated prototype shows measured bandwidth and return loss.",
                    page_no=2,
                    bbox=(40, 560, 420, 540),
                ),
                0,
            ),
        ],
        page_count=2,
    )
    install_fake_docling(monkeypatch, parsers, document)


def test_build_paper_map_is_lightweight_and_preserves_provenance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_paths = _prepare_phase1_run(tmp_path, monkeypatch)

    paper_map = build_paper_map(run_paths.run_dir)
    payload = paper_map.to_clean_dict()

    assert payload["title"]
    assert payload.get("abstract") is None or len(payload["abstract"]) >= 40
    assert len(payload["section_headings_top_level"]) <= 10
    assert payload["key_design_signals"]["proposed"] >= 1
    assert payload["key_design_signals"]["measured"] >= 1
    assert payload["key_design_signals"]["fabricated"] >= 1
    assert 1 <= len(payload["candidate_design_mentions"]) <= 9
    assert payload["candidate_design_mentions"][0]["evidence_id"]
    assert payload["candidate_design_mentions"][0]["page_number"] >= 1
    assert 1 <= len(payload["key_table_refs"]) <= 5
    assert "rows" not in payload["key_table_refs"][0]
    assert 1 <= len(payload["key_figure_refs"]) <= 5


def test_build_paper_map_uses_discovery_retrieval_for_candidate_mentions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_paths = _prepare_phase1_run(tmp_path, monkeypatch)
    calls: list[tuple[str, int, str]] = []

    class FakeBundleRetriever:
        def __init__(self, run_dir):
            self.run_dir = run_dir
            self.config = RetrievalConfig(chunking_mode="paragraph", embedding_backend="hash", fusion_strategy="weighted")

        def search_text(self, query: str, top_k: int = 5, diagnostics_path=None):
            calls.append((query, top_k, self.config.fusion_strategy))
            if query == "proposed antenna":
                return [
                    {
                        "evidence_id": "chunk:chunk_001",
                        "source_type": "chunk",
                        "page_number": 1,
                        "score": 0.9,
                        "snippet": "This proposed design studies two configurations.",
                    },
                    {
                        "evidence_id": "section:page_001",
                        "source_type": "section",
                        "page_number": 1,
                        "score": 0.85,
                        "snippet": "The rest of the paper is structured as follows. Section 2 describes the design and Section 3 presents the results.",
                    },
                    {
                        "evidence_id": "chunk:chunk_003",
                        "source_type": "chunk",
                        "page_number": 2,
                        "score": 0.8,
                        "snippet": "The antenna geometry is analyzed through return loss and VSWR.",
                    },
                ]
            if query == "final design":
                return [
                    {
                        "evidence_id": "chunk:chunk_002",
                        "source_type": "chunk",
                        "page_number": 1,
                        "score": 0.88,
                        "snippet": "The final optimized design is fabricated and measured.",
                    },
                    {
                        "evidence_id": "chunk:chunk_002",
                        "source_type": "chunk",
                        "page_number": 1,
                        "score": 0.84,
                        "snippet": "The final optimized design is fabricated and measured.",
                    },
                ]
            if query == "design variants":
                return [
                    {
                        "evidence_id": "chunk:chunk_004",
                        "source_type": "chunk",
                        "page_number": 2,
                        "score": 0.75,
                        "snippet": "A modified design is compared with the reference antenna in two configurations.",
                    }
                ]
            return []

        def get_evidence_by_id(self, evidence_id: str):
            payloads = {
                "chunk:chunk_001": {
                    "source_type": "chunk",
                    "text": "This proposed design studies two configurations.",
                },
                "chunk:chunk_002": {
                    "source_type": "chunk",
                    "text": "The final optimized design is fabricated and measured.",
                },
                "chunk:chunk_004": {
                    "source_type": "chunk",
                    "text": "A modified design is compared with the reference antenna in two configurations.",
                },
                "section:page_001": {
                    "source_type": "section",
                    "text": "The rest of the paper is structured as follows. Section 2 describes the design and Section 3 presents the results.",
                },
                "chunk:chunk_003": {
                    "source_type": "chunk",
                    "text": "The antenna geometry is analyzed through return loss and VSWR.",
                },
            }
            return payloads.get(evidence_id)

    monkeypatch.setattr(discovery_module, "BundleRetriever", FakeBundleRetriever)

    paper_map = build_paper_map(run_paths.run_dir).to_clean_dict()

    assert calls
    assert all(top_k == discovery_module.DISCOVERY_TOP_K for _, top_k, _ in calls)
    assert all(fusion_strategy == "rrf" for _, _, fusion_strategy in calls)
    assert [query for query, _, _ in calls] == [
        query
        for _bucket, queries in discovery_module.DISCOVERY_QUERY_BUCKETS
        for query in queries
    ]
    assert paper_map["candidate_design_mentions"] == [
        {
            "text": "This proposed design studies two configurations.",
            "page_number": 1,
            "evidence_id": "chunk:chunk_001",
        },
        {
            "text": "The rest of the paper is structured as follows. Section 2 describes the design and Section 3 presents the results.",
            "page_number": 1,
            "evidence_id": "section:page_001",
        },
        {
            "text": "The antenna geometry is analyzed through return loss and VSWR.",
            "page_number": 2,
            "evidence_id": "chunk:chunk_003",
        },
        {
            "text": "The final optimized design is fabricated and measured.",
            "page_number": 1,
            "evidence_id": "chunk:chunk_002",
        },
        {
            "text": "A modified design is compared with the reference antenna in two configurations.",
            "page_number": 2,
            "evidence_id": "chunk:chunk_004",
        },
    ]


def test_run_phase1_writes_outputs_and_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_paths = _prepare_phase1_run(tmp_path, monkeypatch)
    client = FakeInterpretationClient([_valid_interpretation_payload()])

    paper_map, interpretation_map, report = run_phase1(
        run_paths.run_dir,
        model="gpt-5.4-mini",
        llm_client=client,
        debug=True,
    )

    assert client.calls
    assert client.calls[0]["response_model"] is InterpretationMap
    assert validate_interpretation_map_payload(interpretation_map)
    assert (run_paths.outputs_dir / "paper_map.json").exists()
    assert (run_paths.outputs_dir / "interpretation_map.json").exists()
    assert (run_paths.outputs_dir / "debug" / "phase1_interpretation_messages.json").exists()
    assert report["phase1"]["run"] is True
    assert report["phase1"]["paper_map_status"] == "completed"
    assert report["phase1"]["interpretation_map_status"] == "completed"
    assert report["phase1"]["model_name"] == "gpt-5.4-mini"
    assert paper_map["candidate_design_mentions"]

    saved_report = json.loads(run_paths.extraction_report_path.read_text(encoding="utf-8"))
    assert saved_report["phase1"]["paper_map_path"].endswith("paper_map.json")
    assert saved_report["phase1"]["interpretation_map_path"].endswith("interpretation_map.json")


def _prepare_phase1_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source_pdf = tmp_path / "article.pdf"
    create_interpretation_fixture_pdf(source_pdf)
    _install_markdown_stub(monkeypatch)
    run_paths, _, _ = run_pipeline(source_pdf, base_dir=tmp_path)
    index_run(
        run_paths,
        config=RetrievalConfig(chunking_mode="paragraph", embedding_backend="hash", fusion_strategy="weighted"),
    )
    return run_paths


def _valid_interpretation_payload() -> dict:
    return {
        "has_multiple_variants": True,
        "has_final_design_signal": True,
        "search_queries": [
            {
                "query_id": "Q1",
                "query_text": "final selected antenna design",
                "priority": "high",
                "why": "The paper map suggests multiple configurations and a measured result stage.",
            },
            {
                "query_id": "Q2",
                "query_text": "design parameters of the proposed antenna",
                "priority": "high",
                "why": "A dimensions table is present and should be retrieved next.",
            },
            {
                "query_id": "Q3",
                "query_text": "fabricated prototype measured results",
                "priority": "medium",
                "why": "The paper map shows fabricated and measured signals that may mark the final design.",
            },
        ],
        "open_uncertainties": [
            "Whether the paper contains one design or an early/final variant pair.",
        ],
    }
