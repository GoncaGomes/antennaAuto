from __future__ import annotations

import json
from pathlib import Path

import pytest

try:
    import pymupdf
except ImportError:  # pragma: no cover
    import fitz as pymupdf  # type: ignore[no-redef]

from mvp import parsers
from mvp.pipeline import run_pipeline


def create_test_pdf(path: Path) -> None:
    document = pymupdf.open()
    page_one = document.new_page()
    page_one.insert_text(
        (72, 72),
        (
            "Introduction\n\n"
            "The parameters are summarized in Table 1 below for the antenna geometry.\n"
            "Table 1. Dimensions of proposed antenna\n"
            "Parameter Value(mm)\n"
            "Lgnd 15\n"
            "Wlng 8\n"
            "Lpat 3.494"
        ),
    )
    page_two = document.new_page()
    page_two.insert_text(
        (72, 72),
        (
            "Table 2 Spacial Parameter of Antenna array\n"
            "X-axis Y-axis Z-axis\n"
            "Elements in x, y, z 2 2 2\n"
            "Space shift in x, y, z 6 1 2\n"
            "4. Conclusion\n"
            "Second page content for section generation."
        ),
    )
    page_three = document.new_page()
    page_three.insert_text(
        (72, 72),
        (
            "Table 3. Unsupported layout\n"
            "This paragraph sits below the caption and acts as fallback evidence text.\n"
            "It is intentionally prose, not a real structured table."
        ),
    )
    document.save(path)
    document.close()


def _install_markdown_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_to_markdown(path: str, **kwargs):
        image_dir = Path(kwargs["image_path"])
        image_dir.mkdir(parents=True, exist_ok=True)
        (image_dir / "article.pdf-0001-01.png").write_bytes(b"png")
        return [
            {
                "metadata": {"page_number": 1},
                "text": "\n".join(
                    [
                        "# Introduction",
                        "The parameters are summarized in Table 1 below for the antenna geometry.",
                        "Table 1. Dimensions of proposed antenna",
                        "| Parameter | Value(mm) |",
                        "| --- | --- |",
                        "| Lgnd | 15 |",
                        "| Wlng | 8 |",
                        "| Lpat | 3.494 |",
                        "![Image](figures/article.pdf-0001-01.png)",
                        "Figure 1. Antenna geometry",
                    ]
                ),
            },
            {
                "metadata": {"page_number": 2},
                "text": "\n".join(
                    [
                        "## Array Parameters",
                        "Table 2 Spacial Parameter of Antenna array",
                        "| Parameter | X-axis | Y-axis | Z-axis |",
                        "| --- | --- | --- | --- |",
                        "| Elements in x, y, z | 2 | 2 | 2 |",
                        "| Space shift in x, y, z | 6 | 1 | 2 |",
                    ]
                ),
            },
            {
                "metadata": {"page_number": 3},
                "text": "## Conclusion\nSecond page content for section generation.",
            },
        ]

    monkeypatch.setattr(parsers.pymupdf4llm, "to_markdown", fake_to_markdown)


def test_full_pipeline_generates_bundle_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_pdf = tmp_path / "article.pdf"
    create_test_pdf(source_pdf)
    _install_markdown_stub(monkeypatch)

    run_paths, metadata, parse_report = run_pipeline(source_pdf, base_dir=tmp_path)

    assert run_paths.fulltext_path.exists()
    assert run_paths.sections_path.exists()
    assert run_paths.parse_report_path.exists()
    assert run_paths.tables_dir.exists()
    assert run_paths.figures_dir.exists()
    assert metadata["page_count"] == 3

    sections = json.loads(run_paths.sections_path.read_text(encoding="utf-8"))
    assert sections
    assert set(sections[0]) == {"section_id", "title", "text_excerpt"}
    assert not any("page_start" in section or "page_end" in section for section in sections)

    table_paths = sorted(run_paths.tables_dir.glob("table_*.md"))
    assert table_paths
    assert not list(run_paths.tables_dir.glob("table_*.json"))
    assert not list(run_paths.tables_dir.glob("table_*.csv"))
    table_markdown = table_paths[0].read_text(encoding="utf-8")
    assert "|" in table_markdown

    figure_paths = sorted(run_paths.figures_dir.glob("*.png"))
    assert figure_paths
    assert not list(run_paths.figures_dir.glob("fig_*"))

    fulltext = run_paths.fulltext_path.read_text(encoding="utf-8")
    assert "![Image]" in fulltext or "![]" in fulltext

    expected_report_keys = {
        "status",
        "message",
        "page_count",
        "table_caption_candidates_found",
        "table_candidates_deduplicated",
        "table_regions_cropped",
        "tables_extracted_structured",
        "tables_saved_as_fallback_only",
        "tables_rejected_validation",
        "extracted_image_count",
        "extracted_table_count",
        "fulltext_generated",
        "sections_generated",
        "table_summaries",
        "figure_summaries",
        "page_summaries",
        "parser_versions",
        "warnings",
    }
    assert expected_report_keys.issubset(parse_report)
    assert parse_report["page_count"] == 3
    assert parse_report["table_caption_candidates_found"] == parse_report["extracted_table_count"]
    assert parse_report["table_candidates_deduplicated"] == parse_report["extracted_table_count"]
    assert parse_report["table_regions_cropped"] == 0
    assert parse_report["tables_extracted_structured"] == parse_report["extracted_table_count"]
    assert parse_report["tables_saved_as_fallback_only"] == 0
    assert parse_report["tables_rejected_validation"] == 0
    assert parse_report["extracted_table_count"] >= 1
    assert parse_report["fulltext_generated"] is True
    assert parse_report["sections_generated"] is True
    assert parse_report["table_summaries"]
    assert parse_report["figure_summaries"]
    assert len(parse_report["page_summaries"]) == 3
