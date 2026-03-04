"""
Shared configuration and client factory for KB Agent evaluation scripts.

All scripts use environment variables populated by ``make dev-setup-env`` (AZD values).

Architecture overview
~~~~~~~~~~~~~~~~~~~~~
Evaluation definitions are created via the Foundry OpenAI-compatible Evals API
(``project_client.get_openai_client().evals.create``), which returns an ``eval_id``.
That ``eval_id`` is then referenced by:
  * ``ContinuousEvaluationRuleAction`` — continuous evaluation rules
  * ``EvaluationScheduleTask`` — scheduled evaluation / red-team runs

All traffic stays within the Azure Foundry project; the ``openai`` package is
used only as the wire protocol.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

if TYPE_CHECKING:
    from openai import OpenAI

load_dotenv()


def _require_env(key: str) -> str:
    """Return an environment variable or raise with a clear message."""
    val = os.environ.get(key)
    if not val:
        raise EnvironmentError(
            f"Missing required env var: {key}. Run 'make dev-setup-env' to populate."
        )
    return val.strip().strip('"')


# ---------------------------------------------------------------------------
# Environment values (filled by AZD)
# ---------------------------------------------------------------------------

def get_env_name() -> str:
    return _require_env("AZURE_ENV_NAME")


def get_deployment_name() -> str:
    """Model deployment used as judge for AI-assisted evaluators (e.g. task_adherence, coherence)."""
    return _require_env("AGENT_DEPLOYMENT_NAME")


def get_ai_services_name() -> str:
    return _require_env("AI_SERVICES_NAME")


def get_project_name() -> str:
    return _require_env("FOUNDRY_PROJECT_NAME")


def get_appinsights_name() -> str:
    return _require_env("APPINSIGHTS_NAME")


def get_agent_name() -> str:
    """Deployed agent application name."""
    return os.environ.get("AGENT_APP_NAME", "kb-agent").strip().strip('"')


def get_project_endpoint() -> str:
    """Build Foundry project endpoint from AI Services + project names."""
    ai_name = get_ai_services_name()
    proj_name = get_project_name()
    return f"https://{ai_name}.services.ai.azure.com/api/projects/{proj_name}"


# ---------------------------------------------------------------------------
# Client factories
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_credential() -> DefaultAzureCredential:
    return DefaultAzureCredential()


@lru_cache(maxsize=1)
def get_project_client() -> AIProjectClient:
    return AIProjectClient(
        endpoint=get_project_endpoint(),
        credential=get_credential(),
    )


def get_openai_client() -> OpenAI:
    """Return an OpenAI-compatible client scoped to the Foundry project.

    ``AIProjectClient.get_openai_client()`` transparently handles
    authentication and endpoint routing.  The returned client is used
    for the Foundry Evals API (``client.evals.create`` etc.).

    Despite the ``openai`` package import, all traffic stays within the
    Azure Foundry endpoint — no data goes to OpenAI.
    """
    return get_project_client().get_openai_client()
