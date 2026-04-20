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
from tests.docling_test_stubs import (
    FakeDoc,
    FakePictureItem,
    FakeRef,
    FakeSectionHeaderItem,
    FakeTableCell,
    FakeTableItem,
    FakeTextItem,
    install_fake_docling,
)


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
    document = FakeDoc(
        [
            (
                FakeSectionHeaderItem(
                    self_ref="#/texts/1",
                    label="section_header",
                    text="Introduction",
                    page_no=1,
                    bbox=(40, 760, 180, 740),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/2",
                    label="text",
                    text="The parameters are summarized in Table 1 below for the antenna geometry.",
                    page_no=1,
                    bbox=(40, 720, 520, 700),
                ),
                0,
            ),
            (
                FakeTableItem(
                    self_ref="#/tables/1",
                    label="table",
                    page_no=1,
                    bbox=(40, 660, 360, 560),
                    captions=[FakeRef("#/texts/3")],
                    markdown="Table 1. Dimensions of proposed antenna\n\n| Parameter | Value(mm) |\n| --- | --- |\n| Lgnd | 15 |\n| Wlng | 8 |\n| Lpat | 3.494 |",
                    table_cells=[
                        FakeTableCell(0, 1, 0, 1, "Parameter"),
                        FakeTableCell(0, 1, 1, 2, "Value(mm)"),
                        FakeTableCell(1, 2, 0, 1, "Lgnd"),
                        FakeTableCell(1, 2, 1, 2, "15"),
                        FakeTableCell(2, 3, 0, 1, "Wlng"),
                        FakeTableCell(2, 3, 1, 2, "8"),
                        FakeTableCell(3, 4, 0, 1, "Lpat"),
                        FakeTableCell(3, 4, 1, 2, "3.494"),
                    ],
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/3",
                    label="caption",
                    text="Table 1. Dimensions of proposed antenna",
                    page_no=1,
                    bbox=(40, 680, 280, 665),
                ),
                0,
            ),
            (
                FakePictureItem(
                    self_ref="#/pictures/1",
                    label="picture",
                    page_no=1,
                    bbox=(380, 660, 520, 540),
                    captions=[FakeRef("#/texts/4")],
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/4",
                    label="caption",
                    text="Figure 1. Antenna geometry",
                    page_no=1,
                    bbox=(380, 520, 520, 505),
                ),
                0,
            ),
            (
                FakeSectionHeaderItem(
                    self_ref="#/texts/5",
                    label="section_header",
                    text="Array Parameters",
                    page_no=2,
                    bbox=(40, 760, 220, 740),
                ),
                0,
            ),
            (
                FakeTableItem(
                    self_ref="#/tables/2",
                    label="table",
                    page_no=2,
                    bbox=(40, 700, 420, 600),
                    captions=[FakeRef("#/texts/6")],
                    markdown="Table 2. Spacial Parameter of Antenna array\n\n| Parameter | X-axis | Y-axis | Z-axis |\n| --- | --- | --- | --- |\n| Elements in x, y, z | 2 | 2 | 2 |\n| Space shift in x, y, z | 6 | 1 | 2 |",
                    table_cells=[
                        FakeTableCell(0, 1, 0, 1, "Parameter"),
                        FakeTableCell(0, 1, 1, 2, "X-axis"),
                        FakeTableCell(0, 1, 2, 3, "Y-axis"),
                        FakeTableCell(0, 1, 3, 4, "Z-axis"),
                        FakeTableCell(1, 2, 0, 1, "Elements in x, y, z"),
                        FakeTableCell(1, 2, 1, 2, "2"),
                        FakeTableCell(1, 2, 2, 3, "2"),
                        FakeTableCell(1, 2, 3, 4, "2"),
                        FakeTableCell(2, 3, 0, 1, "Space shift in x, y, z"),
                        FakeTableCell(2, 3, 1, 2, "6"),
                        FakeTableCell(2, 3, 2, 3, "1"),
                        FakeTableCell(2, 3, 3, 4, "2"),
                    ],
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/6",
                    label="caption",
                    text="Table 2. Spacial Parameter of Antenna array",
                    page_no=2,
                    bbox=(40, 720, 320, 705),
                ),
                0,
            ),
            (
                FakeSectionHeaderItem(
                    self_ref="#/texts/7",
                    label="section_header",
                    text="Conclusion",
                    page_no=3,
                    bbox=(40, 760, 180, 740),
                ),
                0,
            ),
            (
                FakeTextItem(
                    self_ref="#/texts/8",
                    label="text",
                    text="Second page content for section generation.",
                    page_no=3,
                    bbox=(40, 720, 260, 700),
                ),
                0,
            ),
        ],
        page_count=3,
    )
    install_fake_docling(monkeypatch, parsers, document)


def test_full_pipeline_generates_bundle_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_pdf = tmp_path / "article.pdf"
    create_test_pdf(source_pdf)
    _install_markdown_stub(monkeypatch)

    run_paths, metadata, parse_report = run_pipeline(source_pdf, base_dir=tmp_path)

    assert run_paths.fulltext_path.exists()
    assert run_paths.sections_path.exists()
    assert run_paths.parse_report_path.exists()
    assert (run_paths.bundle_dir / "page_objects.json").exists()
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
    assert "![Figure](figures/figure_001.png)" in fulltext

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
        "page_object_count",
        "object_counts_by_type",
        "tables_using_structured_export_count",
        "figures_with_explicit_caption_count",
        "figures_with_group_caption_count",
        "figures_with_missing_caption_count",
        "grobid_status",
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
    assert parse_report["page_object_count"] >= 1
    assert parse_report["object_counts_by_type"]["table"] == 2
    assert parse_report["grobid_status"] == "disabled"
