import json
from pathlib import Path
from typing import Any, List

REQUIRED_SECTIONS = [
    "Problem Statement",
    "Goals",
    "Non-Goals",
    "Context & Constraints",
    "Architecture Overview",
    "Data Design",
    "API / Interface Contracts",
    "Non-Functional Requirements",
    "Risks & Mitigations",
    "Rollout Plan",
    "Test Strategy",
    "Decision Log",
    "Prior QA Report Review",
    "Assumptions",
]

PLACEHOLDER_TOKENS = ["TODO", "TBD", "Lorem", "FILL ME", "???"]
CRITIQUE_REPORT_FILENAME = "critique_report.json"
QUALITY_THRESHOLD_STRICT_GT = 80
QUALITY_THRESHOLD_RULE = ">80"
EXPECTED_CRITIQUE_VERSION = 1
EXPECTED_REVIEWER_ROLE = "IT Super Architect"
EXPECTED_CRITIQUE_CALC = "weighted_average_rounded"

CRITIQUE_CRITERIA_SPEC = [
    ("input_alignment_fidelity", "Input Alignment Fidelity", 20),
    ("problem_scope_clarity", "Problem Scope Clarity", 8),
    ("architecture_design_quality", "Architecture Design Quality", 12),
    ("component_interface_specificity", "Component Interface Specificity", 10),
    ("data_design_quality", "Data Design Quality", 8),
    ("security_risk_coverage", "Security Risk Coverage", 8),
    ("nfrs_operability_quality", "NFRs and Operability Quality", 8),
    ("delivery_readiness", "Delivery Readiness", 8),
    ("testability_validation_strategy", "Testability and Validation Strategy", 8),
    ("decision_traceability_and_assumptions", "Decision Traceability and Assumptions", 5),
    ("document_coherence_and_consistency", "Document Coherence and Consistency", 5),
]

CRITIQUE_CRITERIA_BY_KEY = {key: {"label": label, "weight_pct": weight} for key, label, weight in CRITIQUE_CRITERIA_SPEC}


def load_doc(path: Path) -> str:
    # Read the generated document if present; empty string otherwise.
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def find_missing_sections(doc: str) -> List[str]:
    # Detect missing high-level sections in the final document.
    missing = []
    for section in REQUIRED_SECTIONS:
        if f"## {section}" not in doc:
            missing.append(section)
    return missing


def find_placeholders(doc: str) -> List[str]:
    # Guard against placeholders slipping into final output.
    hits = []
    for token in PLACEHOLDER_TOKENS:
        if token in doc:
            hits.append(token)
    return hits


def extract_section_body(doc: str, section: str) -> str:
    # Return the content under a top-level heading, excluding the heading line.
    marker = f"## {section}"
    start = doc.find(marker)
    if start == -1:
        return ""
    body_start = start + len(marker)
    remainder = doc[body_start:]
    next_section = remainder.find("\n## ")
    if next_section == -1:
        return remainder.strip()
    return remainder[:next_section].strip()


def mentions_prior_qa_review(prior_review_section: str) -> bool:
    # Accept semantically equivalent wording for prior QA review acknowledgment.
    text = prior_review_section.lower()
    if "previous_review_report.json" in text:
        return True
    has_prior_ref = "prior" in text or "previous" in text
    has_report_ref = "qa report" in text or "review report" in text
    return has_prior_ref and has_report_ref


def validate_section_file(path: Path, required_headers: List[str], issues: List[dict]) -> None:
    # Verify each section artifact exists and contains the expected headings.
    if not path.exists():
        issues.append(
            {
                "section": str(path),
                "issue": "Missing section output file",
                "fix": f"Ensure {path.name} is generated",
            }
        )
        return
    content = path.read_text(encoding="utf-8")
    for header in required_headers:
        if f"## {header}" not in content:
            issues.append(
                {
                    "section": path.name,
                    "issue": f"Missing heading: {header}",
                    "fix": f"Add '## {header}' to {path.name}",
                }
            )


def _weighted_quality_score(criteria: list[dict[str, Any]]) -> int:
    total = 0
    weight_total = 0
    for item in criteria:
        score = item.get("score")
        weight = item.get("weight_pct")
        if isinstance(score, int) and isinstance(weight, int):
            total += score * weight
            weight_total += weight
    if weight_total <= 0:
        return 0
    return round(total / weight_total)


