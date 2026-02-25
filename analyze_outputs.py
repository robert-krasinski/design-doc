import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import qa


SECTION_FILE_HEADERS = {
    "requirements.md": ["Problem Statement", "Goals", "Non-Goals", "Assumptions"],
    "architecture.md": ["Architecture Overview", "Components", "Trade-offs", "Diagram", "Assumptions"],
    "data_api.md": [
        "Data Design",
        "Entities",
        "Data Flows",
        "Storage/Retention",
        "API / Interface Contracts",
        "Assumptions",
    ],
    "security.md": ["Risks & Mitigations", "Security Controls", "Assumptions"],
    "nfrs_ops.md": ["Non-Functional Requirements", "Observability", "Ops Runbooks", "Assumptions"],
}


@dataclass
class RunRecord:
    run_id: str
    run_dir: Path
    output_dir: str
    timestamp: str
    manifest: dict[str, Any]
    qa_status: str | None
    qa_issue_count: int | None
    qa_issue_sections: set[str]
    design_doc_exists: bool
    design_doc_text: str
    design_doc_hash: str | None
    review_report_hash: str | None
    previous_design_doc_hash: str | None
    previous_review_report_hash: str | None
    required_sections_total: int
    required_sections_completed: int
    required_sections_completion_pct: float
    section_artifacts_total: int
    section_artifacts_present: int
    section_artifacts_valid: int
    section_artifacts_completion_pct: float
    parent_run_id: str | None = None
    sequence_id: str | None = None
    sequence_index: int | None = None


