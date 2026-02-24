import os

from crewai import Crew, LLM, Process
from openai import OpenAI

from crew.agents import (
    data_api_designer,
    editor_integrator,
    product_scope_analyst,
    security_reviewer,
    solution_architect,
    sre_reviewer,
)
from crew.tasks import (
    task_architecture,
    task_data_api,
    task_integrate,
    task_requirements,
    task_security,
    task_sre,
)


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


def run_crew(output_dir: str, previous_doc_path: str | None, previous_review_path: str | None) -> None:
    # Build agents and tasks from config-driven definitions.
    llm = build_llm()
    agents = {
        "product": product_scope_analyst(llm=llm),
        "arch": solution_architect(llm=llm),
        "data": data_api_designer(llm=llm),
        "sec": security_reviewer(llm=llm),
        "sre": sre_reviewer(llm=llm),
        "edit": editor_integrator(llm=llm),
    }

    tasks = [
        task_requirements(agents["product"], output_dir, previous_doc_path, previous_review_path),
        task_architecture(agents["arch"], output_dir, previous_doc_path, previous_review_path),
        task_data_api(agents["data"], output_dir, previous_doc_path, previous_review_path),
        task_security(agents["sec"], output_dir, previous_doc_path, previous_review_path),
        task_sre(agents["sre"], output_dir, previous_doc_path, previous_review_path),
        task_integrate(agents["edit"], output_dir, previous_doc_path, previous_review_path),
    ]

    crew = Crew(
        agents=list(agents.values()),
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
        tracing=True,
    )

    crew.kickoff()
