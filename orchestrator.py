import json
import logging
import os
from pathlib import Path

from crewai import Crew, LLM, Process
from openai import OpenAI

from crew.agents import (
    critique_architect,
    data_api_designer,
    editor_integrator,
    prioritizer_agent,
    product_scope_analyst,
    security_reviewer,
    solution_architect,
    sre_reviewer,
)
from crew.tasks import (
    task_architecture,
    task_critique_design_doc,
    task_data_api,
    task_integrate,
    task_prioritize_review_fixes,
    task_requirements,
    task_security,
    task_sre,
)
from priority_plan import baseline_priority_plan, load_and_normalize_priority_plan, write_priority_plan


def build_llm() -> LLM:
    # Explicitly bind to an OpenAI-compatible provider for local servers.
    model = os.environ.get("LOCAL_LLM_MODEL", "qwen/qwen2.5-vl-7b")
    base_url = os.environ.get("OPENAI_API_BASE") or os.environ.get("OPENAI_BASE_URL")
    api_key = os.environ.get("OPENAI_API_KEY", "local")
    return LLM(model=model, provider="openai", base_url=base_url, api_key=api_key)


def preflight_tool_calling_check() -> None:
    # Fast fail if the current model/server does not support tool calls.
    model = os.environ.get("LOCAL_LLM_MODEL", "qwen/qwen2.5-vl-7b")
    base_url = os.environ.get("OPENAI_API_BASE") or os.environ.get("OPENAI_BASE_URL")
    if not base_url:
        raise RuntimeError("OPENAI_API_BASE is not set for preflight tool-calling check.")

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "local"), base_url=base_url)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "ping",
                "description": "Return a static acknowledgement.",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Call the ping tool."}],
        tools=tools,
        tool_choice="auto",
    )
    if not response.choices or not response.choices[0].message.tool_calls:
        raise RuntimeError(
            "Tool-calling preflight failed: LLM did not return tool_calls. "
            f"model={model} base_url={base_url}"
        )


def _run_tasks_with_crew(agents: list[object], tasks: list[object]) -> None:
    crew = Crew(
        agents=agents,
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
        tracing=True,
    )
    crew.kickoff()


def _log_prior_review_state(root: Path, output_dir: str) -> None:
    logger = logging.getLogger(__name__)
    prior_review_path = root / output_dir / "inputs" / "previous_review_report.json"
    if not prior_review_path.exists():
        logger.info("Prior review input missing: %s", str(prior_review_path))
        return
    size = prior_review_path.stat().st_size
    try:
        data = json.loads(prior_review_path.read_text(encoding="utf-8"))
        sections = [
            issue.get("section")
            for issue in data.get("issues", [])
            if isinstance(issue, dict) and isinstance(issue.get("section"), str)
        ]
        logger.info(
            "Prior review input found: path=%s size=%s parsed=true issue_sections=%s",
            str(prior_review_path),
            size,
            sections,
        )
    except json.JSONDecodeError as exc:
        logger.info(
            "Prior review input found: path=%s size=%s parsed=false error=%s",
            str(prior_review_path),
            size,
            exc,
        )


def _ensure_valid_priority_plan(root: Path, output_dir: str) -> dict:
    logger = logging.getLogger(__name__)
    plan_path = root / output_dir / "priority_plan.json"
    data, error = load_and_normalize_priority_plan(plan_path)
    if data is None:
        fallback_reason = f"Priority plan fallback: {error or 'unknown validation error'}"
        data = baseline_priority_plan(fallback_reason)
        write_priority_plan(plan_path, data)
        logger.warning("Priority plan invalid; wrote baseline fallback: %s path=%s", fallback_reason, str(plan_path))
        return data

    write_priority_plan(plan_path, data)
    logger.info(
        "Priority plan validated: path=%s status=%s selected=%s deferred=%s",
        str(plan_path),
        data.get("status"),
        data.get("selected_headings"),
        data.get("deferred_headings"),
    )
    return data


def run_product_scope_requirements_only(
    output_dir: str,
    previous_doc_path: str | None = None,
    previous_review_path: str | None = None,
    *,
    llm: object | None = None,
) -> None:
    # Focused execution path used by tests/debugging to run only the product requirements task.
    resolved_llm = llm if llm is not None else build_llm()
    product_agent = product_scope_analyst(llm=resolved_llm)
    requirements_task = task_requirements(product_agent, output_dir, previous_doc_path, previous_review_path)
    _run_tasks_with_crew([product_agent], [requirements_task])


def run_critique_only(
    output_dir: str,
    previous_doc_path: str | None = None,
    previous_review_path: str | None = None,
    *,
    llm: object | None = None,
) -> None:
    # Focused execution path used by tests/debugging to run only the critique task on an existing design_doc.md.
    resolved_llm = llm if llm is not None else build_llm()
    critique_agent = critique_architect(llm=resolved_llm)
    critique_task = task_critique_design_doc(critique_agent, output_dir, previous_doc_path, previous_review_path)
    _run_tasks_with_crew([critique_agent], [critique_task])


def run_crew(output_dir: str, previous_doc_path: str | None, previous_review_path: str | None) -> None:
    # Build agents and tasks from config-driven definitions.
    root = Path(__file__).resolve().parent
    llm = build_llm()
    agents = {
        "prioritizer": prioritizer_agent(llm=llm),
        "product": product_scope_analyst(llm=llm),
        "arch": solution_architect(llm=llm),
        "data": data_api_designer(llm=llm),
        "sec": security_reviewer(llm=llm),
        "sre": sre_reviewer(llm=llm),
        "edit": editor_integrator(llm=llm),
        "critique": critique_architect(llm=llm),
    }

    prioritizer_task = task_prioritize_review_fixes(
        agents["prioritizer"], output_dir, previous_doc_path, previous_review_path
    )
    core_tasks = [
        task_requirements(agents["product"], output_dir, previous_doc_path, previous_review_path),
        task_architecture(agents["arch"], output_dir, previous_doc_path, previous_review_path),
        task_data_api(agents["data"], output_dir, previous_doc_path, previous_review_path),
        task_security(agents["sec"], output_dir, previous_doc_path, previous_review_path),
        task_sre(agents["sre"], output_dir, previous_doc_path, previous_review_path),
        task_integrate(agents["edit"], output_dir, previous_doc_path, previous_review_path),
    ]
    critique_task = task_critique_design_doc(agents["critique"], output_dir, previous_doc_path, previous_review_path)

    logger = logging.getLogger(__name__)

    _log_prior_review_state(root, output_dir)
    try:
        _run_tasks_with_crew([agents["prioritizer"]], [prioritizer_task])
    except Exception as exc:
        plan_path = root / output_dir / "priority_plan.json"
        fallback_reason = f"Prioritizer task failed; using baseline fallback: {type(exc).__name__}: {exc}"
        write_priority_plan(plan_path, baseline_priority_plan(fallback_reason))
        logger.warning(
            "Prioritizer task failed; wrote baseline priority plan and continuing: path=%s error=%s",
            str(plan_path),
            exc,
        )
    _ensure_valid_priority_plan(root, output_dir)
    try:
        _run_tasks_with_crew(
            [
                agents["product"],
                agents["arch"],
                agents["data"],
                agents["sec"],
                agents["sre"],
                agents["edit"],
            ],
            core_tasks,
        )
    except Exception as exc:
        logger.warning("Core documentation tasks failed; continuing to QA with partial outputs: %s", exc)
        return

    try:
        _run_tasks_with_crew([agents["critique"]], [critique_task])
    except Exception as exc:
        logger.warning("Critique task failed; continuing to QA without critique output: %s", exc)
