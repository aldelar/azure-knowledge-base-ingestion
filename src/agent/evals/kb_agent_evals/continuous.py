"""
Story 3 — Continuous evaluation rule for kb-agent.

Creates/updates an evaluation rule that automatically evaluates
live agent responses using the quality eval definition created by bootstrap.

The rule uses ``ContinuousEvaluationRuleAction`` with an ``eval_id`` obtained
from ``openai_client.evals.create()`` (via bootstrap).

Usage:
    uv run python -m kb_agent_evals.continuous          # requires bootstrap first
    uv run python -m kb_agent_evals.continuous --eval-id <id>  # provide eval_id directly
"""

from __future__ import annotations

import argparse
import sys

from azure.ai.projects.models import (
    ContinuousEvaluationRuleAction,
    EvaluationRule,
    EvaluationRuleEventType,
    EvaluationRuleFilter,
)

from kb_agent_evals.config import get_agent_name, get_env_name, get_project_client


# ---------------------------------------------------------------------------
# Sampling config by environment
# ---------------------------------------------------------------------------
MAX_HOURLY_RUNS = {
    "dev": 100,
    "prod": 100,
}


def get_rule_id() -> str:
    """Deterministic rule ID scoped to environment."""
    return f"kb-agent-continuous-{get_env_name()}"


def setup_continuous_eval(eval_id: str) -> str:
    """Create or update the continuous evaluation rule. Returns rule ID.

    Parameters
    ----------
    eval_id:
        The eval definition ID returned by ``bootstrap.bootstrap()["quality"]``
        or by ``openai_client.evals.create().id``.
    """
    client = get_project_client()
    env = get_env_name()
    agent_name = get_agent_name()
    rule_id = get_rule_id()
    max_hourly = MAX_HOURLY_RUNS.get(env, MAX_HOURLY_RUNS["dev"])

    print(f"  Environment      : {env}")
    print(f"  Agent            : {agent_name}")
    print(f"  Rule ID          : {rule_id}")
    print(f"  Eval ID          : {eval_id}")
    print(f"  Max hourly runs  : {max_hourly}")
    print()

    rule = EvaluationRule(
        display_name=f"KB Agent Continuous Eval ({env})",
        description=(
            f"Continuous evaluation for {agent_name}: "
            f"task_adherence + coherence + violence"
        ),
        action=ContinuousEvaluationRuleAction(
            eval_id=eval_id,
            max_hourly_runs=max_hourly,
        ),
        event_type=EvaluationRuleEventType.RESPONSE_COMPLETED,
        filter=EvaluationRuleFilter(agent_name=agent_name),
        enabled=True,
    )

    result = client.evaluation_rules.create_or_update(
        id=rule_id,
        evaluation_rule=rule,
    )

    result_id = getattr(result, "id", rule_id)
    enabled = getattr(result, "enabled", "unknown")
    print(f"  Created/updated rule : {result_id}")
    print(f"  Enabled              : {enabled}")
    return str(result_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure continuous evaluation rule")
    parser.add_argument("--eval-id", help="Eval definition ID (from bootstrap)")
    args = parser.parse_args()

    print("=" * 60)
    print("  Configure Continuous Evaluation Rule")
    print("=" * 60)
    print()

    eval_id = args.eval_id
    if not eval_id:
        print("  No --eval-id provided; running bootstrap first...")
        print()
        from kb_agent_evals.bootstrap import bootstrap
        eval_ids = bootstrap()
        eval_id = eval_ids["quality"]
        print()

    try:
        rule_id = setup_continuous_eval(eval_id)
        print()
        print(f"  PASS: Continuous evaluation active — {rule_id}")
    except Exception as exc:
        print(f"  ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