def _critique_schema_issues(output_base: Path, critique: Any) -> list[dict[str, str]]:
    path_label = str(output_base / CRITIQUE_REPORT_FILENAME)
    issues: list[dict[str, str]] = []
    if not isinstance(critique, dict):
        return [
            {
                "section": "Document",
                "issue": "Critique report is missing or invalid JSON",
                "fix": f"Generate a valid {CRITIQUE_REPORT_FILENAME} with strict JSON schema",
            }
        ]

    if critique.get("reviewer_role") != EXPECTED_REVIEWER_ROLE:
        issues.append(
            {
                "section": "Document",
                "issue": f"Invalid critique reviewer_role in {CRITIQUE_REPORT_FILENAME}",
                "fix": f"Set reviewer_role to '{EXPECTED_REVIEWER_ROLE}' in {path_label}",
            }
        )
    if critique.get("version") != EXPECTED_CRITIQUE_VERSION:
        issues.append(
            {
                "section": "Document",
                "issue": f"Invalid critique version in {CRITIQUE_REPORT_FILENAME}",
                "fix": f"Set version to {EXPECTED_CRITIQUE_VERSION} in {path_label}",
            }
        )

    scoring = critique.get("scoring")
    if not isinstance(scoring, dict):
        issues.append(
            {
                "section": "Document",
                "issue": f"Missing or invalid scoring object in {CRITIQUE_REPORT_FILENAME}",
                "fix": "Write a scoring object with threshold, overall score, and gate boolean",
            }
        )
    else:
        if scoring.get("scale_min") != 0 or scoring.get("scale_max") != 100:
            issues.append(
                {
                    "section": "Document",
                    "issue": f"Invalid scoring scale in {CRITIQUE_REPORT_FILENAME}",
                    "fix": "Set scoring.scale_min=0 and scoring.scale_max=100",
                }
            )
        if scoring.get("threshold_strictly_greater_than") != QUALITY_THRESHOLD_STRICT_GT:
            issues.append(
                {
                    "section": "Document",
                    "issue": f"Invalid critique threshold in {CRITIQUE_REPORT_FILENAME}",
                    "fix": f"Set scoring.threshold_strictly_greater_than={QUALITY_THRESHOLD_STRICT_GT}",
                }
            )
        if scoring.get("calculation") != EXPECTED_CRITIQUE_CALC:
            issues.append(
                {
                    "section": "Document",
                    "issue": f"Invalid critique calculation mode in {CRITIQUE_REPORT_FILENAME}",
                    "fix": f"Set scoring.calculation to '{EXPECTED_CRITIQUE_CALC}'",
                }
            )

    criteria = critique.get("criteria")
    if not isinstance(criteria, list):
        issues.append(
            {
                "section": "Document",
                "issue": f"Missing or invalid criteria array in {CRITIQUE_REPORT_FILENAME}",
                "fix": "Write all required rubric criteria to critique_report.json",
            }
        )
        return issues

    seen_keys: set[str] = set()
    criteria_by_key: dict[str, dict[str, Any]] = {}
    for item in criteria:
        if not isinstance(item, dict):
            issues.append(
                {
                    "section": "Document",
                    "issue": f"Invalid criterion entry type in {CRITIQUE_REPORT_FILENAME}",
                    "fix": "Ensure each criteria[] item is an object",
                }
            )
            continue
        key = item.get("key")
        if not isinstance(key, str):
            issues.append(
                {
                    "section": "Document",
                    "issue": f"Criterion missing string key in {CRITIQUE_REPORT_FILENAME}",
                    "fix": "Provide a valid key for each criteria[] item",
                }
            )
            continue
        if key in seen_keys:
            issues.append(
                {
                    "section": "Document",
                    "issue": f"Duplicate criterion key in {CRITIQUE_REPORT_FILENAME}: {key}",
                    "fix": "Emit each rubric criterion exactly once",
                }
            )
            continue
        seen_keys.add(key)
        criteria_by_key[key] = item

        score = item.get("score")
        weight = item.get("weight_pct")
        primary_section = item.get("primary_section")
        if not isinstance(score, int) or score < 0 or score > 100:
            issues.append(
                {
                    "section": "Document",
                    "issue": f"Invalid score for criterion '{key}' in {CRITIQUE_REPORT_FILENAME}",
                    "fix": "Use integer criterion scores in the range 0..100",
                }
            )
        if not isinstance(weight, int):
            issues.append(
                {
                    "section": "Document",
                    "issue": f"Invalid weight for criterion '{key}' in {CRITIQUE_REPORT_FILENAME}",
                    "fix": "Use integer weight_pct values for all criteria",
                }
            )
        if not isinstance(primary_section, str) or primary_section not in REQUIRED_SECTIONS:
            issues.append(
                {
                    "section": "Document",
                    "issue": f"Invalid primary_section for criterion '{key}' in {CRITIQUE_REPORT_FILENAME}",
                    "fix": "Use a valid QA heading name for criterion primary_section",
                }
            )

    expected_keys = {key for key, _, _ in CRITIQUE_CRITERIA_SPEC}
    missing_keys = sorted(expected_keys - seen_keys)
    extra_keys = sorted(seen_keys - expected_keys)
    if missing_keys:
        issues.append(
            {
                "section": "Document",
                "issue": f"Missing critique criteria in {CRITIQUE_REPORT_FILENAME}: {', '.join(missing_keys)}",
                "fix": "Emit all required rubric criteria exactly once",
            }
        )
    if extra_keys:
        issues.append(
            {
                "section": "Document",
                "issue": f"Unexpected critique criteria in {CRITIQUE_REPORT_FILENAME}: {', '.join(extra_keys)}",
                "fix": "Use only the defined rubric criterion keys",
            }
        )

    if not missing_keys and not extra_keys:
        weight_sum = 0
        for key, _label, expected_weight in CRITIQUE_CRITERIA_SPEC:
            item = criteria_by_key.get(key, {})
            if item.get("weight_pct") != expected_weight:
                issues.append(
                    {
                        "section": "Document",
                        "issue": f"Incorrect weight for criterion '{key}' in {CRITIQUE_REPORT_FILENAME}",
                        "fix": f"Set weight_pct for '{key}' to {expected_weight}",
                    }
                )
            weight = item.get("weight_pct")
            if isinstance(weight, int):
                weight_sum += weight
        if weight_sum != 100:
            issues.append(
                {
                    "section": "Document",
                    "issue": f"Critique weights do not sum to 100 in {CRITIQUE_REPORT_FILENAME}",
                    "fix": "Ensure the rubric weight_pct values sum to 100",
                }
            )

    if isinstance(scoring, dict):
        computed = _weighted_quality_score(criteria)
        overall = scoring.get("overall_quality_score")
        gate = scoring.get("quality_gate_passed")
        if not isinstance(overall, int) or overall < 0 or overall > 100:
            issues.append(
                {
                    "section": "Document",
                    "issue": f"Invalid overall_quality_score in {CRITIQUE_REPORT_FILENAME}",
                    "fix": "Set an integer overall_quality_score in the range 0..100",
                }
            )
        elif overall != computed:
            issues.append(
                {
                    "section": "Document",
                    "issue": f"Critique overall_quality_score mismatch in {CRITIQUE_REPORT_FILENAME}",
                    "fix": f"Recompute weighted average and set overall_quality_score={computed}",
                }
            )
        expected_gate = computed > QUALITY_THRESHOLD_STRICT_GT
        if not isinstance(gate, bool):
            issues.append(
                {
                    "section": "Document",
                    "issue": f"Invalid quality_gate_passed in {CRITIQUE_REPORT_FILENAME}",
                    "fix": "Set scoring.quality_gate_passed to a boolean matching the threshold rule",
                }
            )
        elif gate != expected_gate:
            issues.append(
                {
                    "section": "Document",
                    "issue": f"Critique quality_gate_passed mismatch in {CRITIQUE_REPORT_FILENAME}",
                    "fix": f"Set scoring.quality_gate_passed to {str(expected_gate).lower()}",
                }
            )

    return issues


