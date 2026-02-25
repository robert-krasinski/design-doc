import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from priority_plan import load_and_normalize_priority_plan, write_priority_plan


def test_load_and_normalize_priority_plan_accepts_plain_json(tmp_path: Path) -> None:
    path = tmp_path / "priority_plan.json"
    write_priority_plan(
        path,
        {
            "source_review_found": True,
            "source_review_valid": True,
            "status": "prioritized",
            "selected_headings": ["Rollout Plan"],
            "deferred_headings": ["Decision Log"],
            "rationale": ["Only actionable issue in prior QA report."],
            "related_change_rule": "Non-priority sections may be changed only when directly required by selected priority fixes or consistency with current inputs.",
            "notes": [],
        },
    )

    data, error = load_and_normalize_priority_plan(path)
    assert error is None
    assert data is not None
    assert data["status"] == "prioritized"


def test_load_and_normalize_priority_plan_strips_markdown_fences(tmp_path: Path) -> None:
    path = tmp_path / "priority_plan.json"
    path.write_text(
        """```json
{
  "source_review_found": false,
  "source_review_valid": false,
  "status": "baseline_no_prior_review",
  "selected_headings": [],
  "deferred_headings": ["Rollout Plan"],
  "rationale": ["No prior review report found or invalid JSON."],
  "related_change_rule": "Non-priority sections may be changed only when directly required by selected priority fixes or consistency with current inputs.",
  "notes": []
}
```""",
        encoding="utf-8",
    )

    data, error = load_and_normalize_priority_plan(path)
    assert error is None
    assert data is not None
    assert data["status"] == "baseline_no_prior_review"


def test_load_and_normalize_priority_plan_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "priority_plan.json"
    path.write_text("{not json}", encoding="utf-8")

    data, error = load_and_normalize_priority_plan(path)
    assert data is None
    assert error is not None
    assert "invalid JSON" in error


def test_load_and_normalize_priority_plan_rejects_missing_keys(tmp_path: Path) -> None:
    path = tmp_path / "priority_plan.json"
    path.write_text('{"status":"prioritized"}', encoding="utf-8")

    data, error = load_and_normalize_priority_plan(path)
    assert data is None
    assert error is not None
    assert "missing key" in error


def test_load_and_normalize_priority_plan_rejects_wrong_types(tmp_path: Path) -> None:
    path = tmp_path / "priority_plan.json"
    path.write_text(
        """{
  "source_review_found": "true",
  "source_review_valid": true,
  "status": "prioritized",
  "selected_headings": [],
  "deferred_headings": [],
  "rationale": [],
  "related_change_rule": "x",
  "notes": []
}""",
        encoding="utf-8",
    )

    data, error = load_and_normalize_priority_plan(path)
    assert data is None
    assert error is not None
    assert "invalid type" in error
