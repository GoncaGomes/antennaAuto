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


def _install_markdown_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_to_markdown(path: str, **kwargs):
        image_dir = Path(kwargs["image_path"])
        image_dir.mkdir(parents=True, exist_ok=True)
        (image_dir / "article.pdf-0001-01.png").write_bytes(TEST_PNG)
        return [
            {
                "metadata": {"page_number": 1},
                "text": "\n".join(
                    [
                        "# Materials and Design",
                        "The substrate material is Rogers RT5880 and the operating frequency is 28 GHz.",
                        "![Image](figures/article.pdf-0001-01.png)",
                        "Figure 1. Operating frequency response",
                        "This figure shows the operating frequency response near 28 GHz.",
                    ]
                ),
            },
            {
                "metadata": {"page_number": 2},
                "text": "\n".join(
                    [
                        "## Parameters",
                        "Table 1. Dimensions of proposed antenna",
                        "| Parameter | Value(mm) |",
                        "| --- | --- |",
                        "| Lgnd | 15 |",
                        "| Wpat | 5.3 |",
                        "| FeedWidth | 0.1 |",
                    ]
                ),
            },
        ]

    monkeypatch.setattr(parsers.pymupdf4llm, "to_markdown", fake_to_markdown)


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
