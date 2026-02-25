import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Tuple
from uuid import uuid4

from run_io import copy_run_inputs_from_output, create_run_dir, update_run_manifest, write_run_manifest


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


def _ensure_run_log_handler(run_dir: Path) -> None:
    # Attach a file handler for each rerun directory for per-run traceability.
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    existing = {
        getattr(handler, "baseFilename", None)
        for handler in root_logger.handlers
        if isinstance(handler, logging.FileHandler)
    }
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = logs_dir / f"run_{timestamp}_{uuid4().hex}.log"
    if str(log_path) in existing:
        return
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root_logger.addHandler(file_handler)


def run_top_orchestrator(
    root: Path,
    run_dir: Path,
    run_timestamp: str,
    output_dir: str,
    previous_doc_path: str | None,
    previous_review_path: str | None,
    manifest_path: Path,
    *,
    max_runs: int = 10,
    crew_enabled: bool = True,
) -> tuple[int, dict[str, Any] | None, str, str]:
    logger = logging.getLogger(__name__)
    logger.info(
        "Top orchestrator start: output_dir=%s max_runs=%s crew_enabled=%s",
        output_dir,
        max_runs,
        crew_enabled,
    )

    if not crew_enabled:
        logger.info("Crew disabled; running QA only for %s", output_dir)
        exit_code = _run_qa(output_dir)
        report_path = root / output_dir / "review_report.json"
        last_report = _load_report(report_path)
        if last_report:
            update_run_manifest(
                manifest_path, last_report.get("status", "UNKNOWN"), len(last_report.get("issues", []))
            )
        return exit_code, last_report, output_dir, run_timestamp

    try:
        preflight_tool_calling_check, run_crew = _get_crew_functions()
        preflight_tool_calling_check()
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.warning("Tool-calling preflight failed; skipping crew runs: %s", exc)
        exit_code = _run_qa(output_dir)
        report_path = root / output_dir / "review_report.json"
        last_report = _load_report(report_path)
        if last_report:
            update_run_manifest(
                manifest_path, last_report.get("status", "UNKNOWN"), len(last_report.get("issues", []))
            )
        return exit_code, last_report, output_dir, run_timestamp

    runs = 0
    last_exit = 0
    last_report: dict[str, Any] | None = None
    current_output_dir = output_dir
    current_run_dir = run_dir
    current_run_timestamp = run_timestamp
    current_manifest_path = manifest_path
    current_prev_doc_path = previous_doc_path
    current_prev_review_path = previous_review_path

    while runs < max_runs:
        _ensure_run_log_handler(current_run_dir)
        logger.info("Starting crew run %s/%s in %s", runs + 1, max_runs, current_output_dir)
        run_crew(current_output_dir, current_prev_doc_path, current_prev_review_path)
        runs += 1
        last_exit = _run_qa(current_output_dir)
        report_path = root / current_output_dir / "review_report.json"
        last_report = _load_report(report_path)
        current_status = last_report.get("status") if last_report else None
        if last_report:
            update_run_manifest(
                current_manifest_path,
                current_status or "UNKNOWN",
                len(last_report.get("issues", [])),
            )

        continue_runs = current_status == "FAIL" and runs < max_runs
        if last_report is None:
            logger.info(
                "Rerun decision: report_missing path=%s continue=%s",
                str(report_path),
                continue_runs,
            )
        else:
            logger.info(
                "Rerun decision: status=%s report=%s continue=%s",
                current_status,
                str(report_path),
                continue_runs,
            )
        if current_status != "FAIL":
            break

        if runs >= max_runs:
            break

        previous_output_dir = current_output_dir
        current_run_dir, current_run_timestamp = create_run_dir(root)
        current_output_dir = str(current_run_dir.relative_to(root))
        current_prev_doc_path, current_prev_review_path = copy_run_inputs_from_output(
            root, previous_output_dir, current_run_dir / "inputs"
        )
        current_manifest_path = write_run_manifest(
            root,
            current_run_dir,
            current_run_timestamp,
            current_output_dir,
            current_prev_doc_path,
            current_prev_review_path,
        )
        logger.info(
            "Prepared rerun directory %s with previous inputs from %s",
            current_output_dir,
            previous_output_dir,
        )

    return last_exit, last_report, current_output_dir, current_run_timestamp