def _sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_read_text(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _normalize_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")).strip()


def _count_required_sections(doc_text: str) -> tuple[int, int, float]:
    total = len(qa.REQUIRED_SECTIONS)
    if not doc_text:
        return total, 0, 0.0
    completed = 0
    for section in qa.REQUIRED_SECTIONS:
        if f"## {section}" in doc_text:
            completed += 1
    pct = (completed / total * 100.0) if total else 0.0
    return total, completed, round(pct, 1)


def _evaluate_section_artifacts(run_dir: Path) -> tuple[int, int, int, float]:
    sections_dir = run_dir / "sections"
    total = len(SECTION_FILE_HEADERS)
    present = 0
    valid = 0
    for filename, headers in SECTION_FILE_HEADERS.items():
        path = sections_dir / filename
        if not path.exists():
            continue
        present += 1
        content = path.read_text(encoding="utf-8")
        if all(f"## {header}" in content for header in headers):
            valid += 1
    pct = (valid / total * 100.0) if total else 0.0
    return total, present, valid, round(pct, 1)


def _parse_review_report(run_dir: Path) -> tuple[str | None, int | None, set[str], str | None]:
    report_path = run_dir / "review_report.json"
    raw_hash = _sha256_file(report_path)
    data = _load_json(report_path)
    if data is None:
        return ("MISSING" if report_path.exists() else None), None, set(), raw_hash
    status = data.get("status")
    issues = data.get("issues", [])
    if not isinstance(issues, list):
        issues = []
    sections: set[str] = set()
    for issue in issues:
        if isinstance(issue, dict):
            section = issue.get("section")
            if isinstance(section, str):
                sections.add(section)
    return (status if isinstance(status, str) else None), len(issues), sections, raw_hash


def discover_runs(outputs_dir: Path) -> list[RunRecord]:
    runs: list[RunRecord] = []
    for manifest_path in sorted(outputs_dir.glob("**/run_*/run_manifest.json")):
        run_dir = manifest_path.parent
        manifest = _load_json(manifest_path)
        if manifest is None:
            continue
        run_id = run_dir.name
        output_dir = manifest.get("output_dir") if isinstance(manifest.get("output_dir"), str) else str(run_dir)
        timestamp = manifest.get("timestamp") if isinstance(manifest.get("timestamp"), str) else run_id

        doc_path = run_dir / "design_doc.md"
        doc_text = _safe_read_text(doc_path)
        req_total, req_done, req_pct = _count_required_sections(doc_text)
        art_total, art_present, art_valid, art_pct = _evaluate_section_artifacts(run_dir)
        qa_status, qa_issue_count, qa_issue_sections, review_hash = _parse_review_report(run_dir)

        runs.append(
            RunRecord(
                run_id=run_id,
                run_dir=run_dir,
                output_dir=output_dir,
                timestamp=timestamp,
                manifest=manifest,
                qa_status=qa_status,
                qa_issue_count=qa_issue_count,
                qa_issue_sections=qa_issue_sections,
                design_doc_exists=doc_path.exists(),
                design_doc_text=doc_text,
                design_doc_hash=_sha256_file(doc_path),
                review_report_hash=review_hash,
                previous_design_doc_hash=_sha256_file(run_dir / "inputs" / "previous_design_doc.md"),
                previous_review_report_hash=_sha256_file(run_dir / "inputs" / "previous_review_report.json"),
                required_sections_total=req_total,
                required_sections_completed=req_done,
                required_sections_completion_pct=req_pct,
                section_artifacts_total=art_total,
                section_artifacts_present=art_present,
                section_artifacts_valid=art_valid,
                section_artifacts_completion_pct=art_pct,
            )
        )
    runs.sort(key=lambda r: (r.timestamp, r.run_id))
    return runs


def reconstruct_lineage(runs: list[RunRecord]) -> None:
    by_doc_hash: dict[str, list[RunRecord]] = {}
    by_report_hash: dict[str, list[RunRecord]] = {}
    for run in runs:
        if run.design_doc_hash:
            by_doc_hash.setdefault(run.design_doc_hash, []).append(run)
        if run.review_report_hash:
            by_report_hash.setdefault(run.review_report_hash, []).append(run)

    for run in runs:
        parent_candidates: list[RunRecord] = []
        if run.previous_design_doc_hash:
            parent_candidates.extend(by_doc_hash.get(run.previous_design_doc_hash, []))
        if not parent_candidates and run.previous_review_report_hash:
            parent_candidates.extend(by_report_hash.get(run.previous_review_report_hash, []))
        parent_candidates = [c for c in parent_candidates if c.run_id != run.run_id and c.timestamp < run.timestamp]
        if not parent_candidates:
            continue
        parent_candidates.sort(key=lambda r: (r.timestamp, r.run_id))
        run.parent_run_id = parent_candidates[-1].run_id


def assign_sequences(runs: list[RunRecord]) -> list[list[RunRecord]]:
    by_id = {r.run_id: r for r in runs}
    children: dict[str, list[RunRecord]] = {}
    roots: list[RunRecord] = []
    for run in runs:
        if run.parent_run_id and run.parent_run_id in by_id:
            children.setdefault(run.parent_run_id, []).append(run)
        else:
            roots.append(run)
    for vals in children.values():
        vals.sort(key=lambda r: (r.timestamp, r.run_id))
    roots.sort(key=lambda r: (r.timestamp, r.run_id))

    visited: set[str] = set()
    sequences: list[list[RunRecord]] = []
    seq_num = 0

    for root in roots:
        if root.run_id in visited:
            continue
        seq_num += 1
        seq_id = f"seq_{root.run_dir.parent.name}_{seq_num:03d}"
        queue = [root]
        seq_runs: list[RunRecord] = []
        while queue:
            current = queue.pop(0)
            if current.run_id in visited:
                continue
            visited.add(current.run_id)
            seq_runs.append(current)
            queue.extend(children.get(current.run_id, []))
        seq_runs.sort(key=lambda r: (r.timestamp, r.run_id))
        for idx, run in enumerate(seq_runs, start=1):
            run.sequence_id = seq_id
            run.sequence_index = idx
        sequences.append(seq_runs)

    orphaned = [r for r in runs if r.run_id not in visited]
    for run in orphaned:
        seq_num += 1
        run.sequence_id = f"seq_{run.run_dir.parent.name}_{seq_num:03d}"
        run.sequence_index = 1
        sequences.append([run])
    return sequences


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _remap_minus1_to_1_to_0_to_1(value: float) -> float:
    return (value + 1.0) / 2.0


def _doc_similarity(a: str, b: str) -> float | None:
    if not a or not b:
        return None
    return round(SequenceMatcher(None, _normalize_text(a), _normalize_text(b)).ratio(), 4)


def compute_run_metrics(runs: list[RunRecord], convergence_threshold: float = 0.75) -> list[dict[str, Any]]:
    by_id = {r.run_id: r for r in runs}
    metrics: list[dict[str, Any]] = []
    for run in runs:
        parent = by_id.get(run.parent_run_id) if run.parent_run_id else None

        resolved = introduced = unchanged = None
        issue_jaccard = None
        qa_issue_delta = None
        completion_delta = None
        similarity = None
        convergence_score = None
        convergence_label = "baseline" if parent is None else "mixed"

        if parent is not None:
            parent_issues = parent.qa_issue_sections
            current_issues = run.qa_issue_sections
            resolved = len(parent_issues - current_issues)
            introduced = len(current_issues - parent_issues)
            unchanged = len(parent_issues & current_issues)
            union = len(parent_issues | current_issues)
            issue_jaccard = round((unchanged / union) if union else 0.0, 4)
            similarity = _doc_similarity(parent.design_doc_text, run.design_doc_text)
            completion_delta = round(
                run.required_sections_completion_pct - parent.required_sections_completion_pct,
                1,
            )
            if parent.qa_issue_count is not None and run.qa_issue_count is not None:
                qa_issue_delta = parent.qa_issue_count - run.qa_issue_count

            quality_norm = 0.5
            if parent.qa_issue_count is not None and run.qa_issue_count is not None:
                raw = (parent.qa_issue_count - run.qa_issue_count) / max(parent.qa_issue_count, 1)
                quality_norm = _remap_minus1_to_1_to_0_to_1(_clamp(raw, -1.0, 1.0))
            completion_norm = 0.5
            raw_completion = completion_delta / 100.0 if completion_delta is not None else 0.0
            completion_norm = _remap_minus1_to_1_to_0_to_1(_clamp(raw_completion, -1.0, 1.0))
            stability_score = similarity if similarity is not None else 0.0
            if introduced is None or run.qa_issue_count is None:
                regression_penalty = 0.5
            else:
                denom = max((run.qa_issue_count or 0) + introduced, 1)
                regression_penalty = 1.0 - min(introduced / denom, 1.0)

            convergence_score = round(
                0.40 * quality_norm
                + 0.30 * completion_norm
                + 0.20 * stability_score
                + 0.10 * regression_penalty,
                4,
            )
            if convergence_score >= convergence_threshold:
                convergence_label = "converging"
            elif convergence_score < 0.45:
                convergence_label = "regressing"
            else:
                convergence_label = "mixed"

        metrics.append(
            {
                "run_id": run.run_id,
                "output_dir": run.output_dir,
                "timestamp": run.timestamp,
                "sequence_id": run.sequence_id,
                "sequence_index": run.sequence_index,
                "parent_run_id": run.parent_run_id,
                "qa_status": run.qa_status,
                "qa_issue_count": run.qa_issue_count,
                "qa_issue_sections": sorted(run.qa_issue_sections),
                "required_sections_total": run.required_sections_total,
                "required_sections_completed": run.required_sections_completed,
                "required_sections_completion_pct": run.required_sections_completion_pct,
                "section_artifacts_total": run.section_artifacts_total,
                "section_artifacts_present": run.section_artifacts_present,
                "section_artifacts_valid": run.section_artifacts_valid,
                "section_artifacts_completion_pct": run.section_artifacts_completion_pct,
                "resolved_issues_vs_parent": resolved,
                "introduced_issues_vs_parent": introduced,
                "unchanged_issues_vs_parent": unchanged,
                "issue_jaccard_vs_parent": issue_jaccard,
                "doc_similarity_vs_parent": similarity,
                "completion_delta_pct_vs_parent": completion_delta,
                "qa_issue_delta_vs_parent": qa_issue_delta,
                "convergence_score": convergence_score,
                "convergence_label": convergence_label,
            }
        )
    return metrics


def _sign(value: int) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def summarize_sequences(
    sequences: list[list[RunRecord]],
    run_metrics: list[dict[str, Any]],
    *,
    plateau_window: int = 2,
) -> list[dict[str, Any]]:
    metric_by_run = {m["run_id"]: m for m in run_metrics}
    summaries: list[dict[str, Any]] = []
    for seq_runs in sequences:
        seq_runs = sorted(seq_runs, key=lambda r: (r.timestamp, r.run_id))
        ids = [r.run_id for r in seq_runs]
        metrics = [metric_by_run[r.run_id] for r in seq_runs]
        qa_counts = [m["qa_issue_count"] for m in metrics if m["qa_issue_count"] is not None]
        completion_pcts = [m["required_sections_completion_pct"] for m in metrics]
        final = metrics[-1]

        oscillation = False
        deltas = []
        prev_count = None
        for m in metrics:
            count = m["qa_issue_count"]
            if count is None:
                continue
            if prev_count is not None:
                deltas.append(count - prev_count)
            prev_count = count
        last_nonzero_sign = 0
        for delta in deltas:
            s = _sign(delta)
            if s == 0:
                continue
            if last_nonzero_sign and s != last_nonzero_sign:
                oscillation = True
                break
            last_nonzero_sign = s

        converged = False
        reason = "No PASS and no stable plateau with improvement"
        if final["qa_status"] == "PASS":
            converged = True
            reason = "Final run passed QA"
        elif len(metrics) >= plateau_window and plateau_window >= 2:
            tail = metrics[-plateau_window:]
            counts = [m["qa_issue_count"] for m in tail]
            same_count = all(c is not None and c == counts[0] for c in counts)
            no_new_issues = all((m["introduced_issues_vs_parent"] in (0, None)) for m in tail[1:])
            stable_docs = all(
                (m["doc_similarity_vs_parent"] is not None and m["doc_similarity_vs_parent"] >= 0.95) for m in tail[1:]
            )
            stable_completion = all(
                (m["completion_delta_pct_vs_parent"] is not None and abs(m["completion_delta_pct_vs_parent"]) <= 1.0)
                for m in tail[1:]
            )
            if same_count and no_new_issues and stable_docs and stable_completion:
                converged = True
                reason = "Stable plateau across recent runs"

        best_metric = max(
            metrics,
            key=lambda m: (
                1 if m["qa_status"] == "PASS" else 0,
                -(m["qa_issue_count"] if m["qa_issue_count"] is not None else 10**9),
                m["required_sections_completion_pct"] or 0.0,
                m["timestamp"],
            ),
        )

        summaries.append(
            {
                "sequence_id": seq_runs[0].sequence_id,
                "run_ids": ids,
                "length": len(ids),
                "start_timestamp": seq_runs[0].timestamp,
                "end_timestamp": seq_runs[-1].timestamp,
                "final_qa_status": final["qa_status"],
                "best_qa_issue_count": best_metric["qa_issue_count"],
                "final_qa_issue_count": final["qa_issue_count"],
                "best_completion_pct": best_metric["required_sections_completion_pct"],
                "final_completion_pct": final["required_sections_completion_pct"],
                "oscillation_detected": oscillation,
                "converged": converged,
                "convergence_reason": reason,
            }
        )
    return summaries


def evaluate_outputs(
    outputs_dir: Path,
    *,
    convergence_threshold: float = 0.75,
    plateau_window: int = 2,
) -> dict[str, Any]:
    runs = discover_runs(outputs_dir)
    reconstruct_lineage(runs)
    sequences = assign_sequences(runs)
    run_metrics = compute_run_metrics(runs, convergence_threshold=convergence_threshold)
    sequence_summaries = summarize_sequences(sequences, run_metrics, plateau_window=plateau_window)
    return {
        "outputs_dir": str(outputs_dir),
        "run_count": len(runs),
        "sequence_count": len(sequences),
        "run_metrics": run_metrics,
        "sequence_summaries": sequence_summaries,
    }


def _resolve_outputs_dir(arg_path: str | None, date_filter: str | None) -> Path:
    if arg_path:
        base = Path(arg_path)
    else:
        base = Path(__file__).resolve().parent / "outputs"
    if date_filter:
        base = base / date_filter
    return base


def _print_table(result: dict[str, Any]) -> None:
    rows = result["run_metrics"]
    if not rows:
        print("No runs found.")
        return
    headers = ["run_id", "seq", "idx", "qa", "issues", "completion%", "delta", "conv"]
    data_rows = []
    for row in rows:
        data_rows.append(
            [
                row["run_id"],
                row.get("sequence_id") or "",
                str(row.get("sequence_index") or ""),
                row.get("qa_status") or "",
                "" if row.get("qa_issue_count") is None else str(row["qa_issue_count"]),
                f'{row.get("required_sections_completion_pct", 0.0):.1f}',
                ""
                if row.get("qa_issue_delta_vs_parent") is None
                else f'{row["qa_issue_delta_vs_parent"]:+d}',
                row.get("convergence_label") or "",
            ]
        )
    widths = [len(h) for h in headers]
    for data_row in data_rows:
        for i, val in enumerate(data_row):
            widths[i] = max(widths[i], len(val))
    print("  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    print("  ".join("-" * widths[i] for i in range(len(headers))))
    for data_row in data_rows:
        print("  ".join(data_row[i].ljust(widths[i]) for i in range(len(headers))))
    print()
    print("Sequence summaries:")
    for seq in result["sequence_summaries"]:
        print(
            f'- {seq["sequence_id"]}: runs={seq["length"]} final={seq["final_qa_status"]} '
            f'best_issues={seq["best_qa_issue_count"]} final_issues={seq["final_qa_issue_count"]} '
            f'best_completion={seq["best_completion_pct"]:.1f}% oscillation={seq["oscillation_detected"]} '
            f'converged={seq["converged"]}'
        )


def _print_csv(result: dict[str, Any]) -> None:
    fieldnames = [
        "run_id",
        "sequence_id",
        "sequence_index",
        "timestamp",
        "parent_run_id",
        "qa_status",
        "qa_issue_count",
        "required_sections_completion_pct",
        "section_artifacts_completion_pct",
        "qa_issue_delta_vs_parent",
        "completion_delta_pct_vs_parent",
        "doc_similarity_vs_parent",
        "convergence_score",
        "convergence_label",
    ]
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
    writer.writeheader()
    for row in result["run_metrics"]:
        writer.writerow({k: row.get(k) for k in fieldnames})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze design-doc output runs for convergence and completion.")
    parser.add_argument("--outputs-dir", help="Base outputs directory (default: design-doc/outputs next to this script)")
    parser.add_argument("--date", help="Optional date folder filter (YYYY-MM-DD)")
    parser.add_argument("--format", choices=["table", "json", "csv"], default="table")
    parser.add_argument("--write", help="Optional path to write JSON results")
    parser.add_argument("--plateau-window", type=int, default=2)
    parser.add_argument("--convergence-threshold", type=float, default=0.75)
    args = parser.parse_args(argv)

    outputs_dir = _resolve_outputs_dir(args.outputs_dir, args.date)
    result = evaluate_outputs(
        outputs_dir,
        convergence_threshold=args.convergence_threshold,
        plateau_window=args.plateau_window,
    )

    if args.write:
        out_path = Path(args.write)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    if args.format == "json":
        print(json.dumps(result, indent=2))
    elif args.format == "csv":
        _print_csv(result)
    else:
        _print_table(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
