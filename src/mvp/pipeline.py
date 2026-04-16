from __future__ import annotations

from pathlib import Path
from typing import Any

from .bundle import RunPaths, load_run_paths, prepare_run_bundle
from .config import RetrievalConfig
from .index import index_run
from .parsers import (
    extract_images,
    extract_markdown,
    extract_tables,
    generate_sections,
    get_pdf_details,
    parser_versions,
)
from .utils import ensure_reports_dir, project_root, read_json, sha256_file, utc_timestamp, write_json


def _initial_parse_report(page_count: int) -> dict[str, Any]:
    return {
        "status": "ingested",
        "message": "PDF copied into run folder. Parsing not started.",
        "page_count": page_count,
        "table_caption_candidates_found": 0,
        "table_candidates_deduplicated": 0,
        "tables_extracted_structured": 0,
        "tables_saved_as_fallback_only": 0,
        "tables_rejected_validation": 0,
        "table_regions_cropped": 0,
        "extracted_image_count": 0,
        "extracted_table_count": 0,
        "fulltext_generated": False,
        "sections_generated": False,
        "table_summaries": [],
        "parser_versions": parser_versions(),
        "warnings": [],
    }


def ingest_pdf(input_pdf: str | Path, base_dir: str | Path | None = None) -> RunPaths:
    source_pdf = Path(input_pdf)
    base_path = Path(base_dir).resolve() if base_dir else project_root()

    ensure_reports_dir(base_path)
    run_paths = prepare_run_bundle(source_pdf, base_path)
    pdf_details = get_pdf_details(run_paths.article_pdf)

    metadata = {
        "run_id": run_paths.run_id,
        "original_filename": source_pdf.name,
        "original_path": str(source_pdf.expanduser().resolve()),
        "file_size_bytes": run_paths.article_pdf.stat().st_size,
        "sha256": sha256_file(run_paths.article_pdf),
        "ingestion_timestamp_utc": utc_timestamp(),
        "page_count": pdf_details["page_count"],
        "pdf_metadata": pdf_details["pdf_metadata"],
    }
    write_json(run_paths.metadata_path, metadata)
    write_json(run_paths.parse_report_path, _initial_parse_report(pdf_details["page_count"]))
    return run_paths


def parse_run(run_paths: RunPaths) -> dict[str, Any]:
    warnings: list[str] = []
    markdown_text = ""
    fulltext_generated = False
    sections_generated = False
    extracted_image_count = 0
    extracted_table_count = 0
    table_caption_candidates_found = 0
    table_candidates_deduplicated = 0
    table_regions_cropped = 0
    tables_extracted_structured = 0
    tables_saved_as_fallback_only = 0
    tables_rejected_validation = 0
    table_summaries: list[dict[str, Any]] = []

    try:
        markdown_text = extract_markdown(run_paths.article_pdf, run_paths.fulltext_path)
        fulltext_generated = bool(markdown_text.strip())
    except Exception as exc:
        warnings.append(f"Markdown extraction failed: {exc}")

    try:
        figures, image_warnings = extract_images(run_paths.article_pdf, run_paths.figures_dir)
        extracted_image_count = len(figures)
        warnings.extend(image_warnings)
    except Exception as exc:
        warnings.append(f"Image extraction failed: {exc}")

    try:
        table_result = extract_tables(run_paths.article_pdf, run_paths.tables_dir)
        extracted_table_count = len(table_result["tables"])
        table_caption_candidates_found = table_result["table_caption_candidates_found"]
        table_candidates_deduplicated = table_result["table_candidates_deduplicated"]
        table_regions_cropped = table_result["table_regions_cropped"]
        tables_extracted_structured = table_result["tables_extracted_structured"]
        tables_saved_as_fallback_only = table_result["tables_saved_as_fallback_only"]
        tables_rejected_validation = table_result["tables_rejected_validation"]
        table_summaries = table_result.get("table_summaries", [])
        warnings.extend(table_result["warnings"])
    except Exception as exc:
        warnings.append(f"Table extraction failed: {exc}")

    try:
        sections = generate_sections(run_paths.article_pdf, run_paths.sections_path)
        sections_generated = bool(sections)
    except Exception as exc:
        warnings.append(f"Section generation failed: {exc}")

    metadata = read_json(run_paths.metadata_path)
    status = "completed" if not warnings else "completed_with_warnings"
    message = "PDF parsed successfully." if not warnings else "PDF parsed with warnings."
    report = {
        "status": status,
        "message": message,
        "page_count": metadata["page_count"],
        "table_caption_candidates_found": table_caption_candidates_found,
        "table_candidates_deduplicated": table_candidates_deduplicated,
        "table_regions_cropped": table_regions_cropped,
        "tables_extracted_structured": tables_extracted_structured,
        "tables_saved_as_fallback_only": tables_saved_as_fallback_only,
        "tables_rejected_validation": tables_rejected_validation,
        "extracted_image_count": extracted_image_count,
        "extracted_table_count": extracted_table_count,
        "fulltext_generated": fulltext_generated,
        "sections_generated": sections_generated,
        "table_summaries": table_summaries,
        "parser_versions": parser_versions(),
        "warnings": warnings,
    }
    write_json(run_paths.parse_report_path, report)
    return report


def run_pipeline(input_pdf: str | Path, base_dir: str | Path | None = None) -> tuple[RunPaths, dict[str, Any], dict[str, Any]]:
    run_paths = ingest_pdf(input_pdf, base_dir=base_dir)
    parse_report = parse_run(run_paths)
    metadata = read_json(run_paths.metadata_path)
    return run_paths, metadata, parse_report


def run_index_stage(
    run_dir: str | Path, config: RetrievalConfig | None = None
) -> tuple[RunPaths, dict[str, Any]]:
    run_paths = load_run_paths(Path(run_dir))
    report = index_run(run_paths, config=config)
    return run_paths, report


def summarize_run(
    run_paths: RunPaths, parse_report: dict[str, Any], index_report: dict[str, Any] | None = None
) -> dict[str, Any]:
    summary = {
        "run_dir": str(run_paths.run_dir),
        "input_pdf": str(run_paths.article_pdf),
        "metadata": str(run_paths.metadata_path),
        "fulltext": str(run_paths.fulltext_path),
        "sections": str(run_paths.sections_path),
        "parse_report": str(run_paths.parse_report_path),
        "figure_dirs": len(list(run_paths.figures_dir.glob("fig_*"))),
        "table_files": len(list(run_paths.tables_dir.glob("table_*.json"))),
        "status": parse_report["status"],
    }
    if index_report is not None:
        summary["indexes_dir"] = str(run_paths.indexes_dir)
        summary["bm25_dir"] = str(run_paths.bm25_dir)
        summary["faiss_dir"] = str(run_paths.faiss_dir)
        summary["graph"] = str(run_paths.graph_path)
        summary["index_report"] = str(run_paths.index_report_path)
        summary["evidence_items"] = index_report["evidence_item_count"]
    return summary