def _quality_summary_from_critique(critique: Any) -> dict[str, Any]:
    score = None
    passed = False
    if isinstance(critique, dict):
        scoring = critique.get("scoring")
        if isinstance(scoring, dict):
            if isinstance(scoring.get("overall_quality_score"), int):
                score = scoring["overall_quality_score"]
            if isinstance(scoring.get("quality_gate_passed"), bool):
                passed = scoring["quality_gate_passed"]
    return {
        "source": CRITIQUE_REPORT_FILENAME,
        "score": score,
        "threshold_rule": QUALITY_THRESHOLD_RULE,
        "passed": passed,
    }


def _quality_gate_issues(output_base: Path, critique: Any) -> tuple[list[dict[str, str]], dict[str, Any]]:
    critique_path = output_base / CRITIQUE_REPORT_FILENAME
    if critique_path.exists() and critique is None:
        issues = [
            {
                "section": "Document",
                "issue": f"{CRITIQUE_REPORT_FILENAME} is present but invalid JSON",
                "fix": f"Write valid JSON to {CRITIQUE_REPORT_FILENAME}",
            }
        ]
        return issues, _quality_summary_from_critique(None)

    schema_issues = _critique_schema_issues(output_base, critique)
    summary = _quality_summary_from_critique(critique)
    if schema_issues:
        return schema_issues, summary

    assert isinstance(critique, dict)
    scoring = critique["scoring"]
    criteria = critique["criteria"]
    overall_score = scoring["overall_quality_score"]
    summary = {
        "source": CRITIQUE_REPORT_FILENAME,
        "score": overall_score,
        "threshold_rule": QUALITY_THRESHOLD_RULE,
        "passed": overall_score > QUALITY_THRESHOLD_STRICT_GT,
    }
    if overall_score > QUALITY_THRESHOLD_STRICT_GT:
        return [], summary

    issues: list[dict[str, str]] = [
        {
            "section": "Document",
            "issue": f"Quality score {overall_score} does not meet threshold {QUALITY_THRESHOLD_RULE}",
            "fix": f"Improve weak areas identified in {CRITIQUE_REPORT_FILENAME} and raise quality score above {QUALITY_THRESHOLD_STRICT_GT}",
        }
    ]
    for item in criteria:
        key = str(item.get("key") or "")
        score = item.get("score")
        if not isinstance(score, int) or score >= 80:
            continue
        section = item.get("primary_section")
        if not isinstance(section, str) or section not in REQUIRED_SECTIONS:
            section = "Document"
        label = item.get("label")
        criterion_label = str(label) if isinstance(label, str) and label else key
        actions = item.get("recommended_actions")
        fix = None
        if isinstance(actions, list):
            for action in actions:
                if isinstance(action, str) and action.strip():
                    fix = action.strip()
                    break
        if not fix:
            fix = f"Improve documentation quality for {criterion_label}"
        issues.append(
            {
                "section": section,
                "issue": f"Low quality score for {criterion_label}: {score}/100",
                "fix": fix,
            }
        )
    return issues, summary


