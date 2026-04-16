from __future__ import annotations

import argparse
from pathlib import Path

from .extraction.pipeline import extract_run
from .interpretation.pipeline import DEFAULT_PHASE1_MODEL, run_phase1


LEGACY_DIRECT_MODEL_DEFAULT = "gpt-4o"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the antenna architecture extraction agent on a prepared run.")
    parser.add_argument("--run-dir", required=True, help="Path to an existing prepared run directory.")
    parser.add_argument(
        "--model",
        default=None,
        help="Legacy direct extraction model name. Only used with --legacy-direct-extraction.",
    )
    parser.add_argument(
        "--legacy-direct-extraction",
        action="store_true",
        help="Run the isolated legacy single-call extraction path instead of the default retrieval -> LLM2 -> LLM3 path.",
    )
    parser.add_argument(
        "--phase1-only",
        action="store_true",
        help="Run only Phase 1 paper understanding (paper_map + interpretation_map).",
    )
    parser.add_argument(
        "--phase1-model",
        default=DEFAULT_PHASE1_MODEL,
        help="OpenAI model name to use for the Phase 1 interpretation plan.",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Retrieval depth per query.")
    parser.add_argument("--output-dir", help="Optional output directory. Defaults to runs/<run_id>/outputs.")
    parser.add_argument("--debug", action="store_true", help="Persist debug prompt/response artifacts.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_root = Path(args.output_dir) if args.output_dir else Path(args.run_dir) / "outputs"

    if args.phase1_only:
        _, _, report = run_phase1(
            run_dir=Path(args.run_dir),
            model=args.phase1_model,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            debug=args.debug,
        )
        phase1 = report["phase1"]
        print(f"Phase 1 paper-map status: {phase1['paper_map_status']}")
        print(f"Phase 1 interpretation status: {phase1['interpretation_map_status']}")
        print(f"Paper map path: {output_root / 'paper_map.json'}")
        print(f"Interpretation map path: {output_root / 'interpretation_map.json'}")
        print(f"Report path: {output_root / 'extraction_run_report.json'}")
        return 0

    spec, report = extract_run(
        run_dir=Path(args.run_dir),
        model=args.model or LEGACY_DIRECT_MODEL_DEFAULT,
        top_k=args.top_k,
        output_dir=Path(args.output_dir) if args.output_dir else None,
        debug=args.debug,
        legacy_direct=args.legacy_direct_extraction,
    )
    print(f"Extraction status: {report['extraction_status']}")
    print(f"Extraction path: {report['extraction_path']}")
    print(f"Spec path: {output_root / 'antenna_architecture_spec_mvp_v2.json'}")
    print(f"Report path: {output_root / 'extraction_run_report.json'}")
    if report.get("canonical_design_record_path"):
        print(f"Canonical design record path: {report['canonical_design_record_path']}")
    print(f"Evidence used: {len(spec['evidence_used'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
