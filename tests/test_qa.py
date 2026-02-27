import json
import shutil
import sys
from pathlib import Path
from uuid import uuid4

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import qa


SECTION_FILE_HEADERS = {
    "requirements.md": ["Problem Statement", "Goals", "Non-Goals", "Assumptions"],
    "architecture.md": ["Architecture Overview", "Components", "Trade-offs", "Diagram", "Assumptions"],
    "data_api.md": [
        "Data Design",
        "Entities",
        "Data Flows",
        "Storage/Retention",
        "API / Interface Contracts",
        "Assumptions",
    ],
    "security.md": ["Risks & Mitigations", "Security Controls", "Assumptions"],
    "nfrs_ops.md": ["Non-Functional Requirements", "Observability", "Ops Runbooks", "Assumptions"],
}


def _make_output_dir(name: str) -> tuple[Path, str]:
    rel = f"outputs/{name}-{uuid4().hex}"
    out_dir = ROOT / rel
    (out_dir / "sections").mkdir(parents=True, exist_ok=True)
    (out_dir / "inputs").mkdir(parents=True, exist_ok=True)
    return out_dir, rel


@pytest.fixture(autouse=True)
def _cleanup_test_outputs() -> None:
    created_dirs: list[Path] = []
    original_make_output_dir = _make_output_dir

    def _tracking_make_output_dir(name: str) -> tuple[Path, str]:
        out_dir, rel = original_make_output_dir(name)
        created_dirs.append(out_dir)
        return out_dir, rel

    globals()["_make_output_dir"] = _tracking_make_output_dir
    try:
        yield
    finally:
        globals()["_make_output_dir"] = original_make_output_dir
        for out_dir in created_dirs:
            shutil.rmtree(out_dir, ignore_errors=True)


def _write_valid_section_files(out_dir: Path) -> None:
    for filename, headers in SECTION_FILE_HEADERS.items():
        content = "\n\n".join(f"## {header}\nText." for header in headers) + "\n"
        (out_dir / "sections" / filename).write_text(content, encoding="utf-8")


def _write_design_doc(
    out_dir: Path,
    *,
    include_all_required: bool = True,
    include_prior_review_phrase: bool = True,
    prior_review_body_override: str | None = None,
) -> None:
    headings = qa.REQUIRED_SECTIONS if include_all_required else [h for h in qa.REQUIRED_SECTIONS if h != "Rollout Plan"]
    chunks = []
    for heading in headings:
        body = "Text."
        if heading == "Prior QA Report Review":
            if prior_review_body_override is not None:
                body = prior_review_body_override
            elif include_prior_review_phrase:
                body = "This section notes the prior QA report review."
            else:
                body = "First run or no prior findings to reconcile."
        chunks.append(f"## {heading}\n{body}")
    (out_dir / "design_doc.md").write_text("\n\n".join(chunks) + "\n", encoding="utf-8")


def _build_critique_report(*, criterion_score: int = 85) -> dict:
    section_by_key = {
        "input_alignment_fidelity": "Context & Constraints",
        "problem_scope_clarity": "Context & Constraints",
        "architecture_design_quality": "Architecture Overview",
        "component_interface_specificity": "API / Interface Contracts",
        "data_design_quality": "Data Design",
        "security_risk_coverage": "Risks & Mitigations",
        "nfrs_operability_quality": "Non-Functional Requirements",
        "delivery_readiness": "Rollout Plan",
        "testability_validation_strategy": "Test Strategy",
        "decision_traceability_and_assumptions": "Decision Log",
        "document_coherence_and_consistency": "Prior QA Report Review",
    }
    criteria = []
    for key, label, weight in qa.CRITIQUE_CRITERIA_SPEC:
        criteria.append(
            {
                "key": key,
                "label": label,
                "weight_pct": weight,
                "score": criterion_score,
                "primary_section": section_by_key[key],
                "strengths": ["Grounded content"],
                "gaps": ["Minor refinements possible"],
                "evidence": ["Observed required section content"],
                "recommended_actions": ["Add more implementation detail where useful."],
            }
        )
    overall = qa._weighted_quality_score(criteria)
    return {
        "reviewer_role": "IT Super Architect",
        "version": 1,
        "document_path": "outputs/x/design_doc.md",
        "scoring": {
            "scale_min": 0,
            "scale_max": 100,
            "threshold_strictly_greater_than": 80,
            "overall_quality_score": overall,
            "quality_gate_passed": overall > 80,
            "calculation": "weighted_average_rounded",
        },
        "criteria": criteria,
        "top_strengths": ["Sections are present"],
        "top_risks": ["Could improve specificity"],
        "summary": "Fixture critique report.",
    }


