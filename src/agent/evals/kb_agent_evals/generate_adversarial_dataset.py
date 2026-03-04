"""
Story 5 — Generate adversarial evaluation dataset using AdversarialSimulator.

Uses azure.ai.evaluation.simulator.AdversarialSimulator to generate
adversarial conversations for offline review and regression testing.

Usage:
    uv run python -m kb_agent_evals.generate_adversarial_dataset
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from azure.ai.evaluation.simulator import AdversarialScenario, AdversarialSimulator
from azure.identity import DefaultAzureCredential

from kb_agent_evals.config import get_credential, get_project_endpoint


OUTPUT_DIR = Path(__file__).parent.parent / "data"
OUTPUT_FILE = OUTPUT_DIR / "adversarial-baseline.jsonl"

# Scenarios aligned with KB agent use case (Q&A + conversation)
SCENARIOS = [
    AdversarialScenario.ADVERSARIAL_QA,
    AdversarialScenario.ADVERSARIAL_CONVERSATION,
]


async def _agent_target(messages: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """
    Simulated agent target callback for adversarial dataset generation.

    Returns a safe refusal response — the adversarial simulator is testing
    whether the agent can be provoked into unsafe responses.
    """
    return {
        "messages": messages.get("messages", []) + [
            {
                "role": "assistant",
                "content": (
                    "I'm a knowledge base assistant focused on Azure AI documentation. "
                    "I can only help with questions about Azure AI Search, Content Understanding, "
                    "and related topics from our knowledge base."
                ),
            }
        ],
        "finish_reason": "stop",
        "id": "adversarial-gen",
    }


async def generate_adversarial_dataset(
    max_turns: int = 3,
    max_results_per_scenario: int = 25,
) -> Path:
    """Generate adversarial dataset and write to JSONL."""
    endpoint = get_project_endpoint()
    credential = get_credential()

    print(f"  Project endpoint : {endpoint}")
    print(f"  Scenarios        : {[s.value for s in SCENARIOS]}")
    print(f"  Max turns        : {max_turns}")
    print(f"  Results/scenario : {max_results_per_scenario}")
    print()

    simulator = AdversarialSimulator(
        azure_ai_project=endpoint,
        credential=credential,
    )

    all_results = []
    for scenario in SCENARIOS:
        print(f"  Running scenario: {scenario.value}...")
        results = await simulator(
            scenario=scenario,
            target=_agent_target,
            max_conversation_turns=max_turns,
            max_simulation_results=max_results_per_scenario,
        )
        print(f"    → {len(results)} conversations generated")
        all_results.extend(results)

    # Write JSONL
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        for conversation in all_results:
            record = dict(conversation)
            f.write(json.dumps(record, default=str) + "\n")

    print()
    print(f"  Generated {len(all_results)} adversarial conversations → {OUTPUT_FILE}")
    return OUTPUT_FILE


def main() -> None:
    print("=" * 60)
    print("  Generate Adversarial Evaluation Dataset")
    print("=" * 60)
    print()

    max_turns = int(os.environ.get("ADVERSARIAL_MAX_TURNS", "3"))
    max_results = int(os.environ.get("ADVERSARIAL_MAX_RESULTS", "25"))

    try:
        output = asyncio.run(
            generate_adversarial_dataset(
                max_turns=max_turns,
                max_results_per_scenario=max_results,
            )
        )
        print()
        print(f"  PASS: Adversarial dataset written to {output}")
    except Exception as exc:
        print(f"  ERROR: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
