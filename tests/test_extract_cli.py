from __future__ import annotations

from pathlib import Path

from mvp import extract as extract_cli


def test_extract_cli_runs_phase1_only(monkeypatch, capsys) -> None:
    calls: dict[str, object] = {}

    def fake_run_phase1(*, run_dir, model, output_dir, debug):
        calls["phase1"] = {
            "run_dir": run_dir,
            "model": model,
            "output_dir": output_dir,
            "debug": debug,
        }
        return {}, {}, {"phase1": {"paper_map_status": "completed", "interpretation_map_status": "completed"}}

    def fake_extract_run(**kwargs):
        raise AssertionError("extract_run should not be called in phase1-only mode")

    monkeypatch.setattr(extract_cli, "run_phase1", fake_run_phase1)
    monkeypatch.setattr(extract_cli, "extract_run", fake_extract_run)

    rc = extract_cli.main(["--run-dir", "runs/run_x", "--phase1-only", "--phase1-model", "gpt-5.4-mini"])

    assert rc == 0
    assert calls["phase1"]["model"] == "gpt-5.4-mini"
    output = capsys.readouterr().out
    assert "Phase 1 paper-map status: completed" in output
    assert "Interpretation map path:" in output


def test_extract_cli_uses_multistage_path_by_default(monkeypatch, capsys) -> None:
    calls: dict[str, object] = {}

    def fake_run_phase1(**kwargs):
        raise AssertionError("run_phase1 should not be called without --phase1-only")

    def fake_extract_run(*, run_dir, model, top_k, output_dir, debug, legacy_direct):
        calls["extract"] = {
            "run_dir": run_dir,
            "model": model,
            "top_k": top_k,
            "output_dir": output_dir,
            "debug": debug,
            "legacy_direct": legacy_direct,
        }
        return {"evidence_used": ["chunk:chunk_001"]}, {"extraction_status": "completed", "extraction_path": "retrieval_llm2_llm3", "canonical_design_record_path": "runs/run_y/outputs/canonical_design_record.json"}

    monkeypatch.setattr(extract_cli, "run_phase1", fake_run_phase1)
    monkeypatch.setattr(extract_cli, "extract_run", fake_extract_run)

    rc = extract_cli.main(["--run-dir", "runs/run_y", "--top-k", "7"])

    assert rc == 0
    assert calls["extract"]["top_k"] == 7
    assert calls["extract"]["legacy_direct"] is False
    assert calls["extract"]["run_dir"] == Path("runs/run_y")
    output = capsys.readouterr().out
    assert "Extraction path: retrieval_llm2_llm3" in output
    assert "Canonical design record path:" in output


def test_extract_cli_can_request_legacy_direct_path(monkeypatch) -> None:
    calls: dict[str, object] = {}

    def fake_extract_run(*, run_dir, model, top_k, output_dir, debug, legacy_direct):
        calls["extract"] = {
            "run_dir": run_dir,
            "model": model,
            "legacy_direct": legacy_direct,
        }
        return {"evidence_used": []}, {"extraction_status": "completed", "extraction_path": "legacy_direct_single_call"}

    monkeypatch.setattr(extract_cli, "extract_run", fake_extract_run)

    rc = extract_cli.main(["--run-dir", "runs/run_z", "--legacy-direct-extraction", "--model", "gpt-4o"])

    assert rc == 0
    assert calls["extract"]["legacy_direct"] is True
    assert calls["extract"]["model"] == "gpt-4o"