def _write_critique_report(out_dir: Path, *, criterion_score: int = 85) -> None:
    report = _build_critique_report(criterion_score=criterion_score)
    (out_dir / "critique_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def _run_qa_and_load(rel_output_dir: str) -> tuple[int, dict]:
    exit_code = qa.main(rel_output_dir)
    report = json.loads((ROOT / rel_output_dir / "review_report.json").read_text(encoding="utf-8"))
    return exit_code, report


def test_first_run_missing_prior_review_focuses_on_missing_sections() -> None:
    out_dir, rel = _make_output_dir("test-qa-first-run-missing-sections")
    _write_valid_section_files(out_dir)
    _write_design_doc(out_dir, include_all_required=False)
    _write_critique_report(out_dir)

    exit_code, report = _run_qa_and_load(rel)

    assert exit_code == 1
    assert report["status"] == "FAIL"
    assert any(
        issue["section"] == "Rollout Plan" and issue["issue"] == "Missing required section"
        for issue in report["issues"]
    )
    assert not any(
        issue["section"] == "Inputs" and "Previous QA report not found" in issue["issue"]
        for issue in report["issues"]
    )


def test_first_run_without_prior_review_can_pass_with_quality_over_80() -> None:
    out_dir, rel = _make_output_dir("test-qa-first-run-pass")
    _write_valid_section_files(out_dir)
    _write_design_doc(out_dir, include_all_required=True)
    _write_critique_report(out_dir, criterion_score=85)

    exit_code, report = _run_qa_and_load(rel)

    assert exit_code == 0
    assert report["status"] == "PASS"
    assert report["issues"] == []
    assert report["quality"] == {
        "source": "critique_report.json",
        "score": 85,
        "threshold_rule": ">80",
        "passed": True,
    }


def test_quality_score_equal_80_fails_strict_threshold() -> None:
    out_dir, rel = _make_output_dir("test-qa-quality-80-fails")
    _write_valid_section_files(out_dir)
    _write_design_doc(out_dir, include_all_required=True)
    _write_critique_report(out_dir, criterion_score=80)

    exit_code, report = _run_qa_and_load(rel)

    assert exit_code == 1
    assert report["status"] == "FAIL"
    assert report["quality"]["score"] == 80
    assert report["quality"]["passed"] is False
    assert any("does not meet threshold >80" in issue["issue"] for issue in report["issues"])
    assert any(issue["section"] == "Document" for issue in report["issues"])


def test_missing_critique_report_fails_closed() -> None:
    out_dir, rel = _make_output_dir("test-qa-missing-critique")
    _write_valid_section_files(out_dir)
    _write_design_doc(out_dir, include_all_required=True)

    exit_code, report = _run_qa_and_load(rel)

    assert exit_code == 1
    assert report["status"] == "FAIL"
    assert report["quality"]["source"] == "critique_report.json"
    assert report["quality"]["score"] is None
    assert any("Critique report is missing or invalid JSON" in issue["issue"] for issue in report["issues"])


def test_invalid_critique_report_json_fails_closed() -> None:
    out_dir, rel = _make_output_dir("test-qa-invalid-critique-json")
    _write_valid_section_files(out_dir)
    _write_design_doc(out_dir, include_all_required=True)
    (out_dir / "critique_report.json").write_text("{invalid json}", encoding="utf-8")

    exit_code, report = _run_qa_and_load(rel)

    assert exit_code == 1
    assert report["status"] == "FAIL"
    assert any("present but invalid JSON" in issue["issue"] for issue in report["issues"])


def test_existing_empty_prior_review_still_fails() -> None:
    out_dir, rel = _make_output_dir("test-qa-empty-prior")
    _write_valid_section_files(out_dir)
    _write_design_doc(out_dir, include_all_required=True)
    _write_critique_report(out_dir)
    (out_dir / "inputs" / "previous_review_report.json").write_text("", encoding="utf-8")

    exit_code, report = _run_qa_and_load(rel)

    assert exit_code == 1
    assert report["status"] == "FAIL"
    assert any(
        issue["section"] == "Inputs" and issue["issue"] == "Previous QA report is empty"
        for issue in report["issues"]
    )


def test_existing_prior_review_requires_review_mention() -> None:
    out_dir, rel = _make_output_dir("test-qa-prior-review-mention")
    _write_valid_section_files(out_dir)
    _write_design_doc(out_dir, include_all_required=True, include_prior_review_phrase=False)
    _write_critique_report(out_dir)
    (out_dir / "inputs" / "previous_review_report.json").write_text(
        json.dumps({"status": "FAIL", "issues": [{"section": "Rollout Plan"}]}, indent=2),
        encoding="utf-8",
    )

    exit_code, report = _run_qa_and_load(rel)

    assert exit_code == 1
    assert report["status"] == "FAIL"
    assert any(
        issue["section"] == "Document"
        and issue["issue"] == "No indication that previous QA report was reviewed"
        for issue in report["issues"]
    )


def test_existing_prior_review_accepts_previous_review_report_wording() -> None:
    out_dir, rel = _make_output_dir("test-qa-prior-review-alt-wording")
    _write_valid_section_files(out_dir)
    _write_design_doc(
        out_dir,
        include_all_required=True,
        prior_review_body_override="The previous review report was reviewed and triaged.",
    )
    _write_critique_report(out_dir)
    (out_dir / "inputs" / "previous_review_report.json").write_text(
        json.dumps({"status": "FAIL", "issues": [{"section": "Decision Log"}]}, indent=2),
        encoding="utf-8",
    )

    exit_code, report = _run_qa_and_load(rel)

    assert exit_code == 0
    assert report["status"] == "PASS"
    assert report["issues"] == []
    assert report["quality"]["passed"] is True


def test_existing_prior_review_accepts_json_path_mention() -> None:
    out_dir, rel = _make_output_dir("test-qa-prior-review-path-mention")
    _write_valid_section_files(out_dir)
    _write_design_doc(
        out_dir,
        include_all_required=True,
        prior_review_body_override="Reviewed inputs/previous_review_report.json and used it for prioritization.",
    )
    _write_critique_report(out_dir)
    (out_dir / "inputs" / "previous_review_report.json").write_text(
        json.dumps({"status": "FAIL", "issues": [{"section": "Test Strategy"}]}, indent=2),
        encoding="utf-8",
    )

    exit_code, report = _run_qa_and_load(rel)

    assert exit_code == 0
    assert report["status"] == "PASS"
    assert report["issues"] == []
    assert report["quality"]["passed"] is True
