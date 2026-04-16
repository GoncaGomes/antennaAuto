from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from .utils import ensure_dir, ensure_reports_dir, make_run_id, write_json


@dataclass(frozen=True)
class RunPaths:
    run_id: str
    run_dir: Path
    input_dir: Path
    bundle_dir: Path
    indexes_dir: Path
    outputs_dir: Path
    tables_dir: Path
    figures_dir: Path
    bm25_dir: Path
    faiss_dir: Path
    article_pdf: Path
    metadata_path: Path
    fulltext_path: Path
    sections_path: Path
    parse_report_path: Path
    graph_path: Path
    index_report_path: Path
    index_config_path: Path
    extraction_spec_path: Path
    extraction_report_path: Path


def validate_pdf_input(pdf_path: Path) -> Path:
    resolved = pdf_path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"PDF not found: {resolved}")
    if resolved.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a .pdf file: {resolved}")
    return resolved


def prepare_run_bundle(source_pdf: Path, base_dir: Path) -> RunPaths:
    source_pdf = validate_pdf_input(source_pdf)
    runs_root = ensure_dir(base_dir / "runs")
    ensure_reports_dir(base_dir)

    run_dir = runs_root / make_run_id()
    while run_dir.exists():
        run_dir = runs_root / make_run_id()

    input_dir = ensure_dir(run_dir / "input")
    bundle_dir = ensure_dir(run_dir / "bundle")
    indexes_dir = ensure_dir(run_dir / "indexes")
    outputs_dir = ensure_dir(run_dir / "outputs")
    tables_dir = ensure_dir(bundle_dir / "tables")
    figures_dir = ensure_dir(bundle_dir / "figures")
    bm25_dir = ensure_dir(indexes_dir / "bm25")
    faiss_dir = ensure_dir(indexes_dir / "faiss")

    article_pdf = input_dir / source_pdf.name
    shutil.copy2(source_pdf, article_pdf)

    return RunPaths(
        run_id=run_dir.name,
        run_dir=run_dir,
        input_dir=input_dir,
        bundle_dir=bundle_dir,
        indexes_dir=indexes_dir,
        outputs_dir=outputs_dir,
        tables_dir=tables_dir,
        figures_dir=figures_dir,
        bm25_dir=bm25_dir,
        faiss_dir=faiss_dir,
        article_pdf=article_pdf,
        metadata_path=bundle_dir / "metadata.json",
        fulltext_path=bundle_dir / "fulltext.md",
        sections_path=bundle_dir / "sections.json",
        parse_report_path=bundle_dir / "parse_report.json",
        graph_path=indexes_dir / "graph.json",
        index_report_path=indexes_dir / "index_report.json",
        index_config_path=indexes_dir / "index_config.json",
        extraction_spec_path=outputs_dir / "antenna_architecture_spec_mvp_v2.json",
        extraction_report_path=outputs_dir / "extraction_run_report.json",
    )


def load_run_paths(run_dir: Path) -> RunPaths:
    resolved = run_dir.expanduser().resolve()
    bundle_dir = resolved / "bundle"
    indexes_dir = resolved / "indexes"
    outputs_dir = resolved / "outputs"
    article_pdf = _resolve_article_pdf_path(resolved, bundle_dir)
    return RunPaths(
        run_id=resolved.name,
        run_dir=resolved,
        input_dir=resolved / "input",
        bundle_dir=bundle_dir,
        indexes_dir=indexes_dir,
        outputs_dir=outputs_dir,
        tables_dir=bundle_dir / "tables",
        figures_dir=bundle_dir / "figures",
        bm25_dir=indexes_dir / "bm25",
        faiss_dir=indexes_dir / "faiss",
        article_pdf=article_pdf,
        metadata_path=bundle_dir / "metadata.json",
        fulltext_path=bundle_dir / "fulltext.md",
        sections_path=bundle_dir / "sections.json",
        parse_report_path=bundle_dir / "parse_report.json",
        graph_path=indexes_dir / "graph.json",
        index_report_path=indexes_dir / "index_report.json",
        index_config_path=indexes_dir / "index_config.json",
        extraction_spec_path=outputs_dir / "antenna_architecture_spec_mvp_v2.json",
        extraction_report_path=outputs_dir / "extraction_run_report.json",
    )


def save_structured_output(
    run_dir: str | Path,
    spec_json: dict,
    report_json: dict,
    output_dir: str | Path | None = None,
) -> RunPaths:
    run_paths = load_run_paths(Path(run_dir))
    target_dir = ensure_dir(Path(output_dir)) if output_dir else ensure_dir(run_paths.outputs_dir)
    spec_path = target_dir / "antenna_architecture_spec_mvp_v2.json"
    report_path = target_dir / "extraction_run_report.json"
    write_json(spec_path, spec_json)
    write_json(report_path, report_json)
    return run_paths


def _resolve_article_pdf_path(run_dir: Path, bundle_dir: Path) -> Path:
    input_dir = run_dir / "input"
    metadata_path = bundle_dir / "metadata.json"
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            metadata = {}
        original_filename = str(metadata.get("original_filename", "")).strip()
        if original_filename:
            candidate = input_dir / original_filename
            if candidate.exists():
                return candidate

    legacy_path = input_dir / "article.pdf"
    if legacy_path.exists():
        return legacy_path

    pdf_files = sorted(input_dir.glob("*.pdf"))
    if len(pdf_files) == 1:
        return pdf_files[0]
    if not pdf_files:
        return legacy_path
    raise FileNotFoundError(f"Expected exactly one PDF under {input_dir}, found {len(pdf_files)}")
