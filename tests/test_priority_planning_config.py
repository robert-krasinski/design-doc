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
    description = config["prioritize_review_fixes"]["description"]
    assert "prioritize_review_fixes" in config
    assert config["prioritize_review_fixes"]["output_file"] == "{output_dir}/priority_plan.json"
    assert "strict JSON prioritization plan" in description
    assert "{output_dir}/inputs/previous_review_report.json" in description
    assert "read_file" in description
    assert "list_dir" in description
    assert "raw JSON only" in description
    assert "`status` value may be `FAIL` and is still valid input" in description
    assert "missing, empty, or invalid JSON" in description
    assert "do not emit `baseline_no_prior_review`" in description
    assert 'set `status` to `prioritized`' in description


def test_prioritizer_agent_and_task_enforce_nonbaseline_for_valid_rerun_review() -> None:
    tasks_config = _load_yaml(ROOT / "crew" / "config" / "tasks.yaml")
    agents_config = _load_yaml(ROOT / "crew" / "config" / "agents.yaml")

    task_description = tasks_config["prioritize_review_fixes"]["description"]
    agent_backstory = agents_config["prioritizer_agent"]["backstory"]

    assert "parses as JSON, do not emit `baseline_no_prior_review`" in task_description
    assert "If `source_review_valid` is `true`, set `status` to `prioritized`." in task_description
    assert "QA report `status: FAIL` is still valid prior review input." in agent_backstory
    assert "do not emit baseline" in agent_backstory
    assert "Emit a baseline fallback priority plan only when the prior review is missing, empty, or invalid JSON." in agent_backstory


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
