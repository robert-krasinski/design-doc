import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("crewai")

from crew.tasks import _task_config


def test_task_config_appends_run_specific_prior_context() -> None:
    output_dir = "outputs/2026-02-25/run_test"
    prior_context = (
        "Run-specific prior artifacts (if present):\n"
        "- Prior design doc: `outputs/x/inputs/previous_design_doc.md`\n"
        "- Prior QA report: `outputs/x/inputs/previous_review_report.json`"
    )
    task = _task_config("prioritize_review_fixes", output_dir, prior_context)

    assert "{output_dir}" not in task["description"]
    assert "Run-specific prior artifacts (if present):" in task["description"]
    assert "outputs/x/inputs/previous_review_report.json" in task["description"]
    assert task["output_file"] == f"{output_dir}/priority_plan.json"
