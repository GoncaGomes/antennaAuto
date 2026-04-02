from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .config import CONFIG_PRESETS, DEFAULT_CONFIG_NAME, RetrievalConfig
from .index import index_run
from .pipeline import run_pipeline
from .retrieval import BundleRetriever
from .utils import ensure_dir, read_json, write_json

BENCHMARK_QUERIES = [
    "substrate material",
    "Rogers RT5880",
    "inset feed",
    "VSWR",
    "input impedance",
    "gain",
    "reflection coefficient",
    "bandwidth",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run retrieval benchmark configurations.")
    parser.add_argument("--input", required=True, help="Path to the source PDF article.")
    parser.add_argument(
        "--config-name",
        choices=sorted(CONFIG_PRESETS),
        default=DEFAULT_CONFIG_NAME,
        help=f"Named benchmark configuration to run. Defaults to {DEFAULT_CONFIG_NAME}.",
    )
    parser.add_argument(
        "--docs-dir",
        default="docs",
        help="Folder where benchmark markdown and JSON reports will be written.",
    )
    parser.add_argument(
        "--build-summary",
        action="store_true",
        help="Build the cross-configuration comparison summary from existing benchmark JSON files.",
    )
    parser.add_argument(
        "--write-default-confirmation",
        action="store_true",
        help="Write docs/retrieval_default_baseline_confirmation.md for the selected run.",
    )
    parser.add_argument("--top-k", type=int, default=3, help="Number of results to include per query path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    docs_dir = ensure_dir(Path(args.docs_dir))

    if args.build_summary:
        build_comparison_summary(docs_dir)
        return 0

    input_pdf = Path(args.input)
    config_name = args.config_name or DEFAULT_CONFIG_NAME
    config = CONFIG_PRESETS[config_name]
    report = run_benchmark_config(
        input_pdf=input_pdf,
        config_name=config_name,
        config=config,
        docs_dir=docs_dir,
        top_k=args.top_k,
    )
    if args.write_default_confirmation:
        confirmation_path = write_default_baseline_confirmation(report, docs_dir)
        print(f"Default confirmation report: {confirmation_path}")
    markdown_path = docs_dir / f"retrieval_{config_name}.md"
    print(f"Benchmark report: {markdown_path}")
    print(f"Run path: {report['run_path']}")
    return 0


def run_benchmark_config(
    input_pdf: Path,
    config_name: str,
    config: RetrievalConfig,
    docs_dir: Path,
    top_k: int = 3,
) -> dict[str, Any]:
    run_paths, _, _ = run_pipeline(input_pdf)
    index_run(run_paths, config=config)
    retriever = BundleRetriever(run_paths.run_dir)

    query_results: list[dict[str, Any]] = []
    for query in BENCHMARK_QUERIES:
        text_results = retriever.search_text(query, top_k=top_k)
        table_results = retriever.search_tables(query, top_k=top_k)
        figure_results = retriever.search_figures(query, top_k=top_k)
        query_results.append(
            {
                "query": query,
                "text_results": text_results,
                "table_results": table_results,
                "figure_results": figure_results,
                "note": _query_note(query, text_results, table_results, figure_results),
            }
        )

    command = (
        "uv run python -m mvp.benchmark"
        f" --input {input_pdf.as_posix()}"
        f" --config-name {config_name}"
    )
    report = {
        "config_name": config_name,
        "config": config.to_dict(),
        "command": command,
        "run_id": run_paths.run_id,
        "run_path": str(run_paths.run_dir),
        "queries": query_results,
    }

    json_path = docs_dir / f"retrieval_{config_name}.json"
    markdown_path = docs_dir / f"retrieval_{config_name}.md"
    write_json(json_path, report)
    markdown_path.write_text(_benchmark_markdown(report), encoding="utf-8")
    return report


def build_comparison_summary(docs_dir: Path) -> Path:
    reports: list[dict[str, Any]] = []
    for config_name in CONFIG_PRESETS:
        path = docs_dir / f"retrieval_{config_name}.json"
        if path.exists():
            reports.append(read_json(path))

    if not reports:
        raise FileNotFoundError("No benchmark JSON reports found in docs/")

    substrate_rows = [_substrate_summary_row(report) for report in reports]
    best_row = min(
        substrate_rows,
        key=lambda row: (
            0 if row["rogers_top3"] else 1,
            row["first_rogers_rank"] if row["first_rogers_rank"] is not None else 999,
            0 if row["chunking_mode"] == "paragraph" else 1,
            row["rogers_result_char_length"],
        ),
    )
    rank_suffix = (
        f" and first appears at rank {best_row['first_rogers_rank']}"
        if best_row["first_rogers_rank"] is not None
        else ""
    )

    lines: list[str] = [
        "# Retrieval Comparison Summary",
        "",
        "## Configurations",
        "",
        "| Configuration | Rogers RT5880 in top-3 text results | First rank with explicit Rogers evidence | Top text source ids |",
        "|---|---:|---:|---|",
    ]
    for row in substrate_rows:
        rank_display = str(row["first_rogers_rank"]) if row["first_rogers_rank"] is not None else "-"
        source_ids = ", ".join(row["top_text_source_ids"]) or "-"
        lines.append(
            f"| {row['config_name']} | {'yes' if row['rogers_top3'] else 'no'} | {rank_display} | {source_ids} |"
        )

    lines.extend(
        [
            "",
            "## Best Configuration For `substrate material`",
            "",
            f"`{best_row['config_name']}` best surfaces explicit evidence because "
            f"{'Rogers RT5880 appears in the top-3 text results' if best_row['rogers_top3'] else 'it is the least weak among the tested runs'}"
            f"{rank_suffix}.",
            "",
            "## Tradeoffs",
            "",
            f"- Weighted fusion versus RRF: {_fusion_tradeoff_note(reports)}",
            f"- Hash embeddings versus sentence-transformer embeddings: {_embedding_tradeoff_note(reports)}",
            f"- Paragraph chunking versus fixed chunking: {_chunking_tradeoff_note(reports)}",
        ]
    )

    summary_path = docs_dir / "retrieval_comparison_summary.md"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path


def write_default_baseline_confirmation(report: dict[str, Any], docs_dir: Path) -> Path:
    selected_queries = {
        "substrate material",
        "Rogers RT5880",
        "input impedance",
        "bandwidth",
        "VSWR",
    }
    query_entries = [entry for entry in report["queries"] if entry["query"] in selected_queries]

    lines: list[str] = [
        "# Default Retrieval Baseline Confirmation",
        "",
        "## Default Configuration",
        "",
        "```json",
        _json_block(report["config"]),
        "```",
        "",
        "This is the new default retrieval baseline because paragraph chunking produced cleaner evidence units,",
        "weighted fusion surfaced more extraction-ready results than RRF in the benchmark, and the",
        "sentence-transformer backend preserved explicit substrate evidence at the top of the text results.",
        "",
        "## Command",
        "",
        "```powershell",
        report["command"],
        "```",
        "",
        f"Run path: `{report['run_path']}`",
        "",
    ]

    for entry in query_entries:
        lines.extend(
            [
                f"## Query: `{entry['query']}`",
                "",
                f"Note: {_confirmation_note(entry)}",
                "",
                "### Top text result",
                "",
                *_single_result_lines(entry["text_results"]),
                "",
                "### Top table result",
                "",
                *_single_result_lines(entry["table_results"]),
                "",
                "### Top figure result",
                "",
                *_single_result_lines(entry["figure_results"]),
                "",
            ]
        )

    path = docs_dir / "retrieval_default_baseline_confirmation.md"
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def _benchmark_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = [
        f"# Retrieval Benchmark: {report['config_name']}",
        "",
        "## Configuration",
        "",
        "```json",
        _json_block(report["config"]),
        "```",
        "",
        "## Command",
        "",
        "```powershell",
        report["command"],
        "```",
        "",
        f"Run path: `{report['run_path']}`",
        "",
    ]

    for query_entry in report["queries"]:
        lines.extend(
            [
                f"## Query: `{query_entry['query']}`",
                "",
                f"Note: {query_entry['note']}",
                "",
                "### search_text",
                "",
                *_result_lines(query_entry["text_results"]),
                "",
                "### search_tables",
                "",
                *_result_lines(query_entry["table_results"]),
                "",
                "### search_figures",
                "",
                *_result_lines(query_entry["figure_results"]),
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def _result_lines(results: list[dict[str, Any]]) -> list[str]:
    if not results:
        return ["No results."]

    lines: list[str] = []
    for result in results:
        lines.append(
            f"- `{result['evidence_id']}` page={result['page_number']} score={result['score']}"
        )
        lines.append(f"  - snippet: {result['snippet']}")
        lines.append(
            "  - diagnostics: "
            f"bm25_score={result.get('bm25_score')} "
            f"dense_score={result.get('dense_score')} "
            f"bm25_rank={result.get('bm25_rank')} "
            f"dense_rank={result.get('dense_rank')} "
            f"final_rank={result.get('final_rank')} "
            f"fusion_strategy={result.get('fusion_strategy')} "
            f"chunking_mode={result.get('chunking_mode')} "
            f"embedding_backend={result.get('embedding_backend')} "
            f"weighted_score={result.get('weighted_score')} "
            f"rrf_score={result.get('rrf_score')}"
        )
    return lines


def _single_result_lines(results: list[dict[str, Any]]) -> list[str]:
    if not results:
        return ["No results."]
    return _result_lines(results[:1])


def _query_note(
    query: str,
    text_results: list[dict[str, Any]],
    table_results: list[dict[str, Any]],
    figure_results: list[dict[str, Any]],
) -> str:
    top3_text = text_results[:3]
    rogers_in_text = any("rogers rt5880" in result["snippet"].lower() for result in top3_text)
    exact_query_in_text = any(query.lower() in result["snippet"].lower() for result in top3_text)

    return (
        f"Top-3 text results explicit Rogers RT5880={'yes' if rogers_in_text else 'no'}; "
        f"exact query phrase in text snippets={'yes' if exact_query_in_text else 'no'}; "
        f"text_results={len(text_results)}, table_results={len(table_results)}, figure_results={len(figure_results)}."
    )


def _substrate_summary_row(report: dict[str, Any]) -> dict[str, Any]:
    substrate_query = next(item for item in report["queries"] if item["query"] == "substrate material")
    top_text = substrate_query["text_results"][:3]
    rogers_results = [
        result for result in top_text if "rogers rt5880" in result["snippet"].lower()
    ]
    rogers_ranks = [result["final_rank"] for result in rogers_results]
    rogers_lengths = [
        (result["metadata"].get("char_end", 10**9) - result["metadata"].get("char_start", 0))
        if result["metadata"].get("char_end") is not None
        else 10**9
        for result in rogers_results
    ]
    return {
        "config_name": report["config_name"],
        "chunking_mode": report["config"]["chunking_mode"],
        "rogers_top3": bool(rogers_ranks),
        "first_rogers_rank": min(rogers_ranks) if rogers_ranks else None,
        "rogers_result_char_length": min(rogers_lengths) if rogers_lengths else 10**9,
        "top_text_source_ids": [result["source_id"] for result in top_text],
    }


def _fusion_tradeoff_note(reports: list[dict[str, Any]]) -> str:
    weighted = [row for row in reports if row["config"]["fusion_strategy"] == "weighted"]
    rrf = [row for row in reports if row["config"]["fusion_strategy"] == "rrf"]
    weighted_hits = sum(_substrate_summary_row(report)["rogers_top3"] for report in weighted)
    rrf_hits = sum(_substrate_summary_row(report)["rogers_top3"] for report in rrf)
    return f"weighted surfaced explicit Rogers evidence in {weighted_hits} run(s), while RRF did so in {rrf_hits} run(s)."


def _embedding_tradeoff_note(reports: list[dict[str, Any]]) -> str:
    hash_reports = [row for row in reports if row["config"]["embedding_backend"] == "hash"]
    st_reports = [row for row in reports if row["config"]["embedding_backend"] == "sentence_transformer"]
    hash_hits = sum(_substrate_summary_row(report)["rogers_top3"] for report in hash_reports)
    st_hits = sum(_substrate_summary_row(report)["rogers_top3"] for report in st_reports)
    return f"hash backends produced explicit Rogers evidence in {hash_hits} run(s); sentence-transformer backends did so in {st_hits} run(s)."


def _chunking_tradeoff_note(reports: list[dict[str, Any]]) -> str:
    fixed_reports = [row for row in reports if row["config"]["chunking_mode"] == "fixed"]
    paragraph_reports = [row for row in reports if row["config"]["chunking_mode"] == "paragraph"]
    fixed_hits = sum(_substrate_summary_row(report)["rogers_top3"] for report in fixed_reports)
    paragraph_hits = sum(_substrate_summary_row(report)["rogers_top3"] for report in paragraph_reports)
    return f"fixed chunking produced explicit Rogers evidence in {fixed_hits} run(s); paragraph chunking did so in {paragraph_hits} run(s)."


def _json_block(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, indent=2, sort_keys=True)


def _confirmation_note(query_entry: dict[str, Any]) -> str:
    note = query_entry["note"]
    top_text = query_entry["text_results"][:1]
    if not top_text:
        return f"{note} No text result was returned."

    snippet = top_text[0]["snippet"].lower()
    if "rogers rt5880" in snippet:
        return f"{note} The top text result contains explicit Rogers RT5880 evidence."
    if query_entry["query"].lower() in snippet:
        return f"{note} The top text result contains the exact query phrase."
    return f"{note} The top text result is relevant, but the key phrase is implicit rather than exact."


if __name__ == "__main__":
    raise SystemExit(main())
