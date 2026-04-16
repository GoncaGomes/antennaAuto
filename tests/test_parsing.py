from __future__ import annotations

import json
from pathlib import Path

try:
    import pymupdf
except ImportError:  # pragma: no cover
    import fitz as pymupdf  # type: ignore[no-redef]

from mvp.pipeline import run_pipeline
from mvp.parsers import detect_table_caption_lines, validate_table_rows


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


def test_detect_table_caption_lines() -> None:
    text = (
        "Introduction\n"
        "The parameters are summarized in Table 1 below.\n"
        "Table 1. Dimensions of proposed antenna\n"
        "Table 2 Spacial Parameter of Antenna array\n"
    )

    captions = detect_table_caption_lines(text)

    assert captions == [
        "Table 1. Dimensions of proposed antenna",
        "Table 2 Spacial Parameter of Antenna array",
    ]


def test_detect_table_caption_lines_supports_roman_numerals() -> None:
    text = (
        "Introduction\n"
        "As discussed in Table I, the patch is compact.\n"
        "TABLE I\n"
        "ANTENNA PARAMETERS\n"
        "Table IV: Comparison of gain values\n"
    )

    captions = detect_table_caption_lines(text)

    assert captions == [
        "TABLE I ANTENNA PARAMETERS",
        "Table IV: Comparison of gain values",
    ]


def test_validate_table_rows() -> None:
    assert validate_table_rows([["Parameter", "Value"], ["Width", "10 mm"]]) is True
    assert validate_table_rows([["Parameter", "Value"], ["This is just a paragraph", "text"]]) is False
    assert validate_table_rows([["This is just a paragraph"], ["Still one column"]]) is False


def test_full_pipeline_generates_bundle_outputs(tmp_path: Path) -> None:
    source_pdf = tmp_path / "article.pdf"
    create_test_pdf(source_pdf)

    run_paths, metadata, parse_report = run_pipeline(source_pdf, base_dir=tmp_path)

    assert run_paths.fulltext_path.exists()
    assert run_paths.sections_path.exists()
    assert run_paths.parse_report_path.exists()
    assert run_paths.tables_dir.exists()
    assert run_paths.figures_dir.exists()
    assert metadata["page_count"] == 3

    sections = json.loads(run_paths.sections_path.read_text(encoding="utf-8"))
    assert len(sections) == 3

    table_001 = json.loads((run_paths.tables_dir / "table_001.json").read_text(encoding="utf-8"))
    table_002 = json.loads((run_paths.tables_dir / "table_002.json").read_text(encoding="utf-8"))
    fallback_dir = run_paths.tables_dir / "table_003"

    assert table_001["structured"] is True
    assert table_001["extraction_method"] == "text_parameter_value"
    assert isinstance(table_001["parse_score"], float)
    assert table_001["parse_quality"] == "complete"
    assert table_001["candidate_scores_summary"]
    assert table_001["shape"] == {"rows": 4, "cols": 2}
    assert table_001["rows"][0] == ["Parameter", "Value(mm)"]
    assert table_002["structured"] is True
    assert table_002["extraction_method"] == "text_axis_columns"
    assert isinstance(table_002["parse_score"], float)
    assert table_002["parse_quality"] == "complete"
    assert table_002["candidate_scores_summary"]
    assert table_002["shape"] == {"rows": 3, "cols": 4}
    assert table_002["rows"][0] == ["Parameter", "X-axis", "Y-axis", "Z-axis"]
    assert (run_paths.tables_dir / "table_001.csv").exists()
    assert (run_paths.tables_dir / "table_001.md").exists()
    assert (run_paths.tables_dir / "table_002.csv").exists()
    assert (run_paths.tables_dir / "table_002.md").exists()
    assert not (run_paths.tables_dir / "table_001").exists()
    assert not (run_paths.tables_dir / "table_002").exists()
    assert fallback_dir.exists()
    assert not (run_paths.tables_dir / "table_003.json").exists()
    assert (fallback_dir / "caption.txt").exists()
    assert (fallback_dir / "context.txt").exists()
    assert (fallback_dir / "crop.png").exists()
    fallback_meta = json.loads((fallback_dir / "table.json").read_text(encoding="utf-8"))
    assert fallback_meta["structured"] is False
    assert fallback_meta["parse_quality"] in {"partial", "noisy", "weak"}
    assert fallback_meta["candidate_scores_summary"]
    assert isinstance(fallback_meta["parse_score"], float)

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
        "parser_versions",
        "warnings",
    }
    assert expected_report_keys.issubset(parse_report)
    assert parse_report["page_count"] == 3
    assert parse_report["table_caption_candidates_found"] == 3
    assert parse_report["table_candidates_deduplicated"] == 3
    assert parse_report["table_regions_cropped"] == 3
    assert parse_report["tables_extracted_structured"] == 2
    assert parse_report["tables_saved_as_fallback_only"] == 1
    assert parse_report["tables_rejected_validation"] == 0
    assert parse_report["extracted_table_count"] == 2
    assert parse_report["fulltext_generated"] is True
    assert parse_report["sections_generated"] is True
    assert len(parse_report["table_summaries"]) == 3
