import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def ensure_paths(run_dir: Path) -> None:
    # Run-scoped folders keep artifacts isolated for auditability.
    (run_dir / "sections").mkdir(parents=True, exist_ok=True)
    (run_dir / "adrs").mkdir(parents=True, exist_ok=True)
    (run_dir / "inputs").mkdir(parents=True, exist_ok=True)
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)


def create_run_dir(root: Path) -> tuple[Path, str]:
    # Use date-based folders with run-specific IDs for easy navigation.
    date_dir = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    run_id = uuid4().hex
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = root / "outputs" / date_dir / f"run_{timestamp}_{run_id}"
    ensure_paths(run_dir)
    return run_dir, timestamp


def prepare_previous_inputs(root: Path, run_inputs_dir: Path) -> tuple[str | None, str | None]:
    # Copy latest outputs into the run folder so agents can reference them.
    prev_doc = root / "outputs" / "design_doc.md"
    prev_review = root / "outputs" / "review_report.json"
    prev_doc_path = None
    prev_review_path = None

    if prev_doc.exists():
        target = run_inputs_dir / "previous_design_doc.md"
        target.write_text(prev_doc.read_text(encoding="utf-8"), encoding="utf-8")
        prev_doc_path = str(target.relative_to(root))

    if prev_review.exists():
        target = run_inputs_dir / "previous_review_report.json"
        target.write_text(prev_review.read_text(encoding="utf-8"), encoding="utf-8")
        prev_review_path = str(target.relative_to(root))

    return prev_doc_path, prev_review_path


def _hash_file(path: Path) -> str:
    # Content hash supports reproducibility tracking in the manifest.
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def write_run_manifest(
    root: Path,
    run_dir: Path,
    run_timestamp: str,
    output_dir: str,
    previous_doc_path: str | None,
    previous_review_path: str | None,
) -> Path:
    # Persist run metadata for traceability and debugging.
    inputs_dir = root / "inputs"
    model = os.environ.get("LOCAL_LLM_MODEL", "qwen/qwen2.5-vl-7b")
    base_url = os.environ.get("OPENAI_API_BASE") or os.environ.get("OPENAI_BASE_URL")

    inputs = []
    for name in ["context.md", "constraints.yaml", "repo_manifest.txt"]:
        path = inputs_dir / name
        if path.exists():
            inputs.append({"path": str(path.relative_to(root)), "sha256": _hash_file(path)})

    manifest = {
        "timestamp": run_timestamp,
        "run_dir": str(run_dir.relative_to(root)),
        "output_dir": output_dir,
        "model": model,
        "base_url": base_url,
        "inputs": inputs,
        "previous_design_doc": previous_doc_path,
        "previous_review_report": previous_review_path,
        "qa_status": None,
        "qa_issues": None,
    }

    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def update_run_manifest(manifest_path: Path, qa_status: str, qa_issues: int) -> None:
    # Update after QA so the manifest reflects final run status.
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["qa_status"] = qa_status
    data["qa_issues"] = qa_issues
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
