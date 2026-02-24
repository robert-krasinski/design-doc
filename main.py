import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))

from config import configure_llm_defaults
from diffs import summarize_changes
from run_io import (
    create_run_dir,
    prepare_previous_inputs,
    update_run_manifest,
    write_run_manifest,
)
from orchestrator import preflight_tool_calling_check, run_crew


def setup_logging(run_dir: Path) -> str:
    # One log file per run, with a unique ID for correlation.
    run_id = uuid4().hex
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = run_dir / "logs" / f"run_{timestamp}_{run_id}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()],
    )
    return str(log_path)


def run_qa(output_dir: str) -> int:
    # QA is deterministic and must run even if Crew fails.
    from qa import main as qa_main

    return qa_main(output_dir)


if __name__ == "__main__":
    configure_llm_defaults()
    run_dir, run_timestamp = create_run_dir(root)
    log_path = setup_logging(run_dir)
    logging.getLogger(__name__).info("Run log: %s", log_path)
    output_dir = str(run_dir.relative_to(root))

    prev_doc_path, prev_review_path = prepare_previous_inputs(root, run_dir / "inputs")
    previous_doc_text = None
    if prev_doc_path:
        prev_doc_abs = root / prev_doc_path
        if prev_doc_abs.exists():
            previous_doc_text = prev_doc_abs.read_text(encoding="utf-8")

    manifest_path = write_run_manifest(
        root, run_dir, run_timestamp, output_dir, prev_doc_path, prev_review_path
    )

    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set. Set it or use LOCAL_LLM_BASE_URL.")
    else:
        preflight_tool_calling_check()
        run_crew(output_dir, prev_doc_path, prev_review_path)

    exit_code = run_qa(output_dir)
    qa_report_path = root / output_dir / "review_report.json"
    if qa_report_path.exists():
        qa_data = json.loads(qa_report_path.read_text(encoding="utf-8"))
        update_run_manifest(
            manifest_path, qa_data.get("status", "UNKNOWN"), len(qa_data.get("issues", []))
        )

    latest_design_doc = root / "outputs" / "design_doc.md"
    latest_review = root / "outputs" / "review_report.json"
    dated_review = root / "outputs" / f"review_report_{run_timestamp}.json"
    run_design_doc = root / output_dir / "design_doc.md"
    run_review = root / output_dir / "review_report.json"

    if run_design_doc.exists():
        current_doc_text = run_design_doc.read_text(encoding="utf-8")
        change_summary = summarize_changes(previous_doc_text, current_doc_text)
        run_change_summary = root / output_dir / "change_summary.md"
        dated_change_summary = root / "outputs" / f"change_summary_{run_timestamp}.md"
        run_change_summary.write_text(change_summary, encoding="utf-8")
        dated_change_summary.write_text(change_summary, encoding="utf-8")
        latest_design_doc.write_text(current_doc_text, encoding="utf-8")

    if run_review.exists():
        review_text = run_review.read_text(encoding="utf-8")
        latest_review.write_text(review_text, encoding="utf-8")
        dated_review.write_text(review_text, encoding="utf-8")

    raise SystemExit(exit_code)
