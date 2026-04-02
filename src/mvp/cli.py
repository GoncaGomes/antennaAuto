from __future__ import annotations

import argparse
from pathlib import Path

from .index import index_run
from .pipeline import run_pipeline, summarize_run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local PDF ingestion and parsing pipeline.")
    parser.add_argument("--input", required=True, help="Path to the source PDF article.")
    parser.add_argument(
        "--index",
        action="store_true",
        help="Build BM25, FAISS, and graph indexes after parsing.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_paths, _, parse_report = run_pipeline(Path(args.input))
    index_report = index_run(run_paths) if args.index else None
    summary = summarize_run(run_paths, parse_report, index_report=index_report)

    print(f"Run path: {summary['run_dir']}")
    print("Generated files:")
    print(f"  - input PDF: {summary['input_pdf']}")
    print(f"  - metadata: {summary['metadata']}")
    print(f"  - fulltext: {summary['fulltext']}")
    print(f"  - sections: {summary['sections']}")
    print(f"  - parse report: {summary['parse_report']}")
    if index_report is not None:
        print(f"  - bm25 index: {summary['bm25_dir']}")
        print(f"  - faiss index: {summary['faiss_dir']}")
        print(f"  - graph: {summary['graph']}")
        print(f"  - index report: {summary['index_report']}")
    print(
        "Summary:"
        f" status={summary['status']},"
        f" figures={parse_report['extracted_image_count']},"
        f" tables={parse_report['extracted_table_count']}"
    )
    if index_report is not None:
        print(f"Index summary: evidence_items={summary['evidence_items']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
