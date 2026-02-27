from functools import lru_cache
from pathlib import Path

import yaml
from crewai import Agent
from tools.repo_reader import read_file, list_dir


@lru_cache(maxsize=1)
def _load_agents_config() -> dict[str, dict]:
    # Cache YAML to avoid re-reading on each agent construction.
    config_path = Path(__file__).resolve().parent / "config" / "agents.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Missing agents config: {config_path}")
    return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}


def _agent_config(key: str) -> dict:
    # Pulls role/goal/backstory from YAML by key.
    config = _load_agents_config()
    if key not in config:
        raise KeyError(f"Agent config not found for: {key}")
    return config[key]


def product_scope_analyst(llm=None):
    return Agent(
        **_agent_config("product_scope_analyst"),
        tools=[read_file, list_dir],
        llm=llm,
        verbose=False,
    )


def prioritizer_agent(llm=None):
    return Agent(
        **_agent_config("prioritizer_agent"),
        tools=[read_file, list_dir],
        llm=llm,
        verbose=False,
    )


def solution_architect(llm=None):
    return Agent(
        **_agent_config("solution_architect"),
        tools=[read_file, list_dir],
        llm=llm,
        verbose=False,
    )


def data_api_designer(llm=None):
    return Agent(
        **_agent_config("data_api_designer"),
        tools=[read_file, list_dir],
        llm=llm,
        verbose=False,
    )


def security_reviewer(llm=None):
    return Agent(
        **_agent_config("security_reviewer"),
        tools=[read_file, list_dir],
        llm=llm,
        verbose=False,
    )


def sre_reviewer(llm=None):
    return Agent(
        **_agent_config("sre_reviewer"),
        tools=[read_file, list_dir],
        llm=llm,
        verbose=False,
    )


def editor_integrator(llm=None):
    return Agent(
        **_agent_config("editor_integrator"),
        tools=[read_file, list_dir],
        llm=llm,
        verbose=False,
    )


def critique_architect(llm=None):
    return Agent(
        **_agent_config("critique_architect"),
        tools=[read_file, list_dir],
        llm=llm,
        verbose=False,
    )
