import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import analyze_outputs as ao
import qa


def _write_doc(run_dir: Path, headings: list[str]) -> str:
    chunks = [f"## {h}\nText for {h}." for h in headings]
    text = "\n\n".join(chunks) + "\n"
    (run_dir / "design_doc.md").write_text(text, encoding="utf-8")
    return text


def _write_section_artifacts(run_dir: Path, *, valid: bool = True) -> None:
    sections_dir = run_dir / "sections"
    sections_dir.mkdir(parents=True, exist_ok=True)
    for filename, headers in ao.SECTION_FILE_HEADERS.items():
        if valid:
            body = "\n\n".join(f"## {h}\nText." for h in headers) + "\n"
        else:
            body = "## Incomplete\nText.\n"
        (sections_dir / filename).write_text(body, encoding="utf-8")


def _write_manifest(run_dir: Path, timestamp: str) -> None:
    output_dir = str(run_dir.relative_to(run_dir.parents[2]))
    manifest = {
        "timestamp": timestamp,
        "run_dir": output_dir,
        "output_dir": output_dir,
        "model": "test/model",
        "base_url": "http://localhost",
        "inputs": [],
        "previous_design_doc": None,
        "previous_review_report": None,
        "qa_status": None,
        "qa_issues": None,
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _write_review(run_dir: Path, status: str, sections: list[str]) -> None:
    issues = [{"section": s, "issue": "x", "fix": "y"} for s in sections]
    (run_dir / "review_report.json").write_text(json.dumps({"status": status, "issues": issues}, indent=2), encoding="utf-8")


def _make_run(outputs_dir: Path, run_name: str, timestamp: str) -> Path:
    run_dir = outputs_dir / "2026-02-25" / run_name
    (run_dir / "inputs").mkdir(parents=True, exist_ok=True)
    (run_dir / "sections").mkdir(parents=True, exist_ok=True)
    _write_manifest(run_dir, timestamp)
    return run_dir


def test_discover_runs_computes_completion_and_artifact_metrics(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs"
    run_dir = _make_run(outputs_dir, "run_20260225T100000Z_a", "20260225T100000Z")

    headings = [h for h in qa.REQUIRED_SECTIONS if h not in {"Rollout Plan", "Decision Log"}]
    _write_doc(run_dir, headings)
    _write_section_artifacts(run_dir, valid=True)
    _write_review(run_dir, "FAIL", ["Rollout Plan", "Decision Log"])

    result = ao.evaluate_outputs(outputs_dir)

    assert result["run_count"] == 1
    run = result["run_metrics"][0]
    assert run["required_sections_total"] == len(qa.REQUIRED_SECTIONS)
    assert run["required_sections_completed"] == len(qa.REQUIRED_SECTIONS) - 2
    assert run["required_sections_completion_pct"] == round((len(qa.REQUIRED_SECTIONS) - 2) / len(qa.REQUIRED_SECTIONS) * 100, 1)
    assert run["section_artifacts_total"] == 5
    assert run["section_artifacts_present"] == 5
    assert run["section_artifacts_valid"] == 5
    assert run["section_artifacts_completion_pct"] == 100.0
    assert run["convergence_label"] == "baseline"


def test_reconstructs_lineage_via_previous_design_doc_hash_and_detects_oscillation(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs"

    r1 = _make_run(outputs_dir, "run_20260225T180008Z_a", "20260225T180008Z")
    r2 = _make_run(outputs_dir, "run_20260225T181751Z_b", "20260225T181751Z")
    r3 = _make_run(outputs_dir, "run_20260225T192515Z_c", "20260225T192515Z")

    h1 = [h for h in qa.REQUIRED_SECTIONS if h not in {"Context & Constraints", "Rollout Plan", "Test Strategy", "Decision Log"}]
    h2 = [h for h in qa.REQUIRED_SECTIONS if h not in {"Context & Constraints", "API / Interface Contracts", "Rollout Plan", "Test Strategy", "Decision Log"}]
    h3 = [h for h in qa.REQUIRED_SECTIONS if h not in {"Context & Constraints", "Rollout Plan", "Test Strategy", "Decision Log"}]

    doc1 = _write_doc(r1, h1)
    doc2 = _write_doc(r2, h2)
    _write_doc(r3, h3)

    for run in (r1, r2, r3):
        _write_section_artifacts(run, valid=True)

    _write_review(r1, "FAIL", ["Context & Constraints", "Rollout Plan", "Test Strategy", "Decision Log"])
    _write_review(
        r2,
        "FAIL",
        ["Context & Constraints", "API / Interface Contracts", "Rollout Plan", "Test Strategy", "Decision Log", "Document"],
    )
    _write_review(r3, "FAIL", ["Context & Constraints", "Rollout Plan", "Test Strategy", "Decision Log", "Document"])

    (r2 / "inputs" / "previous_design_doc.md").write_text(doc1, encoding="utf-8")
    (r3 / "inputs" / "previous_design_doc.md").write_text(doc2, encoding="utf-8")

    result = ao.evaluate_outputs(outputs_dir)

    assert result["run_count"] == 3
    metrics = {m["run_id"]: m for m in result["run_metrics"]}

    assert metrics[r1.name]["parent_run_id"] is None
    assert metrics[r2.name]["parent_run_id"] == r1.name
    assert metrics[r3.name]["parent_run_id"] == r2.name

    assert metrics[r2.name]["qa_issue_delta_vs_parent"] == -2  # 4 -> 6 regression
    assert metrics[r3.name]["qa_issue_delta_vs_parent"] == 1   # 6 -> 5 improvement

    seq = result["sequence_summaries"][0]
    assert seq["length"] == 3
    assert seq["oscillation_detected"] is True
    assert seq["final_qa_issue_count"] == 5
    assert seq["best_qa_issue_count"] == 4
    assert seq["converged"] is False


def test_sequence_converges_when_final_run_passes(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs"
    r1 = _make_run(outputs_dir, "run_20260225T100000Z_a", "20260225T100000Z")
    r2 = _make_run(outputs_dir, "run_20260225T101000Z_b", "20260225T101000Z")

    doc1 = _write_doc(r1, [h for h in qa.REQUIRED_SECTIONS if h != "Rollout Plan"])
    _write_doc(r2, qa.REQUIRED_SECTIONS)
    _write_section_artifacts(r1, valid=True)
    _write_section_artifacts(r2, valid=True)
    _write_review(r1, "FAIL", ["Rollout Plan"])
    _write_review(r2, "PASS", [])
    (r2 / "inputs" / "previous_design_doc.md").write_text(doc1, encoding="utf-8")

    result = ao.evaluate_outputs(outputs_dir)
    seq = result["sequence_summaries"][0]
    assert seq["converged"] is True
    assert seq["convergence_reason"] == "Final run passed QA"


def test_sequence_converges_on_stable_plateau(tmp_path: Path) -> None:
    outputs_dir = tmp_path / "outputs"
    r1 = _make_run(outputs_dir, "run_20260225T100000Z_a", "20260225T100000Z")
    r2 = _make_run(outputs_dir, "run_20260225T101000Z_b", "20260225T101000Z")

    doc1 = _write_doc(r1, [h for h in qa.REQUIRED_SECTIONS if h != "Rollout Plan"])
    _write_doc(r2, [h for h in qa.REQUIRED_SECTIONS if h != "Rollout Plan"])
    _write_section_artifacts(r1, valid=True)
    _write_section_artifacts(r2, valid=True)
    _write_review(r1, "FAIL", ["Rollout Plan"])
    _write_review(r2, "FAIL", ["Rollout Plan"])
    (r2 / "inputs" / "previous_design_doc.md").write_text(doc1, encoding="utf-8")

    result = ao.evaluate_outputs(outputs_dir, plateau_window=2)
    seq = result["sequence_summaries"][0]
    assert seq["converged"] is True
    assert seq["convergence_reason"] == "Stable plateau across recent runs"
