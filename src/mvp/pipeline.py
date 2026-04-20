from __future__ import annotations

from pathlib import Path
from typing import Any

from .bundle import RunPaths, load_run_paths, prepare_run_bundle
from .config import RetrievalConfig
from .index import index_run
from .parsers import extract_pdf_to_bundle, get_pdf_details, parser_versions
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
        "captionless_figure_count": 0,
        "figure_kind_counts": {},
        "table_with_caption_count": 0,
        "table_without_caption_count": 0,
        "page_object_count": 0,
        "object_counts_by_type": {},
        "tables_using_structured_export_count": 0,
        "figures_with_explicit_caption_count": 0,
        "figures_with_group_caption_count": 0,
        "figures_with_missing_caption_count": 0,
        "grobid_status": "disabled",
        "table_summaries": [],
        "figure_summaries": [],
        "page_summaries": [],
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
    captionless_figure_count = 0
    figure_kind_counts: dict[str, int] = {}
    table_with_caption_count = 0
    table_without_caption_count = 0
    page_object_count = 0
    object_counts_by_type: dict[str, int] = {}
    tables_using_structured_export_count = 0
    figures_with_explicit_caption_count = 0
    figures_with_group_caption_count = 0
    figures_with_missing_caption_count = 0
    grobid_status = "disabled"
    table_summaries: list[dict[str, Any]] = []
    figure_summaries: list[dict[str, Any]] = []
    page_summaries: list[dict[str, Any]] = []

    try:
        extraction = extract_pdf_to_bundle(run_paths.article_pdf, run_paths.bundle_dir)
        fulltext_generated = bool(extraction["fulltext_generated"])
        sections_generated = bool(extraction["sections_generated"])
        extracted_image_count = int(extraction["extracted_image_count"])
        extracted_table_count = int(extraction["extracted_table_count"])
        table_caption_candidates_found = extracted_table_count
        table_candidates_deduplicated = extracted_table_count
        table_regions_cropped = 0
        tables_extracted_structured = extracted_table_count
        tables_saved_as_fallback_only = 0
        tables_rejected_validation = 0
        captionless_figure_count = int(extraction.get("captionless_figure_count", 0))
        figure_kind_counts = dict(extraction.get("figure_kind_counts", {}))
        table_with_caption_count = int(extraction.get("table_with_caption_count", 0))
        table_without_caption_count = int(extraction.get("table_without_caption_count", 0))
        page_object_count = int(extraction.get("page_object_count", 0))
        object_counts_by_type = dict(extraction.get("object_counts_by_type", {}))
        tables_using_structured_export_count = int(extraction.get("tables_using_structured_export_count", 0))
        figures_with_explicit_caption_count = int(extraction.get("figures_with_explicit_caption_count", 0))
        figures_with_group_caption_count = int(extraction.get("figures_with_group_caption_count", 0))
        figures_with_missing_caption_count = int(extraction.get("figures_with_missing_caption_count", 0))
        grobid_status = str(extraction.get("grobid_status", "disabled"))
        table_summaries = list(extraction.get("table_summaries", []))
        figure_summaries = list(extraction.get("figure_summaries", []))
        page_summaries = list(extraction.get("page_summaries", []))
        warnings.extend(extraction.get("warnings", []))
    except Exception as exc:
        warnings.append(f"Markdown bundle extraction failed: {exc}")

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
        "captionless_figure_count": captionless_figure_count,
        "figure_kind_counts": figure_kind_counts,
        "table_with_caption_count": table_with_caption_count,
        "table_without_caption_count": table_without_caption_count,
        "page_object_count": page_object_count,
        "object_counts_by_type": object_counts_by_type,
        "tables_using_structured_export_count": tables_using_structured_export_count,
        "figures_with_explicit_caption_count": figures_with_explicit_caption_count,
        "figures_with_group_caption_count": figures_with_group_caption_count,
        "figures_with_missing_caption_count": figures_with_missing_caption_count,
        "grobid_status": grobid_status,
        "table_summaries": table_summaries,
        "figure_summaries": figure_summaries,
        "page_summaries": page_summaries,
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
        "figure_dirs": len(list(run_paths.figures_dir.glob("*.png"))),
        "table_files": len(list(run_paths.tables_dir.glob("table_*.md"))),
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
