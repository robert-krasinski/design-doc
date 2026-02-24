from functools import lru_cache
from pathlib import Path

import yaml
from crewai import Task


def _prior_context_note(previous_doc_path: str | None, previous_review_path: str | None) -> str:
    # Optional hint: prior artifacts may be referenced by agents.
    notes = []
    if previous_doc_path:
        notes.append(f"- Prior design doc: `{previous_doc_path}`")
    if previous_review_path:
        notes.append(f"- Prior QA report: `{previous_review_path}`")
    if not notes:
        return ""
    return "If available, use prior artifacts:\\n" + "\\n".join(notes) + "\\n"


@lru_cache(maxsize=1)
def _load_task_config() -> dict[str, dict]:
    # Cache task templates to avoid repeated disk I/O.
    config_path = Path(__file__).resolve().parent / "config" / "tasks.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Missing tasks config: {config_path}")
    return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}


def _task_config(task_key: str, output_dir: str, prior_context: str) -> dict:
    # Format the YAML description/output paths with run-specific values.
    config = _load_task_config()
    if task_key not in config:
        raise KeyError(f"Task config not found for: {task_key}")
    task = dict(config[task_key])
    task["description"] = task["description"].format(output_dir=output_dir).strip()
    task["output_file"] = task["output_file"].format(output_dir=output_dir)
    return task


def task_requirements(agent, output_dir: str, previous_doc_path: str | None = None, previous_review_path: str | None = None):
    return Task(
        **_task_config(
            "requirements",
            output_dir,
            _prior_context_note(previous_doc_path, previous_review_path),
        ),
        agent=agent,
    )


def task_architecture(agent, output_dir: str, previous_doc_path: str | None = None, previous_review_path: str | None = None):
    return Task(
        **_task_config(
            "architecture",
            output_dir,
            _prior_context_note(previous_doc_path, previous_review_path),
        ),
        agent=agent,
    )


def task_data_api(agent, output_dir: str, previous_doc_path: str | None = None, previous_review_path: str | None = None):
    return Task(
        **_task_config(
            "data_api",
            output_dir,
            _prior_context_note(previous_doc_path, previous_review_path),
        ),
        agent=agent,
    )


def task_security(agent, output_dir: str, previous_doc_path: str | None = None, previous_review_path: str | None = None):
    return Task(
        **_task_config(
            "security",
            output_dir,
            _prior_context_note(previous_doc_path, previous_review_path),
        ),
        agent=agent,
    )


def task_sre(agent, output_dir: str, previous_doc_path: str | None = None, previous_review_path: str | None = None):
    return Task(
        **_task_config(
            "sre",
            output_dir,
            _prior_context_note(previous_doc_path, previous_review_path),
        ),
        agent=agent,
    )


def task_integrate(agent, output_dir: str, previous_doc_path: str | None = None, previous_review_path: str | None = None):
    return Task(
        **_task_config(
            "integrate",
            output_dir,
            _prior_context_note(previous_doc_path, previous_review_path),
        ),
        agent=agent,
    )
