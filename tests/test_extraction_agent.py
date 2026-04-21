from __future__ import annotations

import base64
from pathlib import Path

import pytest

try:
    import pymupdf
except ImportError:  # pragma: no cover
    import fitz as pymupdf  # type: ignore[no-redef]

from mvp.config import RetrievalConfig
from mvp.extraction.agent import RETRIEVAL_PLAN, gather_retrieval_context, gather_retrieval_context_with_phase1
from mvp.index import index_run
from mvp import parsers
from mvp.pipeline import run_pipeline
from mvp.retrieval import BundleRetriever
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


def create_agent_fixture_pdf(path: Path) -> None:
    image_path = path.with_suffix(".png")
    image_path.write_bytes(TEST_PNG)

    document = pymupdf.open()
    page_one = document.new_page()
    page_one.insert_text(
        (72, 72),
        (
            "Abstract\n\n"
            "This proposed design is an antenna configuration with a radiating element over a ground plane. "
            "The substrate material is a dielectric material and the conductor material forms the radiating element. "
            "The feeding method and feed type use an input port, and the feed location is tuned for matching. "
            "Bandwidth, gain, return loss, and VSWR are reported.\n\n"
            "The layer stack includes substrate and metal layers."
        ),
    )
    page_one.insert_image(pymupdf.Rect(72, 200, 180, 280), filename=str(image_path))
    page_one.insert_text(
        (72, 300),
        "Figure 1. Antenna geometry\nThe figure shows the radiating element and ground plane geometry.",
    )

    page_two = document.new_page()
    page_two.insert_text(
        (72, 72),
        (
            "Table 1. Design parameters\n"
            "Parameter Value(mm)\n"
            "Length 10\n"
            "Width 8\n"
            "Thickness 1.6\n"
            "OperatingFrequency 28\n\n"
            "Feed type: microstrip feed.\n"
            "Feeding method: line feed.\n"
            "Feed location: edge location.\n"
            "Input port: standard feed connector.\n"
            "Bandwidth: 2.5 GHz.\n"
            "Gain: 6 dBi.\n"
            "Return loss: -18 dB.\n"
            "VSWR: 1.4.\n"
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
                    text="Abstract",
                    page_no=1,
                    bbox=(40, 760, 140, 740),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/2",
                    label="text",
                    text="This proposed design is an antenna configuration with a radiating element over a ground plane.",
                    page_no=1,
                    bbox=(40, 720, 520, 700),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/3",
                    label="text",
                    text="The substrate material is a dielectric material and the conductor material forms the radiating element.",
                    page_no=1,
                    bbox=(40, 690, 520, 670),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/4",
                    label="text",
                    text="The feeding method and feed type use an input port, and the feed location is tuned for matching.",
                    page_no=1,
                    bbox=(40, 660, 520, 640),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/5",
                    label="text",
                    text="Bandwidth, gain, return loss, and VSWR are reported.",
                    page_no=1,
                    bbox=(40, 630, 420, 610),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/6",
                    label="text",
                    text="The layer stack includes substrate and metal layers.",
                    page_no=1,
                    bbox=(40, 600, 360, 580),
                ),
                0,
            ),
            (
                FakePictureItem(
                    self_ref="#/pictures/1",
                    label="picture",
                    page_no=1,
                    bbox=(40, 560, 220, 420),
                    captions=[FakeRef("#/texts/7")],
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/7",
                    label="caption",
                    text="Figure 1. Antenna geometry",
                    page_no=1,
                    bbox=(40, 400, 260, 385),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/8",
                    label="text",
                    text="The figure shows the radiating element and ground plane geometry.",
                    page_no=1,
                    bbox=(40, 370, 460, 350),
                ),
                0,
            ),
            (
                FakeSectionHeaderItem(
                    self_ref="#/texts/9",
                    label="section_header",
                    text="Parameters",
                    page_no=2,
                    bbox=(40, 760, 180, 740),
                ),
                0,
            ),
            (
                FakeTableItem(
                    self_ref="#/tables/1",
                    label="table",
                    page_no=2,
                    bbox=(40, 700, 360, 580),
                    captions=[FakeRef("#/texts/10")],
                    markdown="Table 1. Design parameters\n\n| Parameter | Value(mm) |\n| --- | --- |\n| Length | 10 |\n| Width | 8 |\n| Thickness | 1.6 |\n| OperatingFrequency | 28 |",
                    table_cells=[
                        FakeTableCell(0, 1, 0, 1, "Parameter"),
                        FakeTableCell(0, 1, 1, 2, "Value(mm)"),
                        FakeTableCell(1, 2, 0, 1, "Length"),
                        FakeTableCell(1, 2, 1, 2, "10"),
                        FakeTableCell(2, 3, 0, 1, "Width"),
                        FakeTableCell(2, 3, 1, 2, "8"),
                        FakeTableCell(3, 4, 0, 1, "Thickness"),
                        FakeTableCell(3, 4, 1, 2, "1.6"),
                        FakeTableCell(4, 5, 0, 1, "OperatingFrequency"),
                        FakeTableCell(4, 5, 1, 2, "28"),
                    ],
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/10",
                    label="caption",
                    text="Table 1. Design parameters",
                    page_no=2,
                    bbox=(40, 720, 240, 705),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/11",
                    label="text",
                    text="Feed type: microstrip feed.",
                    page_no=2,
                    bbox=(40, 540, 280, 520),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/12",
                    label="text",
                    text="Feeding method: line feed.",
                    page_no=2,
                    bbox=(40, 510, 280, 490),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/13",
                    label="text",
                    text="Feed location: edge location.",
                    page_no=2,
                    bbox=(40, 480, 280, 460),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/14",
                    label="text",
                    text="Input port: standard feed connector.",
                    page_no=2,
                    bbox=(40, 450, 320, 430),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/15",
                    label="text",
                    text="Bandwidth: 2.5 GHz.",
                    page_no=2,
                    bbox=(40, 420, 200, 400),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/16",
                    label="text",
                    text="Gain: 6 dBi.",
                    page_no=2,
                    bbox=(40, 390, 160, 370),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/17",
                    label="text",
                    text="Return loss: -18 dB.",
                    page_no=2,
                    bbox=(40, 360, 220, 340),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/18",
                    label="text",
                    text="VSWR: 1.4.",
                    page_no=2,
                    bbox=(40, 330, 140, 310),
                ),
                0,
            ),
        ],
        page_count=2,
    )
    install_fake_docling(monkeypatch, parsers, document)


