from __future__ import annotations

from pathlib import Path

from mvp.config import RetrievalConfig
from mvp.index import index_run
from mvp.interpretation.pipeline import run_phase1
from mvp.pipeline import run_pipeline
from mvp.utils import project_root

VALIDATION_PDFS = [
    Path("data/raw/paper_001/article.pdf"),
    Path("data/raw/paper_002/engproc-46-00010.pdf"),
    Path("data/raw/paper_003/IJETT-V4I4P340.pdf"),
]


def main() -> int:
    root = project_root()
    for relative_pdf in VALIDATION_PDFS:
        source_pdf = root / relative_pdf
        run_paths, _, _ = run_pipeline(source_pdf, base_dir=root)
        index_run(run_paths, config=RetrievalConfig())
        _, _, report = run_phase1(run_paths.run_dir, model="gpt-5.4-mini")
        print(f"{source_pdf.name}: {run_paths.run_id}")
        print(f"  paper_map: {run_paths.outputs_dir / 'paper_map.json'}")
        print(f"  interpretation_map: {run_paths.outputs_dir / 'interpretation_map.json'}")
        print(f"  report: {run_paths.outputs_dir / 'extraction_run_report.json'}")
        print(f"  phase1 status: {report['phase1']['paper_map_status']} / {report['phase1']['interpretation_map_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
