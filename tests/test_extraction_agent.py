from __future__ import annotations

import base64
from pathlib import Path

try:
    import pymupdf
except ImportError:  # pragma: no cover
    import fitz as pymupdf  # type: ignore[no-redef]

from mvp.config import RetrievalConfig
from mvp.extraction.agent import RETRIEVAL_PLAN, gather_retrieval_context, gather_retrieval_context_with_phase1
from mvp.index import index_run
from mvp.pipeline import run_pipeline
from mvp.retrieval import BundleRetriever

TEST_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+X2ioAAAAASUVORK5CYII="
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


def test_gather_retrieval_context_runs_with_generic_plan(tmp_path: Path) -> None:
    source_pdf = tmp_path / "article.pdf"
    create_agent_fixture_pdf(source_pdf)

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


def test_gather_retrieval_context_augments_each_block_with_phase1_queries(tmp_path: Path) -> None:
    source_pdf = tmp_path / "article.pdf"
    create_agent_fixture_pdf(source_pdf)

    run_paths, _, _ = run_pipeline(source_pdf, base_dir=tmp_path)
    index_run(
        run_paths,
        config=RetrievalConfig(chunking_mode="paragraph", embedding_backend="hash", fusion_strategy="weighted"),
    )
    retriever = BundleRetriever(run_paths.run_dir)

    retrieval_context = gather_retrieval_context_with_phase1(
        retriever,
        top_k=2,
        phase1_search_queries=[
            {
                "query_id": "Q1",
                "query_text": "proposed antenna geometry",
                "priority": "high",
                "why": "Phase 1 guidance",
            }
        ],
    )

    assert retrieval_context["phase1_guidance_found"] is True
    assert retrieval_context["phase1_search_queries_used"][0]["query_text"] == "proposed antenna geometry"
    for block, entries in retrieval_context["retrieval_queries_used"].items():
        assert any(entry["query_source"] == "base_plan" for entry in entries)
        assert any(
            entry["query_source"] == "phase1_interpretation_map" and entry["query"] == "proposed antenna geometry"
            for entry in entries
        ), block
