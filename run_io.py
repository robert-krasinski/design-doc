import hashlib
import json
import logging
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
    logger = logging.getLogger(__name__)
    prev_doc = root / "outputs" / "design_doc.md"
    prev_review = root / "outputs" / "review_report.json"
    prev_doc_path = None
    prev_review_path = None

    if prev_doc.exists():
        target = run_inputs_dir / "previous_design_doc.md"
        target.write_text(prev_doc.read_text(encoding="utf-8"), encoding="utf-8")
        prev_doc_path = str(target.relative_to(root))
        logger.info(
            "Copied previous design doc: %s -> %s",
            str(prev_doc),
            str(target),
        )
    else:
        logger.info("No previous design doc found at %s", str(prev_doc))

    if prev_review.exists():
        target = run_inputs_dir / "previous_review_report.json"
        target.write_text(prev_review.read_text(encoding="utf-8"), encoding="utf-8")
        prev_review_path = str(target.relative_to(root))
        logger.info(
            "Copied previous review report: %s -> %s",
            str(prev_review),
            str(target),
        )
    else:
        logger.info("No previous review report found at %s", str(prev_review))

    return prev_doc_path, prev_review_path


def find_latest_prior_run_output_dir(root: Path, *, exclude_run_dir: Path | None = None) -> str | None:
    # Discover the newest prior run folder with reusable artifacts.
    outputs_dir = root / "outputs"
    if not outputs_dir.exists():
        return None

    exclude_resolved = exclude_run_dir.resolve() if exclude_run_dir else None
    candidates: list[Path] = []
    for run_dir in outputs_dir.glob("**/run_*"):
        if not run_dir.is_dir():
            continue
        if exclude_resolved and run_dir.resolve() == exclude_resolved:
            continue
        if not ((run_dir / "design_doc.md").exists() or (run_dir / "review_report.json").exists()):
            continue
        candidates.append(run_dir)

    if not candidates:
        return None

    # Run directories use sortable UTC timestamps in the directory name.
    latest = sorted(candidates, key=lambda p: str(p.relative_to(root)))[-1]
    return str(latest.relative_to(root))


def prepare_previous_inputs_for_first_run(root: Path, run_dir: Path) -> tuple[str | None, str | None]:
    # Prefer the most recent prior run folder, then fall back to top-level outputs.
    logger = logging.getLogger(__name__)
    run_inputs_dir = run_dir / "inputs"

    prior_output_dir = find_latest_prior_run_output_dir(root, exclude_run_dir=run_dir)
    if prior_output_dir:
        logger.info("Found prior run candidate for first-run bootstrap: %s", prior_output_dir)
        prev_doc_path, prev_review_path = copy_run_inputs_from_output(root, prior_output_dir, run_inputs_dir)
        if prev_doc_path or prev_review_path:
            logger.info("Using prior run folder for first-run bootstrap: %s", prior_output_dir)
            return prev_doc_path, prev_review_path
        logger.info(
            "Prior run folder had no reusable artifacts; falling back to top-level outputs: %s",
            prior_output_dir,
        )
    else:
        logger.info("No prior run folders found; using top-level outputs bootstrap")

    return prepare_previous_inputs(root, run_inputs_dir)


def copy_inputs_snapshot(root: Path, run_inputs_dir: Path) -> list[str]:
    # Snapshot baseline inputs into the run folder for traceability.
    logger = logging.getLogger(__name__)
    inputs_dir = root / "inputs"
    copied: list[str] = []
    for name in ["context.md", "constraints.yaml", "repo_manifest.txt"]:
        source = inputs_dir / name
        if not source.exists():
            logger.info("Input snapshot missing at %s", str(source))
            continue
        target = run_inputs_dir / name
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        copied.append(str(target.relative_to(root)))
        logger.info("Copied input snapshot: %s -> %s", str(source), str(target))
    return copied


def copy_run_inputs_from_output(
    root: Path, source_output_dir: str, run_inputs_dir: Path
) -> tuple[str | None, str | None]:
    # Copy artifacts from a specific prior run into the new run inputs.
    logger = logging.getLogger(__name__)
    source_root = root / source_output_dir
    prev_doc = source_root / "design_doc.md"
    prev_review = source_root / "review_report.json"
    prev_doc_path = None
    prev_review_path = None

    if prev_doc.exists():
        target = run_inputs_dir / "previous_design_doc.md"
        target.write_text(prev_doc.read_text(encoding="utf-8"), encoding="utf-8")
        prev_doc_path = str(target.relative_to(root))
        logger.info(
            "Copied previous run design doc: %s -> %s",
            str(prev_doc),
            str(target),
        )
    else:
        logger.info("Previous run design doc missing at %s", str(prev_doc))

    if prev_review.exists():
        target = run_inputs_dir / "previous_review_report.json"
        target.write_text(prev_review.read_text(encoding="utf-8"), encoding="utf-8")
        prev_review_path = str(target.relative_to(root))
        logger.info(
            "Copied previous run review report: %s -> %s",
            str(prev_review),
            str(target),
        )
    else:
        logger.info("Previous run review report missing at %s", str(prev_review))

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
