import json
from pathlib import Path

import pytest

import top_orchestrator


ROOT = Path(__file__).resolve().parents[1]


def _prepare_output_dir(name: str) -> str:
    output_dir = f"outputs/{name}"
    (ROOT / output_dir).mkdir(parents=True, exist_ok=True)
    return output_dir


def _fake_qa_factory(statuses: list[str]):
    idx = {"value": 0}

    def _fake_qa(output_dir: str) -> int:
        status = statuses[min(idx["value"], len(statuses) - 1)]
        idx["value"] += 1
        report_path = ROOT / output_dir / "review_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps({"status": status, "issues": []}, indent=2),
            encoding="utf-8",
        )
        return 0 if status == "PASS" else 1

    return _fake_qa


def test_runs_once_when_first_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    output_dir = _prepare_output_dir("test-run-pass")

    run_calls = {"count": 0}

    def _run_crew(*_args, **_kwargs) -> None:
        run_calls["count"] += 1

    monkeypatch.setattr(
        top_orchestrator,
        "_get_crew_functions",
        lambda: (lambda: None, _run_crew),
    )
    monkeypatch.setattr(top_orchestrator, "_run_qa", _fake_qa_factory(["PASS"]))

    top_orchestrator.run_top_orchestrator(
        output_dir,
        previous_doc_path=None,
        previous_review_path=None,
        max_runs=10,
        crew_enabled=True,
    )

    assert run_calls["count"] == 1


def test_reruns_until_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    output_dir = _prepare_output_dir("test-run-rerun")

    run_calls = {"count": 0}

    def _run_crew(*_args, **_kwargs) -> None:
        run_calls["count"] += 1

    monkeypatch.setattr(
        top_orchestrator,
        "_get_crew_functions",
        lambda: (lambda: None, _run_crew),
    )
    monkeypatch.setattr(top_orchestrator, "_run_qa", _fake_qa_factory(["FAIL", "FAIL", "PASS"]))

    top_orchestrator.run_top_orchestrator(
        output_dir,
        previous_doc_path=None,
        previous_review_path=None,
        max_runs=10,
        crew_enabled=True,
    )

    assert run_calls["count"] == 3


def test_caps_at_max_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    output_dir = _prepare_output_dir("test-run-cap")

    run_calls = {"count": 0}

    def _run_crew(*_args, **_kwargs) -> None:
        run_calls["count"] += 1

    monkeypatch.setattr(
        top_orchestrator,
        "_get_crew_functions",
        lambda: (lambda: None, _run_crew),
    )
    monkeypatch.setattr(top_orchestrator, "_run_qa", _fake_qa_factory(["FAIL"]))

    top_orchestrator.run_top_orchestrator(
        output_dir,
        previous_doc_path=None,
        previous_review_path=None,
        max_runs=10,
        crew_enabled=True,
    )

    assert run_calls["count"] == 10
