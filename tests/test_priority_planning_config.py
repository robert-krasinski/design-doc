from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def test_agents_yaml_contains_prioritizer_agent() -> None:
    config = _load_yaml(ROOT / "crew" / "config" / "agents.yaml")
    assert "prioritizer_agent" in config
    assert "select the 2 most important headings" in config["prioritizer_agent"]["goal"]


def test_agents_yaml_contains_critique_architect_agent() -> None:
    config = _load_yaml(ROOT / "crew" / "config" / "agents.yaml")
    assert "critique_architect" in config
    assert "IT super architect" in config["critique_architect"]["backstory"]


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


def test_tasks_yaml_contains_critique_task_and_output() -> None:
    config = _load_yaml(ROOT / "crew" / "config" / "tasks.yaml")
    description = config["critique_design_doc"]["description"]
    assert config["critique_design_doc"]["output_file"] == "{output_dir}/critique_report.json"
    assert "weighted" in description
    assert "overall_quality_score" in description
    assert "strictly greater than 80" in description
    assert "raw JSON only" in description


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


def test_section_tasks_and_agents_require_tool_reads() -> None:
    tasks_config = _load_yaml(ROOT / "crew" / "config" / "tasks.yaml")
    agents_config = _load_yaml(ROOT / "crew" / "config" / "agents.yaml")

    for task_key in ["requirements", "architecture", "data_api", "security", "sre"]:
        task_description = tasks_config[task_key]["description"]
        assert "Mandatory first steps (use tools):" in task_description
        assert 'list_dir("{output_dir}/inputs")' in task_description
        assert 'read_file("{output_dir}/inputs/context.md")' in task_description
        assert 'read_file("{output_dir}/inputs/constraints.yaml")' in task_description
        assert "Do not draft output before reading the run-scoped input files" in task_description

    integrate_description = tasks_config["integrate"]["description"]
    assert "Mandatory first steps (use tools):" in integrate_description
    assert 'list_dir("{output_dir}/inputs")' in integrate_description
    assert 'list_dir("{output_dir}/sections")' in integrate_description
    assert 'read_file("templates/design_doc.md")' in integrate_description
    assert "Do not draft output before reading available run-scoped section files" in integrate_description

    for agent_key in [
        "product_scope_analyst",
        "solution_architect",
        "data_api_designer",
        "security_reviewer",
        "sre_reviewer",
        "editor_integrator",
    ]:
        agent_backstory = agents_config[agent_key]["backstory"]
        assert "Use the list_dir and read_file tools" in agent_backstory
        assert "before drafting" in agent_backstory


def test_orchestrator_runs_prioritizer_before_requirements() -> None:
    content = (ROOT / "orchestrator.py").read_text(encoding="utf-8")
    run_crew_start = content.index("def run_crew(")
    run_crew_body = content[run_crew_start:]
    prioritizer_call = 'task_prioritize_review_fixes('
    requirements_call = 'task_requirements('
    assert prioritizer_call in run_crew_body
    assert requirements_call in run_crew_body
    assert run_crew_body.index(prioritizer_call) < run_crew_body.index(requirements_call)


def test_orchestrator_runs_critique_after_integrate() -> None:
    content = (ROOT / "orchestrator.py").read_text(encoding="utf-8")
    run_crew_start = content.index("def run_crew(")
    run_crew_body = content[run_crew_start:]
    integrate_call = "task_integrate("
    critique_call = "task_critique_design_doc("
    assert integrate_call in run_crew_body
    assert critique_call in run_crew_body
    assert run_crew_body.index(integrate_call) < run_crew_body.index(critique_call)