def test_retrieval_plan_uses_generic_queries() -> None:
    all_queries = {query for entries in RETRIEVAL_PLAN.values() for _, query in entries}

    assert "Rogers RT5880" not in all_queries
    assert "ground plane substrate patch" not in all_queries
    assert "patch geometry" not in all_queries
    assert "slot notch inset feed" not in all_queries
    assert "inset feed" not in all_queries

    assert "proposed design" in all_queries
    assert "final design" in all_queries
    assert "dielectric material" in all_queries
    assert "conductor material" in all_queries
    assert "layer stack" in all_queries
    assert "design parameters" in all_queries
    assert "radiating element" in all_queries
    assert "feeding method" in all_queries
    assert "input port" in all_queries
    assert "return loss" in all_queries


def test_gather_retrieval_context_runs_with_generic_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_pdf = tmp_path / "article.pdf"
    create_agent_fixture_pdf(source_pdf)
    _install_markdown_stub(monkeypatch)

    run_paths, _, _ = run_pipeline(source_pdf, base_dir=tmp_path)
    index_run(
        run_paths,
        config=RetrievalConfig(chunking_mode="paragraph", embedding_backend="hash", fusion_strategy="weighted"),
    )
    retriever = BundleRetriever(run_paths.run_dir)

    retrieval_context = gather_retrieval_context(retriever, top_k=3)

    assert set(retrieval_context["retrieval_queries_used"]) == set(RETRIEVAL_PLAN)
    assert retrieval_context["evidence_ids_by_block"]["classification"]
    assert retrieval_context["evidence_ids_by_block"]["parameters"]
    assert retrieval_context["evidence_ids_by_block"]["entities"]
    assert retrieval_context["evidence_ids_by_block"]["feeds"]
    assert retrieval_context["evidence_ids_by_block"]["quality"]
    assert any(evidence_id.startswith("table:") for evidence_id in retrieval_context["evidence_ids_by_block"]["parameters"])
    assert retrieval_context["run_context"]["original_filename"] == "article.pdf"
    assert retrieval_context["all_retrieved_evidence_ids"]


def test_gather_retrieval_context_routes_phase1_queries_by_modality(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_pdf = tmp_path / "article.pdf"
    create_agent_fixture_pdf(source_pdf)
    _install_markdown_stub(monkeypatch)

    run_paths, _, _ = run_pipeline(source_pdf, base_dir=tmp_path)
    index_run(
        run_paths,
        config=RetrievalConfig(chunking_mode="paragraph", embedding_backend="hash", fusion_strategy="weighted"),
    )
    retriever = BundleRetriever(run_paths.run_dir)

    retrieval_context = gather_retrieval_context_with_phase1(
        retriever,
        top_k=5,
        phase1_search_queries=[
            {
                "query_id": "Q1",
                "query_text": "final selected design",
                "priority": "high",
                "why": "Phase 1 guidance",
            },
            {
                "query_id": "Q2",
                "query_text": "parameter dimensions table",
                "priority": "medium",
                "why": "Phase 1 guidance",
            },
            {
                "query_id": "Q3",
                "query_text": "geometry figure layout",
                "priority": "high",
                "why": "Phase 1 guidance",
            },
        ],
    )

    assert retrieval_context["phase1_guidance_found"] is True
    assert retrieval_context["phase1_search_queries_used"][0]["query_text"] == "final selected design"
    for block, entries in retrieval_context["retrieval_queries_used"].items():
        assert any(entry["query_source"] == "base_plan" for entry in entries)
        phase1_entries = [entry for entry in entries if entry["query_source"] == "phase1_interpretation_map"]
        block_search_types = {search_type for search_type, _ in RETRIEVAL_PLAN[block]}
        assert any(entry["query"] == "final selected design" and entry["search_type"] == "text" for entry in phase1_entries)
        assert not any(entry["query"] == "final selected design" and entry["search_type"] != "text" for entry in phase1_entries)
        if "tables" in block_search_types:
            assert any(entry["query"] == "parameter dimensions table" and entry["search_type"] == "tables" for entry in phase1_entries)
        if "figures" in block_search_types:
            assert any(entry["query"] == "geometry figure layout" and entry["search_type"] == "figures" for entry in phase1_entries)
        assert all(len(entry["result_evidence_ids"]) <= 3 for entry in phase1_entries)
