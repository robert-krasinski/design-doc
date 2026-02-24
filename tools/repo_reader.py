import logging
from pathlib import Path
from typing import List

try:
    from crewai.tools import tool
except Exception:  # pragma: no cover - allows import in environments without crewai
    def tool(name=None):
        def decorator(fn):
            return fn
        return decorator


@tool("list_dir")
def list_dir(path: str) -> List[str]:
    """List files in a directory relative to the project root."""
    # Log tool usage for observability and debugging.
    logging.getLogger(__name__).info("tool_call list_dir path=%s", path)
    root = Path(__file__).resolve().parents[1]
    target = (root / path).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError("Path escapes project root")
    if not target.exists() or not target.is_dir():
        return []
    return sorted(p.name for p in target.iterdir())


@tool("read_file")
def read_file(path: str) -> str:
    """Read a file relative to the project root."""
    # Log tool usage for observability and debugging.
    logging.getLogger(__name__).info("tool_call read_file path=%s", path)
    root = Path(__file__).resolve().parents[1]
    target = (root / path).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError("Path escapes project root")
    if not target.exists() or not target.is_file():
        return ""
    return target.read_text(encoding="utf-8")
