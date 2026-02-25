import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("crewai")

import orchestrator


def _make_valid_priority_plan(selected: list[str]) -> dict:
    return {
        "source_review_found": True,
        "source_review_valid": True,
        "status": "prioritized",
        "selected_headings": selected,
        "deferred_headings": ["Decision Log"],
        "rationale": ["Test fixture."],
        "related_change_rule": "Non-priority sections may be changed only when directly required by selected priority fixes or consistency with current inputs.",
        "notes": [],
    }


def test_ensure_valid_priority_plan_normalizes_fenced_json() -> None:
    output_dir = "outputs/test-priority-normalize"
    out_dir = ROOT / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_path = out_dir / "priority_plan.json"
    plan_path.write_text(
        "```json\n" + json.dumps(_make_valid_priority_plan(["Rollout Plan"]), indent=2) + "\n```",
        encoding="utf-8",
    )

    data = orchestrator._ensure_valid_priority_plan(ROOT, output_dir)

    assert data["status"] == "prioritized"
    persisted = plan_path.read_text(encoding="utf-8")
    assert not persisted.lstrip().startswith("```")
    assert json.loads(persisted)["selected_headings"] == ["Rollout Plan"]


def test_ensure_valid_priority_plan_writes_baseline_on_invalid_json() -> None:
    output_dir = "outputs/test-priority-invalid"
    out_dir = ROOT / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_path = out_dir / "priority_plan.json"
    plan_path.write_text("{not json}", encoding="utf-8")

    data = orchestrator._ensure_valid_priority_plan(ROOT, output_dir)

    assert data["status"] == "baseline_no_prior_review"
    persisted = json.loads(plan_path.read_text(encoding="utf-8"))
    assert persisted["status"] == "baseline_no_prior_review"
    assert persisted["source_review_found"] is False


def test_run_crew_sanitizes_priority_plan_before_phase_b(monkeypatch: pytest.MonkeyPatch) -> None:
    output_dir = "outputs/test-run-priority-phase"
    out_dir = ROOT / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "inputs").mkdir(parents=True, exist_ok=True)
    (out_dir / "inputs" / "previous_review_report.json").write_text(
        json.dumps({"status": "FAIL", "issues": [{"section": "Rollout Plan"}]}, indent=2),
        encoding="utf-8",
    )

    monkeypatch.setattr(orchestrator, "build_llm", lambda: object())
    monkeypatch.setattr(orchestrator, "prioritizer_agent", lambda llm=None: "prioritizer")
    monkeypatch.setattr(orchestrator, "product_scope_analyst", lambda llm=None: "product")
    monkeypatch.setattr(orchestrator, "solution_architect", lambda llm=None: "arch")
    monkeypatch.setattr(orchestrator, "data_api_designer", lambda llm=None: "data")
    monkeypatch.setattr(orchestrator, "security_reviewer", lambda llm=None: "sec")
    monkeypatch.setattr(orchestrator, "sre_reviewer", lambda llm=None: "sre")
    monkeypatch.setattr(orchestrator, "editor_integrator", lambda llm=None: "edit")
    monkeypatch.setattr(orchestrator, "task_prioritize_review_fixes", lambda *args, **kwargs: "prioritizer_task")
    monkeypatch.setattr(orchestrator, "task_requirements", lambda *args, **kwargs: "requirements_task")
    monkeypatch.setattr(orchestrator, "task_architecture", lambda *args, **kwargs: "architecture_task")
    monkeypatch.setattr(orchestrator, "task_data_api", lambda *args, **kwargs: "data_api_task")
    monkeypatch.setattr(orchestrator, "task_security", lambda *args, **kwargs: "security_task")
    monkeypatch.setattr(orchestrator, "task_sre", lambda *args, **kwargs: "sre_task")
    monkeypatch.setattr(orchestrator, "task_integrate", lambda *args, **kwargs: "integrate_task")

    calls: list[int] = []
    plan_path = out_dir / "priority_plan.json"

    def _fake_run_tasks_with_crew(_agents, tasks) -> None:
        calls.append(len(tasks))
        if len(tasks) == 1:
            plan_path.write_text(
                "```json\n" + json.dumps(_make_valid_priority_plan(["Rollout Plan"]), indent=2) + "\n```",
                encoding="utf-8",
            )
        else:
            persisted = plan_path.read_text(encoding="utf-8")
            assert not persisted.lstrip().startswith("```")
            assert json.loads(persisted)["selected_headings"] == ["Rollout Plan"]

    monkeypatch.setattr(orchestrator, "_run_tasks_with_crew", _fake_run_tasks_with_crew)

    orchestrator.run_crew(output_dir, None, None)

    assert calls == [1, 6]


def test_run_crew_prioritizer_failure_falls_back_and_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    output_dir = "outputs/test-run-priority-failure-fallback"
    out_dir = ROOT / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "inputs").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(orchestrator, "build_llm", lambda: object())
    monkeypatch.setattr(orchestrator, "prioritizer_agent", lambda llm=None: "prioritizer")
    monkeypatch.setattr(orchestrator, "product_scope_analyst", lambda llm=None: "product")
    monkeypatch.setattr(orchestrator, "solution_architect", lambda llm=None: "arch")
    monkeypatch.setattr(orchestrator, "data_api_designer", lambda llm=None: "data")
    monkeypatch.setattr(orchestrator, "security_reviewer", lambda llm=None: "sec")
    monkeypatch.setattr(orchestrator, "sre_reviewer", lambda llm=None: "sre")
    monkeypatch.setattr(orchestrator, "editor_integrator", lambda llm=None: "edit")
    monkeypatch.setattr(orchestrator, "task_prioritize_review_fixes", lambda *args, **kwargs: "prioritizer_task")
    monkeypatch.setattr(orchestrator, "task_requirements", lambda *args, **kwargs: "requirements_task")
    monkeypatch.setattr(orchestrator, "task_architecture", lambda *args, **kwargs: "architecture_task")
    monkeypatch.setattr(orchestrator, "task_data_api", lambda *args, **kwargs: "data_api_task")
    monkeypatch.setattr(orchestrator, "task_security", lambda *args, **kwargs: "security_task")
    monkeypatch.setattr(orchestrator, "task_sre", lambda *args, **kwargs: "sre_task")
    monkeypatch.setattr(orchestrator, "task_integrate", lambda *args, **kwargs: "integrate_task")

    calls: list[int] = []
    plan_path = out_dir / "priority_plan.json"

    def _fake_run_tasks_with_crew(_agents, tasks) -> None:
        calls.append(len(tasks))
        if len(tasks) == 1:
            raise ValueError("Invalid response from LLM call - None or empty.")
        persisted = json.loads(plan_path.read_text(encoding="utf-8"))
        assert persisted["status"] == "baseline_no_prior_review"
        assert persisted["source_review_found"] is False
        assert persisted["source_review_valid"] is False

    monkeypatch.setattr(orchestrator, "_run_tasks_with_crew", _fake_run_tasks_with_crew)

    orchestrator.run_crew(output_dir, None, None)

    assert calls == [1, 6]
