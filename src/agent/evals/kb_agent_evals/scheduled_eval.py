"""
Story 4 — Scheduled daily evaluation run.

Creates/updates a daily evaluation schedule that runs the dataset eval
definition against the seed dataset.  The eval definition (``eval_id``) is
created by bootstrap; the schedule triggers a new eval run every day at
06:00 UTC via ``EvaluationScheduleTask``.

The seed dataset is uploaded to the Foundry project via
``project_client.datasets.upload_file`` and referenced by ``file_id``.

Usage:
    uv run python -m kb_agent_evals.scheduled_eval
    uv run python -m kb_agent_evals.scheduled_eval --eval-id <id>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from azure.ai.projects.models import (
    AzureAIAgentTarget,
    DailyRecurrenceSchedule,
    EvaluationScheduleTask,
    RecurrenceTrigger,
    Schedule,
)

from kb_agent_evals.config import (
    get_agent_name,
    get_env_name,
    get_openai_client,
    get_project_client,
)

DATA_DIR = Path(__file__).parent.parent / "data"
DATASET_FILE = DATA_DIR / "mvp-agent-eval.jsonl"


def get_schedule_id() -> str:
    """Deterministic schedule ID scoped to environment."""
    return f"kb-agent-daily-eval-{get_env_name()}"


def _ensure_dataset(dataset_name: str, dataset_version: str = "1") -> str:
    """Upload the seed JSONL dataset if not already present. Returns dataset ID."""
    client = get_project_client()
    if not DATASET_FILE.exists():
        raise FileNotFoundError(
            f"Seed dataset not found: {DATASET_FILE}. "
            "Generate it with 'make eval-generate-dataset'."
        )

    # Try to get existing dataset first
    try:
        existing = client.datasets.get(name=dataset_name, version=dataset_version)
        existing_id = getattr(existing, "id", None)
        if existing_id:
            print(f"  Dataset already exists: {existing_id}")
            return str(existing_id)
    except Exception:
        pass  # Dataset doesn't exist yet — upload below

    dataset = client.datasets.upload_file(
        name=dataset_name,
        version=dataset_version,
        file_path=str(DATASET_FILE),
    )
    return dataset.id  # type: ignore[return-value]


def setup_scheduled_eval(eval_id: str) -> str:
    """Create or update daily evaluation schedule. Returns schedule ID.

    Parameters
    ----------
    eval_id:
        The eval definition ID returned by ``bootstrap.bootstrap()["dataset"]``
        or by ``openai_client.evals.create().id``.
    """
    client = get_project_client()
    env = get_env_name()
    agent_name = get_agent_name()
    schedule_id = get_schedule_id()

    print(f"  Environment  : {env}")
    print(f"  Agent        : {agent_name}")
    print(f"  Schedule ID  : {schedule_id}")
    print(f"  Eval ID      : {eval_id}")
    print(f"  Cadence      : Daily at 06:00 UTC")
    print()

    # Upload / ensure seed dataset
    dataset_name = f"kb-agent-eval-data-{env}"
    print(f"  Uploading seed dataset: {DATASET_FILE.name}")
    data_id = _ensure_dataset(dataset_name)
    print(f"  Dataset ID   : {data_id}")
    print()

    # Build the eval_run descriptor — targets the agent with queries from the
    # seed dataset and evaluates the responses.
    target = AzureAIAgentTarget(name=agent_name)

    eval_run: dict = {
        "eval_id": eval_id,
        "name": f"kb-agent-daily-run-{env}",
        "metadata": {"team": "kb-agent", "scenario": f"dataset-daily-{env}"},
        "data_source": {
            "type": "azure_ai_target_completions",
            "source": {
                "type": "file_id",
                "id": data_id,
            },
            "input_messages": {
                "type": "template",
                "template": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": {"type": "input_text", "text": "{{item.query}}"},
                    }
                ],
            },
            "target": target.as_dict(),
        },
    }

    schedule = Schedule(
        display_name=f"KB Agent Daily Eval ({env})",
        description=(
            f"Daily evaluation for {agent_name}: "
            f"task_adherence + coherence + violence + f1_score"
        ),
        task=EvaluationScheduleTask(eval_id=eval_id, eval_run=eval_run),
        trigger=RecurrenceTrigger(
            interval=1,
            schedule=DailyRecurrenceSchedule(hours=[6]),
        ),
        enabled=True,
    )

    result = client.beta.schedules.create_or_update(
        id=schedule_id,
        schedule=schedule,
    )

    result_id = getattr(result, "id", schedule_id)
    enabled = getattr(result, "enabled", "unknown")
    print(f"  Created/updated schedule : {result_id}")
    print(f"  Enabled                  : {enabled}")
    return str(result_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure daily evaluation schedule")
    parser.add_argument("--eval-id", help="Eval definition ID (from bootstrap)")
    args = parser.parse_args()

    print("=" * 60)
    print("  Configure Scheduled Daily Evaluation")
    print("=" * 60)
    print()

    eval_id = args.eval_id
    if not eval_id:
        print("  No --eval-id provided; running bootstrap first...")
        print()
        from kb_agent_evals.bootstrap import bootstrap
        eval_ids = bootstrap()
        eval_id = eval_ids["dataset"]
        print()

    try:
        schedule_id = setup_scheduled_eval(eval_id)
        print()
        print(f"  PASS: Daily evaluation schedule active — {schedule_id}")
    except Exception as exc:
        print(f"  ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
