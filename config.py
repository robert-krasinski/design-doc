import os


# Centralized environment defaults for local OpenAI-compatible LLMs.


def configure_llm_defaults() -> None:
    # Prefer explicit env, otherwise assume a local server.
    local_base = os.environ.get("LOCAL_LLM_BASE_URL")
    if not local_base and not os.environ.get("OPENAI_API_KEY") and not os.environ.get("OPENAI_API_BASE"):
        local_base = "http://127.0.0.1:1234"
    local_model = os.environ.get("LOCAL_LLM_MODEL", "qwen/qwen2.5-vl-7b")

    if local_base:
        # Normalize to OpenAI-compatible base URL.
        base = local_base.rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        os.environ.setdefault("OPENAI_API_BASE", base)
        os.environ.setdefault("OPENAI_API_KEY", "local")
        os.environ.setdefault("OPENAI_MODEL_NAME", local_model)
