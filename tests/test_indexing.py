from __future__ import annotations

import base64
import json
from pathlib import Path

try:
    import pymupdf
except ImportError:  # pragma: no cover
    import fitz as pymupdf  # type: ignore[no-redef]

from mvp.index import index_run
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


def test_index_stage_creates_expected_artifacts(tmp_path: Path) -> None:
    source_pdf = tmp_path / "article.pdf"
    create_index_fixture_pdf(source_pdf)

    run_paths, _, _ = run_pipeline(source_pdf, base_dir=tmp_path)
    index_report = index_run(run_paths)

    assert run_paths.indexes_dir.exists()
    assert run_paths.bm25_dir.exists()
    assert run_paths.faiss_dir.exists()
    assert run_paths.graph_path.exists()
    assert run_paths.index_report_path.exists()
    assert (run_paths.bm25_dir / "evidence_items.json").exists()
    assert (run_paths.bm25_dir / "bm25_stats.json").exists()
    assert (run_paths.faiss_dir / "evidence_items.json").exists()
    assert (run_paths.faiss_dir / "embedding_meta.json").exists()
    assert (run_paths.faiss_dir / "index.faiss").exists()

    evidence_items = json.loads((run_paths.bm25_dir / "evidence_items.json").read_text(encoding="utf-8"))
    source_types = {item["source_type"] for item in evidence_items}
    assert {"section", "table", "figure"}.issubset(source_types)

    graph = json.loads(run_paths.graph_path.read_text(encoding="utf-8"))
    relations = {edge["relation"] for edge in graph["edges"]}
    assert "has_table" in relations
    assert "has_figure" in relations

    assert index_report["status"] == "completed"
    assert index_report["evidence_item_count"] >= 3
