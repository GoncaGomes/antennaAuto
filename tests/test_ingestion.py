from __future__ import annotations

import json
from pathlib import Path

try:
    import pymupdf
except ImportError:  # pragma: no cover
    import fitz as pymupdf  # type: ignore[no-redef]

from mvp.pipeline import ingest_pdf


def create_test_pdf(path: Path) -> None:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Test Article\n\nMinimal PDF for ingestion tests.")
    document.save(path)
    document.close()


def test_ingestion_creates_run_bundle(tmp_path: Path) -> None:
    source_pdf = tmp_path / "source.pdf"
    create_test_pdf(source_pdf)

    run_paths = ingest_pdf(source_pdf, base_dir=tmp_path)

    assert run_paths.run_dir.exists()
    assert run_paths.input_dir.exists()
    assert run_paths.bundle_dir.exists()
    assert run_paths.tables_dir.exists()
    assert run_paths.figures_dir.exists()
    assert run_paths.article_pdf.exists()
    assert run_paths.metadata_path.exists()
    assert run_paths.parse_report_path.exists()
    assert (tmp_path / "reports").exists()

    metadata = json.loads(run_paths.metadata_path.read_text(encoding="utf-8"))
    expected_keys = {
        "run_id",
        "original_filename",
        "original_path",
        "file_size_bytes",
        "sha256",
        "ingestion_timestamp_utc",
        "page_count",
        "pdf_metadata",
    }
    assert expected_keys.issubset(metadata)
    assert metadata["original_filename"] == "source.pdf"
    assert metadata["page_count"] == 1

    parse_report = json.loads(run_paths.parse_report_path.read_text(encoding="utf-8"))
    assert parse_report["status"] == "ingested"
