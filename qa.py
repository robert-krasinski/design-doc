import json
from pathlib import Path
from typing import List

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


def load_doc(path: Path) -> str:
    # Read the generated document if present; empty string otherwise.
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


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


def main(output_dir: str | None = None) -> int:
    # Run deterministic checks and emit a structured review report.
    root = Path(__file__).resolve().parent
    output_base = root / output_dir if output_dir else root / "outputs"
    doc_path = output_base / "design_doc.md"
    report_path = output_base / "review_report.json"
    prior_review_path = output_base / "inputs" / "previous_review_report.json"

    doc = load_doc(doc_path)
    issues = []

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
            elif "prior qa report" not in doc.lower() and "previous qa report" not in doc.lower():
                issues.append(
                    {
                        "section": "Document",
                        "issue": "No indication that previous QA report was reviewed",
                        "fix": "Mention review of previous QA report in Assumptions or Decision Log",
                    }
                )
        else:
            issues.append(
                {
                    "section": "Inputs",
                    "issue": "Previous QA report not found for this run",
                    "fix": "Ensure inputs/previous_review_report.json is created before the run",
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

    status = "PASS" if not issues else "FAIL"
    report = {"status": status, "issues": issues}
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
