from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .utils import ensure_dir, ensure_reports_dir, make_run_id


@dataclass(frozen=True)
class RunPaths:
    run_id: str
    run_dir: Path
    input_dir: Path
    bundle_dir: Path
    indexes_dir: Path
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
    tables_dir = ensure_dir(bundle_dir / "tables")
    figures_dir = ensure_dir(bundle_dir / "figures")
    bm25_dir = ensure_dir(indexes_dir / "bm25")
    faiss_dir = ensure_dir(indexes_dir / "faiss")

    article_pdf = input_dir / "article.pdf"
    shutil.copy2(source_pdf, article_pdf)

    return RunPaths(
        run_id=run_dir.name,
        run_dir=run_dir,
        input_dir=input_dir,
        bundle_dir=bundle_dir,
        indexes_dir=indexes_dir,
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
    )


def load_run_paths(run_dir: Path) -> RunPaths:
    resolved = run_dir.expanduser().resolve()
    bundle_dir = resolved / "bundle"
    indexes_dir = resolved / "indexes"
    return RunPaths(
        run_id=resolved.name,
        run_dir=resolved,
        input_dir=resolved / "input",
        bundle_dir=bundle_dir,
        indexes_dir=indexes_dir,
        tables_dir=bundle_dir / "tables",
        figures_dir=bundle_dir / "figures",
        bm25_dir=indexes_dir / "bm25",
        faiss_dir=indexes_dir / "faiss",
        article_pdf=resolved / "input" / "article.pdf",
        metadata_path=bundle_dir / "metadata.json",
        fulltext_path=bundle_dir / "fulltext.md",
        sections_path=bundle_dir / "sections.json",
        parse_report_path=bundle_dir / "parse_report.json",
        graph_path=indexes_dir / "graph.json",
        index_report_path=indexes_dir / "index_report.json",
    )
