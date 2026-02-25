import json
from pathlib import Path
from typing import Any


REQUIRED_KEYS = {
    "source_review_found": bool,
    "source_review_valid": bool,
    "status": str,
    "selected_headings": list,
    "deferred_headings": list,
    "rationale": list,
    "related_change_rule": str,
    "notes": list,
}
VALID_STATUSES = {"prioritized", "baseline_no_prior_review"}
RELATED_CHANGE_RULE = (
    "Non-priority sections may be changed only when directly required by selected "
    "priority fixes or consistency with current inputs."
)


def _strip_markdown_fences(text: str) -> str:
    raw = text.strip()
    if not raw.startswith("```"):
        return raw
    lines = raw.splitlines()
    if len(lines) < 2:
        return raw
    if not lines[0].startswith("```"):
        return raw
    if lines[-1].strip() != "```":
        return raw
    return "\n".join(lines[1:-1]).strip()


def baseline_priority_plan(reason: str) -> dict[str, Any]:
    return {
        "source_review_found": False,
        "source_review_valid": False,
        "status": "baseline_no_prior_review",
        "selected_headings": [],
        "deferred_headings": [
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
            "Assumptions",
        ],
        "rationale": [reason],
        "related_change_rule": RELATED_CHANGE_RULE,
        "notes": [],
    }


def _validate_priority_plan(data: Any) -> str | None:
    if not isinstance(data, dict):
        return "priority plan is not a JSON object"
    for key, expected_type in REQUIRED_KEYS.items():
        if key not in data:
            return f"missing key: {key}"
        if not isinstance(data[key], expected_type):
            return f"invalid type for {key}: expected {expected_type.__name__}"
    if data["status"] not in VALID_STATUSES:
        return f"invalid status: {data['status']}"
    for key in ["selected_headings", "deferred_headings", "rationale", "notes"]:
        if not all(isinstance(item, str) for item in data[key]):
            return f"{key} must contain only strings"
    return None


def load_and_normalize_priority_plan(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, "priority plan file not found"
    raw_text = path.read_text(encoding="utf-8")
    if not raw_text.strip():
        return None, "priority plan file is empty"

    cleaned = _strip_markdown_fences(raw_text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"

    error = _validate_priority_plan(data)
    if error:
        return None, error
    return data, None


def write_priority_plan(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
