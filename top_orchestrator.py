import json
import logging
from pathlib import Path
from typing import Any, Callable, Tuple


def _load_report(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _get_crew_functions() -> Tuple[Callable[[], None], Callable[[str, str | None, str | None], None]]:
    from orchestrator import preflight_tool_calling_check, run_crew

    return preflight_tool_calling_check, run_crew


def _run_qa(output_dir: str) -> int:
    # QA is deterministic and must run even if Crew fails.
    from qa import main as qa_main

    return qa_main(output_dir)


def run_top_orchestrator(
    output_dir: str,
    previous_doc_path: str | None,
    previous_review_path: str | None,
    *,
    max_runs: int = 10,
    crew_enabled: bool = True,
) -> tuple[int, dict[str, Any] | None]:
    root = Path(__file__).resolve().parent
    logger = logging.getLogger(__name__)

    if not crew_enabled:
        exit_code = _run_qa(output_dir)
        return exit_code, _load_report(root / output_dir / "review_report.json")

    try:
        preflight_tool_calling_check, run_crew = _get_crew_functions()
        preflight_tool_calling_check()
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.warning("Tool-calling preflight failed; skipping crew runs: %s", exc)
        exit_code = _run_qa(output_dir)
        return exit_code, _load_report(root / output_dir / "review_report.json")

    runs = 0
    last_exit = 0
    last_report: dict[str, Any] | None = None

    while runs < max_runs:
        run_crew(output_dir, previous_doc_path, previous_review_path)
        runs += 1
        last_exit = _run_qa(output_dir)
        last_report = _load_report(root / output_dir / "review_report.json")
        current_status = last_report.get("status") if last_report else None

        if current_status != "FAIL":
            break

    return last_exit, last_report
