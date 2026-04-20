from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

try:
    import pymupdf
except ImportError:  # pragma: no cover
    import fitz as pymupdf  # type: ignore[no-redef]

from mvp.config import CONFIG_PRESETS, DEFAULT_CONFIG_NAME, RetrievalConfig
from mvp.index import index_run
from mvp import parsers
from mvp.pipeline import run_pipeline
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


def _install_markdown_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    document = FakeDoc(
        [
            (
                FakeSectionHeaderItem(
                    self_ref="#/texts/1",
                    label="section_header",
                    text="Materials and Design",
                    page_no=1,
                    bbox=(40, 760, 240, 740),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/2",
                    label="text",
                    text="The substrate material is Rogers RT5880 and the operating frequency is 28 GHz.",
                    page_no=1,
                    bbox=(40, 720, 480, 700),
                ),
                0,
            ),
            (
                FakePictureItem(
                    self_ref="#/pictures/1",
                    label="picture",
                    page_no=1,
                    bbox=(40, 660, 220, 520),
                    captions=[FakeRef("#/texts/3")],
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/3",
                    label="caption",
                    text="Figure 1. Operating frequency response",
                    page_no=1,
                    bbox=(40, 500, 300, 485),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/4",
                    label="text",
                    text="This figure shows the operating frequency response near 28 GHz.",
                    page_no=1,
                    bbox=(40, 470, 420, 450),
                ),
                0,
            ),
            (
                FakeSectionHeaderItem(
                    self_ref="#/texts/5",
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
                    bbox=(40, 700, 340, 600),
                    captions=[FakeRef("#/texts/6")],
                    markdown="Table 1. Dimensions of proposed antenna\n\n| Parameter | Value(mm) |\n| --- | --- |\n| Lgnd | 15 |\n| Wpat | 5.3 |\n| FeedWidth | 0.1 |",
                    table_cells=[
                        FakeTableCell(0, 1, 0, 1, "Parameter"),
                        FakeTableCell(0, 1, 1, 2, "Value(mm)"),
                        FakeTableCell(1, 2, 0, 1, "Lgnd"),
                        FakeTableCell(1, 2, 1, 2, "15"),
                        FakeTableCell(2, 3, 0, 1, "Wpat"),
                        FakeTableCell(2, 3, 1, 2, "5.3"),
                        FakeTableCell(3, 4, 0, 1, "FeedWidth"),
                        FakeTableCell(3, 4, 1, 2, "0.1"),
                    ],
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/6",
                    label="caption",
                    text="Table 1. Dimensions of proposed antenna",
                    page_no=2,
                    bbox=(40, 720, 320, 705),
                ),
                0,
            ),
        ],
        page_count=2,
    )
    install_fake_docling(monkeypatch, parsers, document)


def test_index_stage_creates_expected_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_pdf = tmp_path / "article.pdf"
    create_index_fixture_pdf(source_pdf)
    _install_markdown_stub(monkeypatch)

    run_paths, _, _ = run_pipeline(source_pdf, base_dir=tmp_path)
    index_report = index_run(
        run_paths,
        config=RetrievalConfig(chunking_mode="paragraph", embedding_backend="hash", fusion_strategy="weighted"),
    )

    assert run_paths.indexes_dir.exists()
    assert run_paths.bm25_dir.exists()
    assert run_paths.faiss_dir.exists()
    assert run_paths.graph_path.exists()
    assert run_paths.index_report_path.exists()
    assert run_paths.index_config_path.exists()
    assert (run_paths.bm25_dir / "evidence_items.json").exists()
    assert (run_paths.bm25_dir / "bm25_stats.json").exists()
    assert (run_paths.faiss_dir / "evidence_items.json").exists()
    assert (run_paths.faiss_dir / "embedding_meta.json").exists()
    assert (run_paths.faiss_dir / "index.faiss").exists()

    evidence_items = json.loads((run_paths.bm25_dir / "evidence_items.json").read_text(encoding="utf-8"))
    source_types = {item["source_type"] for item in evidence_items}
    assert {"section", "table", "figure"}.issubset(source_types)
    assert any(item["source_type"] == "chunk" and item["metadata"]["chunking_mode"] == "paragraph" for item in evidence_items)

    graph = json.loads(run_paths.graph_path.read_text(encoding="utf-8"))
    relations = {edge["relation"] for edge in graph["edges"]}
    assert "has_caption" in relations
    assert "has_content" in relations
    assert "has_context" in relations

    embedding_meta = json.loads((run_paths.faiss_dir / "embedding_meta.json").read_text(encoding="utf-8"))
    assert embedding_meta["backend"] == "hash"
    assert embedding_meta["model_name"] == "hash_embedding_v1"
    assert embedding_meta["dim"] == 256
    assert "index_build_timestamp_utc" in embedding_meta

    assert index_report["status"] == "completed"
    assert index_report["evidence_item_count"] >= 3


def test_default_retrieval_config_promotes_paragraph_real_embedding() -> None:
    config = RetrievalConfig()

    assert DEFAULT_CONFIG_NAME == "paragraph_real_embedding"
    assert config.chunking_mode == "paragraph"
    assert config.chunk_overlap_pct == 0.15
    assert config.paragraph_min_chars == 120
    assert config.paragraph_max_chars == 800
    assert config.embedding_backend == "sentence_transformer"
    assert config.embedding_model_name == "sentence-transformers/all-MiniLM-L6-v2"
    assert config.fusion_strategy == "weighted"
    assert config.weighted_alpha == 0.7
    assert config.weighted_beta == 0.3
    assert config.rrf_k == 60
    assert CONFIG_PRESETS["baseline_current"].embedding_backend == "hash"
    assert CONFIG_PRESETS["paragraph_real_embedding"].embedding_backend == "sentence_transformer"
