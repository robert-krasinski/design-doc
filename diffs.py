import difflib


def split_sections(markdown: str) -> dict[str, str]:
    # Simple section splitter keyed by H2 headings for change summaries.
    sections: dict[str, str] = {}
    current = None
    buffer: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buffer).strip()
            current = line[3:].strip()
            buffer = []
        else:
            buffer.append(line)
    if current is not None:
        sections[current] = "\n".join(buffer).strip()
    return sections


def summarize_changes(previous: str | None, current: str) -> str:
    # Produce a lightweight, human-readable summary + diff stats.
    if not previous:
        return "## Change Summary (vs previous run)\n- No prior design doc found. First run.\n"

    prev_sections = split_sections(previous)
    curr_sections = split_sections(current)

    added = [s for s in curr_sections.keys() if s not in prev_sections]
    removed = [s for s in prev_sections.keys() if s not in curr_sections]
    modified = [
        s
        for s in curr_sections.keys()
        if s in prev_sections and curr_sections[s].strip() != prev_sections[s].strip()
    ]

    diff_lines = list(
        difflib.unified_diff(
            previous.splitlines(),
            current.splitlines(),
            lineterm="",
        )
    )
    stats = f"{sum(1 for l in diff_lines if l.startswith('+') and not l.startswith('+++'))} additions, " \
            f"{sum(1 for l in diff_lines if l.startswith('-') and not l.startswith('---'))} deletions"

    lines = ["## Change Summary (vs previous run)"]
    if added:
        lines.append(f"- Added sections: {', '.join(added)}")
    if removed:
        lines.append(f"- Removed sections: {', '.join(removed)}")
    if modified:
        lines.append(f"- Modified sections: {', '.join(modified)}")
    if not added and not removed and not modified:
        lines.append("- No section-level changes detected.")
    lines.append(f"- Diff stats: {stats}")
    return "\n".join(lines) + "\n"
