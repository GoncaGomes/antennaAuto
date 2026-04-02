from __future__ import annotations

import base64
from pathlib import Path

try:
    import pymupdf
except ImportError:  # pragma: no cover
    import fitz as pymupdf  # type: ignore[no-redef]

from mvp.config import RetrievalConfig
from mvp.index import index_run
from mvp.pipeline import run_pipeline
from mvp.retrieval import BundleRetriever

TEST_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+X2ioAAAAASUVORK5CYII="
)


def create_index_fixture_pdf(path: Path) -> None:
    image_path = path.with_suffix(".png")
    image_path.write_bytes(TEST_PNG)

    document = pymupdf.open()
    page_one = document.new_page()
    page_one.insert_text(
        (72, 72),
        (
            "Materials and Design\n\n"
            "The substrate material is Rogers RT5880 and the operating frequency is 28 GHz."
        ),
    )
    page_one.insert_image(pymupdf.Rect(72, 150, 180, 230), filename=str(image_path))
    page_one.insert_text(
        (72, 250),
        "Figure 1. Operating frequency response\nThis figure shows the operating frequency response near 28 GHz.",
    )

    page_two = document.new_page()
    page_two.insert_text(
        (72, 72),
        (
            "Table 1. Dimensions of proposed antenna\n"
            "Parameter Value(mm)\n"
            "Lgnd 15\n"
            "Wpat 5.3\n"
            "FeedWidth 0.1\n"
            "4. Conclusion\n"
            "Testing text after the table."
        ),
    )

    document.save(path)
    document.close()


def test_retrieval_helpers_return_plausible_results(tmp_path: Path) -> None:
    source_pdf = tmp_path / "article.pdf"
    create_index_fixture_pdf(source_pdf)

    run_paths, _, _ = run_pipeline(source_pdf, base_dir=tmp_path)
    index_run(
        run_paths,
        config=RetrievalConfig(chunking_mode="paragraph", embedding_backend="hash", fusion_strategy="weighted"),
    )
    retriever = BundleRetriever(run_paths.run_dir)

    text_results = retriever.search_text("substrate material", top_k=3)
    table_results = retriever.search_tables("antenna dimensions", top_k=3)
    figure_results = retriever.search_figures("operating frequency", top_k=3)

    assert text_results
    assert text_results[0]["source_type"] in {"section", "chunk"}
    assert "rogers" in text_results[0]["snippet"].lower() or "substrate" in text_results[0]["snippet"].lower()

    assert table_results
    assert table_results[0]["source_type"] == "table"
    assert table_results[0]["source_id"] == "table_001"

    assert figure_results
    assert figure_results[0]["source_type"] == "figure"
    assert figure_results[0]["source_id"] == "fig_001"

    section = retriever.get_section("page_001")
    table = retriever.get_table("table_001")
    figure = retriever.get_figure("fig_001")

    assert section is not None
    assert table is not None
    assert table["caption"] == "Table 1. Dimensions of proposed antenna"
    assert figure is not None
    assert figure["page_number"] == 1

    assert "bm25_score" in text_results[0]
    assert "dense_score" in text_results[0]
    assert "weighted_score" in text_results[0]
    assert text_results[0]["fusion_strategy"] == "weighted"
    assert text_results[0]["chunking_mode"] == "paragraph"
    assert text_results[0]["embedding_backend"] == "hash"


def test_rrf_retrieval_returns_rank_diagnostics(tmp_path: Path) -> None:
    source_pdf = tmp_path / "article.pdf"
    create_index_fixture_pdf(source_pdf)

    run_paths, _, _ = run_pipeline(source_pdf, base_dir=tmp_path)
    config = RetrievalConfig(chunking_mode="paragraph", embedding_backend="hash", fusion_strategy="rrf")
    index_run(run_paths, config=config)
    retriever = BundleRetriever(run_paths.run_dir, config=config)

    results = retriever.search_text("Rogers RT5880", top_k=3)

    assert results
    assert results[0]["fusion_strategy"] == "rrf"
    assert "rrf_score" in results[0]
    assert "final_rank" in results[0]
