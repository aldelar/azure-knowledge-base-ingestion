"""
Story 2 — Bootstrap baseline evaluation artifacts for the hosted agent.

Creates evaluation definitions via the Foundry OpenAI-compatible Evals API
(``project_client.get_openai_client().evals.create``), which returns an
``eval_id``.  That ``eval_id`` is then referenced by:
  * ``ContinuousEvaluationRuleAction`` — continuous evaluation rules (Story 3)
  * ``EvaluationScheduleTask`` — scheduled evaluation / red-team (Stories 4 & 5)

Two eval definitions are created:
  1. **quality** — evaluates live agent traffic (continuous rule).
     Evaluators: task_adherence, coherence, violence.
  2. **daily-dataset** — evaluates agent against a seed dataset (daily schedule).
     Evaluators: task_adherence, coherence, violence, f1_score.

Note: Red-team safety evaluation is **not implemented**.  Foundry red teaming
is in preview and claims to support container agents, but the current backend
raises ``ValueError`` for hosted agents whose ``definition.model`` is ``None``.
To be revisited when the preview stabilises.

Usage:
    uv run python -m kb_agent_evals.bootstrap
"""

from __future__ import annotations

import sys
from typing import Any

from kb_agent_evals.config import get_agent_name, get_deployment_name, get_env_name, get_openai_client


# ---------------------------------------------------------------------------
# Testing criteria bundles (Foundry built-in evaluators)
#
# Each evaluator requires ``data_mapping`` to specify where query/response
# come from.  AI-assisted evaluators (task_adherence, coherence) also need
# ``initialization_parameters.deployment_name`` to select the judge model.
#
# Template variables:
#   {{item.query}}          — the "query" field from the test data row
#   {{sample.output_items}} — full agent response (tool calls + messages)
#   {{sample.output_text}}  — just the assistant text
# ---------------------------------------------------------------------------

def _quality_criteria(deployment_name: str) -> list[dict[str, Any]]:
    """Quality evaluators for continuous + scheduled quality evals."""
    return [
        {
            "type": "azure_ai_evaluator",
            "name": "task_adherence",
            "evaluator_name": "builtin.task_adherence",
            "data_mapping": {
                "query": "{{item.query}}",
                "response": "{{sample.output_items}}",
            },
            "initialization_parameters": {"deployment_name": deployment_name},
        },
        {
            "type": "azure_ai_evaluator",
            "name": "coherence",
            "evaluator_name": "builtin.coherence",
            "data_mapping": {
                "query": "{{item.query}}",
                "response": "{{sample.output_items}}",
            },
            "initialization_parameters": {"deployment_name": deployment_name},
        },
        {
            "type": "azure_ai_evaluator",
            "name": "violence",
            "evaluator_name": "builtin.violence",
            "data_mapping": {
                "query": "{{item.query}}",
                "response": "{{sample.output_items}}",
            },
        },
    ]


def _dataset_criteria(deployment_name: str) -> list[dict[str, Any]]:
    """Quality + NLP evaluators for dataset-based scheduled evals."""
    return [
        *_quality_criteria(deployment_name),
        {
            "type": "azure_ai_evaluator",
            "name": "f1_score",
            "evaluator_name": "builtin.f1_score",
            "data_mapping": {
                "query": "{{item.query}}",
                "response": "{{sample.output_text}}",
                "ground_truth": "{{item.ground_truth}}",
            },
        },
    ]


# Data source configs ---------------------------------------------------------
RESPONSES_DATA_SOURCE = {"type": "azure_ai_source", "scenario": "responses"}

DATASET_DATA_SOURCE_CONFIG = {
    "type": "custom",
    "item_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "response": {"type": "string"},
            "ground_truth": {"type": "string"},
        },
        "required": ["query", "response"],
    },
    "include_sample_schema": True,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _create_eval(
    openai_client: Any,
    name: str,
    data_source_config: dict,
    testing_criteria: list,
    *,
    metadata: dict[str, str] | None = None,
) -> str:
    """Create a Foundry eval definition via the OpenAI-compatible API. Returns ``eval_id``."""
    eval_obj = openai_client.evals.create(
        name=name,
        data_source_config=data_source_config,   # type: ignore[arg-type]
        testing_criteria=testing_criteria,         # type: ignore[arg-type]
        metadata=metadata or {},
    )
    return eval_obj.id


def bootstrap() -> dict[str, str]:
    """Create baseline eval definitions. Returns ``{logical_name: eval_id}``."""
    env = get_env_name()
    agent_name = get_agent_name()
    deployment = get_deployment_name()
    openai_client = get_openai_client()
    eval_ids: dict[str, str] = {}

    # --- 1. Quality eval (for continuous rule — Story 3) ---
    quality_criteria = _quality_criteria(deployment)
    quality_name = f"KB Agent Quality Eval ({env})"
    print(f"  Creating quality eval : {quality_name}")
    print(f"    Evaluators: {[c['name'] for c in quality_criteria]}")
    eval_ids["quality"] = _create_eval(
        openai_client, quality_name, RESPONSES_DATA_SOURCE, quality_criteria,
        metadata={"agent_name": agent_name, "scenario": "quality"},
    )
    print(f"    eval_id = {eval_ids['quality']}")
    print()

    # --- 2. Dataset eval (for daily schedule — Story 4) ---
    dataset_criteria = _dataset_criteria(deployment)
    dataset_name = f"KB Agent Dataset Eval ({env})"
    print(f"  Creating dataset eval : {dataset_name}")
    print(f"    Evaluators: {[c['name'] for c in dataset_criteria]}")
    eval_ids["dataset"] = _create_eval(
        openai_client, dataset_name, DATASET_DATA_SOURCE_CONFIG, dataset_criteria,
        metadata={"agent_name": agent_name, "scenario": "dataset"},
    )
    print(f"    eval_id = {eval_ids['dataset']}")
    print()

    return eval_ids


def main() -> None:
    print("=" * 60)
    print("  Bootstrap Baseline Evaluation Artifacts")
    print("=" * 60)
    print()
    try:
        eval_ids = bootstrap()
        print()
        for key, eid in eval_ids.items():
            print(f"  PASS: {key} → {eid}")
    except Exception as exc:
        print(f"  ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
