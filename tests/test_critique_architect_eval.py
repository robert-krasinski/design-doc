import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("crewai")

import orchestrator
import qa
from config import configure_llm_defaults


def _env_flag_enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _write_sample_design_doc(out_dir: Path) -> None:
    chunks: list[str] = []
    for heading in qa.REQUIRED_SECTIONS:
        if heading == "Problem Statement":
            body = "- Users need a reproducible design document generation pipeline.\n- The system should reduce iteration churn."
        elif heading == "Goals":
            body = "- Generate a complete design doc with all required sections.\n- Improve rerun convergence using QA feedback."
        elif heading == "Non-Goals":
            body = "- Building a production deployment system.\n- Replacing human architectural review entirely."
        elif heading == "Context & Constraints":
            body = "- Local LLM endpoint is used via OpenAI-compatible API.\n- Outputs must be stored in run-scoped folders."
        elif heading == "Architecture Overview":
            body = "The pipeline snapshots inputs, runs specialized agents, integrates section outputs, critiques the final document, then runs deterministic QA."
        elif heading == "Data Design":
            body = "- Run artifacts are persisted as JSON/Markdown files under outputs/YYYY-MM-DD/run_*/.\n- Review and critique reports are machine-readable."
        elif heading == "API / Interface Contracts":
            body = "| Endpoint | Method | Request | Response | Errors |\n| --- | --- | --- | --- | --- |\n| /v1/chat/completions | POST | OpenAI chat payload | completion/tool calls | provider/validation errors |"
        elif heading == "Non-Functional Requirements":
            body = "| Metric | Target | Notes |\n| --- | --- | --- |\n| QA pass rate | >80% over runs | Measured per run |\n| Critique JSON validity | 100% | Strict schema enforced |"
        elif heading == "Risks & Mitigations":
            body = "| Threat | Impact | Likelihood | Mitigation |\n| --- | --- | --- | --- |\n| Invalid LLM JSON | QA false fail | Medium | Strict prompt + validation + retries |"
        elif heading == "Rollout Plan":
            body = "- Add critique task after integrate.\n- Fail closed on missing/invalid critique output.\n- Monitor rerun behavior."
        elif heading == "Test Strategy":
            body = "- Unit tests for QA schema validation.\n- Orchestrator tests for task ordering.\n- LLM integration test for critique-only path."
        elif heading == "Decision Log":
            body = "- Added quality gate threshold >80.\n- Kept review_report.json backward-compatible with new quality object."
        elif heading == "Prior QA Report Review":
            body = "- No prior review for this isolated critique-only integration test."
        elif heading == "Assumptions":
            body = "- The local model supports tool calls and can emit strict JSON."
        else:
            body = "Text."
        chunks.append(f"## {heading}\n{body}")
    (out_dir / "design_doc.md").write_text("\n\n".join(chunks) + "\n", encoding="utf-8")


def _copy_run_inputs(run_inputs_dir: Path) -> None:
    source_dir = ROOT / "inputs"
    assert source_dir.exists(), f"Missing inputs dir: {source_dir}"
    run_inputs_dir.mkdir(parents=True, exist_ok=True)
    for source in source_dir.iterdir():
        if source.is_file():
            shutil.copy2(source, run_inputs_dir / source.name)


def _make_output_dir() -> tuple[Path, str]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rel = f"outputs/test-critique-eval-{stamp}"
    out_dir = ROOT / rel
    (out_dir / "inputs").mkdir(parents=True, exist_ok=True)
    return out_dir, rel


@pytest.mark.llm_integration
@pytest.mark.critique_eval
def test_critique_agent_output_schema_llm_eval() -> None:
    if not _env_flag_enabled("RUN_LLM_INTEGRATION_TESTS"):
        pytest.skip("Set RUN_LLM_INTEGRATION_TESTS=1 to enable real LLM integration tests.")

    configure_llm_defaults()
    base_url = os.environ.get("OPENAI_API_BASE") or os.environ.get("OPENAI_BASE_URL") or os.environ.get("LOCAL_LLM_BASE_URL")
    model = os.environ.get("LOCAL_LLM_MODEL") or os.environ.get("OPENAI_MODEL_NAME") or os.environ.get("MODEL")
    if not base_url or not model:
        pytest.skip("LLM config missing: set base URL and model env vars for integration test.")

    out_dir, output_dir = _make_output_dir()
    _copy_run_inputs(out_dir / "inputs")
    _write_sample_design_doc(out_dir)

    orchestrator.run_critique_only(output_dir, None, None)

    critique_path = out_dir / "critique_report.json"
    assert critique_path.exists(), f"Missing critique output: {critique_path}"

    raw = critique_path.read_text(encoding="utf-8")
    try:
        critique = json.loads(raw)
    except json.JSONDecodeError as exc:
        pytest.fail(f"critique_report.json is not strict JSON: {exc}\nRaw output:\n{raw}")

    schema_issues = qa._critique_schema_issues(out_dir, critique)
    assert schema_issues == [], f"Critique schema validation failed:\n{json.dumps(schema_issues, indent=2)}"

    scoring = critique["scoring"]
    assert isinstance(scoring["overall_quality_score"], int)
    assert 0 <= scoring["overall_quality_score"] <= 100
    assert scoring["threshold_strictly_greater_than"] == 80
    assert scoring["calculation"] == "weighted_average_rounded"

    criteria = critique["criteria"]
    assert len(criteria) == len(qa.CRITIQUE_CRITERIA_SPEC)
    assert sum(int(item["weight_pct"]) for item in criteria) == 100

