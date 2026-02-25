from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def test_agents_yaml_contains_prioritizer_agent() -> None:
    config = _load_yaml(ROOT / "crew" / "config" / "agents.yaml")
    assert "prioritizer_agent" in config
    assert "select the 2 most important headings" in config["prioritizer_agent"]["goal"]


def test_tasks_yaml_contains_prioritizer_task_and_priority_plan_output() -> None:
    config = _load_yaml(ROOT / "crew" / "config" / "tasks.yaml")
    assert "prioritize_review_fixes" in config
    assert config["prioritize_review_fixes"]["output_file"] == "{output_dir}/priority_plan.json"
    assert "strict JSON prioritization plan" in config["prioritize_review_fixes"]["description"]
    assert "{output_dir}/inputs/previous_review_report.json" in config["prioritize_review_fixes"]["description"]
    assert "read_file" in config["prioritize_review_fixes"]["description"]
    assert "list_dir" in config["prioritize_review_fixes"]["description"]
    assert "raw JSON only" in config["prioritize_review_fixes"]["description"]


def test_section_tasks_reference_priority_plan() -> None:
    config = _load_yaml(ROOT / "crew" / "config" / "tasks.yaml")
    for task_key in ["requirements", "architecture", "data_api", "security", "sre", "integrate"]:
        assert "{output_dir}/priority_plan.json" in config[task_key]["description"]


def test_orchestrator_runs_prioritizer_before_requirements() -> None:
    content = (ROOT / "orchestrator.py").read_text(encoding="utf-8")
    prioritizer_call = 'task_prioritize_review_fixes('
    requirements_call = 'task_requirements('
    assert prioritizer_call in content
    assert requirements_call in content
    assert content.index(prioritizer_call) < content.index(requirements_call)
