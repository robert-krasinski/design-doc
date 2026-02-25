from pathlib import Path

from run_io import find_latest_prior_run_output_dir, prepare_previous_inputs_for_first_run


def _make_run(root: Path, rel_output_dir: str) -> Path:
    run_dir = root / rel_output_dir
    (run_dir / "inputs").mkdir(parents=True, exist_ok=True)
    return run_dir


def test_first_run_uses_latest_prior_run_folder_when_available(tmp_path: Path) -> None:
    root = tmp_path
    current_run = _make_run(root, "outputs/2026-02-25/run_20260225T195058Z_current")

    older_run = _make_run(root, "outputs/2026-02-24/run_20260224T180000Z_old")
    (older_run / "design_doc.md").write_text("older doc", encoding="utf-8")
    (older_run / "review_report.json").write_text('{"status":"FAIL","issues":[]}', encoding="utf-8")

    latest_run = _make_run(root, "outputs/2026-02-25/run_20260225T194000Z_latest")
    (latest_run / "design_doc.md").write_text("latest run doc", encoding="utf-8")
    (latest_run / "review_report.json").write_text('{"status":"PASS","issues":[]}', encoding="utf-8")

    # Distinct top-level outputs should not be used when a prior run exists.
    (root / "outputs").mkdir(parents=True, exist_ok=True)
    (root / "outputs" / "design_doc.md").write_text("top level doc", encoding="utf-8")
    (root / "outputs" / "review_report.json").write_text('{"status":"TOP","issues":[]}', encoding="utf-8")

    prev_doc_path, prev_review_path = prepare_previous_inputs_for_first_run(root, current_run)

    assert prev_doc_path == "outputs/2026-02-25/run_20260225T195058Z_current/inputs/previous_design_doc.md"
    assert prev_review_path == "outputs/2026-02-25/run_20260225T195058Z_current/inputs/previous_review_report.json"
    assert (current_run / "inputs" / "previous_design_doc.md").read_text(encoding="utf-8") == "latest run doc"
    assert (
        current_run / "inputs" / "previous_review_report.json"
    ).read_text(encoding="utf-8") == '{"status":"PASS","issues":[]}'


def test_first_run_excludes_current_run_directory_from_candidate_selection(tmp_path: Path) -> None:
    root = tmp_path
    current_run = _make_run(root, "outputs/2026-02-25/run_20260225T195058Z_current")
    (current_run / "design_doc.md").write_text("current run doc", encoding="utf-8")
    (current_run / "review_report.json").write_text('{"status":"FAIL","issues":[]}', encoding="utf-8")

    assert find_latest_prior_run_output_dir(root, exclude_run_dir=current_run) is None


def test_first_run_falls_back_to_top_level_when_no_prior_run_folders_exist(tmp_path: Path) -> None:
    root = tmp_path
    current_run = _make_run(root, "outputs/2026-02-25/run_20260225T195058Z_current")

    (root / "outputs").mkdir(parents=True, exist_ok=True)
    (root / "outputs" / "design_doc.md").write_text("top level doc", encoding="utf-8")
    (root / "outputs" / "review_report.json").write_text('{"status":"FAIL","issues":[]}', encoding="utf-8")

    prev_doc_path, prev_review_path = prepare_previous_inputs_for_first_run(root, current_run)

    assert prev_doc_path is not None
    assert prev_review_path is not None
    assert (current_run / "inputs" / "previous_design_doc.md").read_text(encoding="utf-8") == "top level doc"
    assert (
        current_run / "inputs" / "previous_review_report.json"
    ).read_text(encoding="utf-8") == '{"status":"FAIL","issues":[]}'


def test_first_run_falls_back_to_top_level_when_prior_run_has_no_artifacts(tmp_path: Path) -> None:
    root = tmp_path
    current_run = _make_run(root, "outputs/2026-02-25/run_20260225T195058Z_current")
    _make_run(root, "outputs/2026-02-24/run_20260224T180000Z_empty")

    (root / "outputs").mkdir(parents=True, exist_ok=True)
    (root / "outputs" / "design_doc.md").write_text("fallback doc", encoding="utf-8")
    (root / "outputs" / "review_report.json").write_text('{"status":"FALLBACK","issues":[]}', encoding="utf-8")

    prev_doc_path, prev_review_path = prepare_previous_inputs_for_first_run(root, current_run)

    assert prev_doc_path is not None
    assert prev_review_path is not None
    assert (current_run / "inputs" / "previous_design_doc.md").read_text(encoding="utf-8") == "fallback doc"
    assert (
        current_run / "inputs" / "previous_review_report.json"
    ).read_text(encoding="utf-8") == '{"status":"FALLBACK","issues":[]}'


def test_find_latest_prior_run_output_dir_selects_most_recent_run_across_dates(tmp_path: Path) -> None:
    root = tmp_path
    current_run = _make_run(root, "outputs/2026-02-25/run_20260225T195058Z_current")

    r1 = _make_run(root, "outputs/2026-02-24/run_20260224T100000Z_a")
    (r1 / "review_report.json").write_text("{}", encoding="utf-8")
    r2 = _make_run(root, "outputs/2026-02-25/run_20260225T101000Z_b")
    (r2 / "design_doc.md").write_text("doc", encoding="utf-8")
    r3 = _make_run(root, "outputs/2026-02-25/run_20260225T181000Z_c")
    (r3 / "review_report.json").write_text("{}", encoding="utf-8")

    selected = find_latest_prior_run_output_dir(root, exclude_run_dir=current_run)

    assert selected == "outputs/2026-02-25/run_20260225T181000Z_c"
