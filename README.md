# DesignDocAutomator (CrewAI)

This app generates a structured design-doc pack using a CrewAI pipeline, then runs a deterministic QA harness against the outputs. Each run is captured in a timestamped output folder with its own logs and manifest for traceability.

## Folder layout

- `design-doc/inputs/` source context bundle (required inputs)
- `design-doc/templates/` templates for doc and ADRs
- `design-doc/crew/` crew definitions (agents + tasks)
- `design-doc/outputs/` generated outputs (latest + per-run artifacts)
- `design-doc/tools/` optional tools used by agents

## Quickstart

1. Create a virtual environment and install dependencies (using `uv`).

2. Run the pipeline:

```bash
uv venv
source .venv/bin/activate
uv sync
python design-doc/main.py
```

### LLM configuration

You can use a hosted OpenAI-compatible API (`OPENAI_API_KEY`) or a local OpenAI-compatible server.
`design-doc/config.py` normalizes the local base URL to `/v1` and sets defaults.

### Local LLM (OpenAI-compatible)

If you have a local OpenAI-compatible server (e.g., LM Studio) running at
`http://127.0.0.1:1234` with the model `qwen/qwen2.5-vl-7b`, set:

```bash
export LOCAL_LLM_BASE_URL=http://127.0.0.1:1234
export LOCAL_LLM_MODEL=qwen/qwen2.5-vl-7b
python design-doc/main.py
```

If no `OPENAI_API_KEY` or `OPENAI_API_BASE` is set, the app defaults to
`http://127.0.0.1:1234` with `qwen/qwen2.5-vl-7b` and will set
`OPENAI_API_BASE`/`OPENAI_API_KEY` automatically.

Before running the crew, the app performs a tool-calling preflight check
to ensure the selected model/server supports tools.

If `OPENAI_API_KEY` is not set and no local server defaults are applied,
the crew run is skipped and only the QA harness runs.

3. Inspect outputs:

- Latest copies: `design-doc/outputs/design_doc.md`
- Latest copies: `design-doc/outputs/review_report.json`
- Latest copies: `design-doc/outputs/change_summary_<timestamp>.md`
- Per-run artifacts: `design-doc/outputs/YYYY-MM-DD/run_<timestamp>_<id>/`

Each run folder includes:

- `sections/` intermediate section outputs
- `adrs/` ADR outputs
- `inputs/` copies of previous outputs used for context
- `logs/` run log files
- `run_manifest.json` metadata, model, inputs, QA status, and hashes

## Inputs

Populate these files before running for best results:

- `design-doc/inputs/context.md`
- `design-doc/inputs/constraints.yaml`
- `design-doc/inputs/repo_manifest.txt`

## Notes

- Any claims not grounded in inputs should be explicitly listed in an **Assumptions** section.
- The QA harness checks required sections, section file integrity, prior QA review mention, and placeholders.

## Troubleshooting

- `OPENAI_API_KEY is not set. Set it or use LOCAL_LLM_BASE_URL.`  
  The crew run will be skipped. Set `OPENAI_API_KEY` or configure
  `LOCAL_LLM_BASE_URL`/`LOCAL_LLM_MODEL` for a local OpenAI-compatible server.
- `RuntimeError: OPENAI_API_BASE is not set for preflight tool-calling check.`  
  Set `OPENAI_API_BASE` (or `LOCAL_LLM_BASE_URL`) so the preflight can target
  a tool-capable server.
- First run has no prior QA report input  
  This is supported. The QA harness will focus on the generated `design_doc.md`
  (required sections, section artifacts, placeholders). On reruns, prior QA
  reports are copied into the run `inputs/` folder for continuity checks.