def main(output_dir: str | None = None) -> int:
    # Run deterministic checks and emit a structured review report.
    root = Path(__file__).resolve().parent
    output_base = root / output_dir if output_dir else root / "outputs"
    doc_path = output_base / "design_doc.md"
    report_path = output_base / "review_report.json"
    prior_review_path = output_base / "inputs" / "previous_review_report.json"
    critique_path = output_base / CRITIQUE_REPORT_FILENAME

    doc = load_doc(doc_path)
    issues: list[dict[str, str]] = []

    if not doc:
        issues.append(
            {
                "section": "Document",
                "issue": "Missing output",
                "fix": "Run the CrewAI pipeline to generate outputs/design_doc.md",
            }
        )
    else:
        sections_dir = output_base / "sections"
        validate_section_file(
            sections_dir / "requirements.md",
            ["Problem Statement", "Goals", "Non-Goals", "Assumptions"],
            issues,
        )
        validate_section_file(
            sections_dir / "architecture.md",
            ["Architecture Overview", "Components", "Trade-offs", "Diagram", "Assumptions"],
            issues,
        )
        validate_section_file(
            sections_dir / "data_api.md",
            ["Data Design", "Entities", "Data Flows", "Storage/Retention", "API / Interface Contracts", "Assumptions"],
            issues,
        )
        validate_section_file(
            sections_dir / "security.md",
            ["Risks & Mitigations", "Security Controls", "Assumptions"],
            issues,
        )
        validate_section_file(
            sections_dir / "nfrs_ops.md",
            ["Non-Functional Requirements", "Observability", "Ops Runbooks", "Assumptions"],
            issues,
        )

        missing = find_missing_sections(doc)
        for section in missing:
            issues.append(
                {
                    "section": section,
                    "issue": "Missing required section",
                    "fix": f"Add a '## {section}' section",
                }
            )

        if prior_review_path.exists():
            if prior_review_path.stat().st_size == 0:
                issues.append(
                    {
                        "section": "Inputs",
                        "issue": "Previous QA report is empty",
                        "fix": "Ensure inputs/previous_review_report.json contains content",
                    }
                )
            else:
                prior_review_section = extract_section_body(doc, "Prior QA Report Review").lower()
                if not mentions_prior_qa_review(prior_review_section):
                    issues.append(
                        {
                            "section": "Document",
                            "issue": "No indication that previous QA report was reviewed",
                            "fix": "Mention review of the previous QA report in the 'Prior QA Report Review' section",
                        }
                    )

        placeholders = find_placeholders(doc)
        if placeholders:
            issues.append(
                {
                    "section": "Document",
                    "issue": f"Placeholders present: {', '.join(placeholders)}",
                    "fix": "Replace placeholders with real content or remove",
                }
            )

    critique = _load_json(critique_path)
    quality_issues, quality_summary = _quality_gate_issues(output_base, critique)
    issues.extend(quality_issues)

    status = "PASS" if not issues else "FAIL"
    report = {"status": status, "issues": issues, "quality": quality_summary}
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
