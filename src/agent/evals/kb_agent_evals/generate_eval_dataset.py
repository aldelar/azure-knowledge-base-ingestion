"""
Story 4 — Generate synthetic evaluation dataset using the Simulator SDK.

Uses azure.ai.evaluation.simulator.Simulator to generate multi-turn
conversations derived from KB article content. The generated dataset
serves as the seed data for scheduled daily evaluations.

Usage:
    uv run python -m kb_agent_evals.generate_eval_dataset
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from azure.ai.evaluation import AzureOpenAIModelConfiguration
from azure.ai.evaluation.simulator import Simulator

from kb_agent_evals.config import (
    get_ai_services_name,
    get_credential,
    get_env_name,
)


# ---------------------------------------------------------------------------
# KB-derived tasks — questions a user would ask the KB agent
# ---------------------------------------------------------------------------
EVAL_TASKS = [
    "What security features does Azure AI Search provide for protecting data at rest and in transit?",
    "How does role-based access control work in Azure AI Search?",
    "Explain the key concepts of Azure AI Content Understanding and its main use cases.",
    "What are the different analyzer types available in Azure AI Content Understanding?",
    "How does agentic retrieval work in Azure AI Search and what are its benefits?",
    "What is the difference between vector search and hybrid search in Azure AI Search?",
    "How can I set up network security for Azure AI Search using private endpoints?",
    "Describe the architecture of a content understanding pipeline with custom analyzers.",
    "What authentication methods are supported by Azure AI Search?",
    "How does Azure AI Search handle encryption of customer data?",
    "What are the best practices for securing an Azure AI Search service in production?",
    "Explain how agentic retrieval improves relevance compared to traditional keyword search.",
    "What image analysis capabilities does Azure AI Content Understanding support?",
    "How do I configure managed identity access between Azure AI Search and other Azure services?",
    "What are the supported document formats for Azure AI Content Understanding?",
]

# Provide KB context text for the simulator
KB_CONTEXT = """
Azure AI Search is a cloud search service that provides secure, scalable full-text
and vector search capabilities. It supports role-based access control (RBAC) via
Azure Active Directory, encryption at rest with Microsoft-managed or customer-managed
keys, network isolation via private endpoints, and IP firewall rules.

Azure AI Content Understanding is a service for analyzing documents and images.
It provides built-in and custom analyzers for extracting text, tables, key-value
pairs, and visual content from various document formats including PDF, DOCX, and images.

Agentic retrieval in Azure AI Search enables AI agents to perform sophisticated
retrieval operations using vector search, hybrid search (combining keyword and
vector), and semantic ranking to improve relevance for complex queries.
"""

OUTPUT_DIR = Path(__file__).parent.parent / "data"
OUTPUT_FILE = OUTPUT_DIR / "mvp-agent-eval.jsonl"


async def _agent_target(messages: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """
    Simulated agent target callback for dataset generation.

    The Simulator calls this to get agent responses. For dataset generation
    we use a simple echo that captures the conversation structure — the
    actual agent is exercised during scheduled evaluation runs.
    """
    latest = messages["messages"][-1]["content"] if messages.get("messages") else ""
    return {
        "messages": messages.get("messages", []) + [
            {
                "role": "assistant",
                "content": (
                    f"Based on the Azure AI documentation, here is information relevant to your question: "
                    f"This response is a placeholder generated during dataset creation. "
                    f"The actual agent will provide grounded answers during evaluation runs."
                ),
            }
        ],
        "finish_reason": "stop",
        "id": "dataset-gen",
    }


async def generate_dataset(
    num_queries: int = 15,
    max_turns: int = 2,
) -> Path:
    """Generate synthetic eval dataset and write to JSONL."""
    ai_name = get_ai_services_name()
    credential = get_credential()

    model_config = AzureOpenAIModelConfiguration(
        azure_endpoint=f"https://{ai_name}.cognitiveservices.azure.com/",
        azure_deployment="gpt-4.1",
        api_version="2025-03-01-preview",
    )

    print(f"  Model endpoint   : {model_config.azure_endpoint}")
    print(f"  Model deployment : {model_config.azure_deployment}")
    print(f"  Tasks            : {len(EVAL_TASKS)}")
    print(f"  Num queries      : {num_queries}")
    print(f"  Max turns        : {max_turns}")
    print()

    simulator = Simulator(model_config=model_config)

    results = await simulator(
        target=_agent_target,
        tasks=EVAL_TASKS,
        text=KB_CONTEXT,
        num_queries=num_queries,
        max_conversation_turns=max_turns,
        randomization_seed=42,
    )

    # Write JSONL
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        for conversation in results:
            record = dict(conversation)  # JsonLineChatProtocol → dict
            f.write(json.dumps(record, default=str) + "\n")

    print(f"  Generated {len(results)} conversations → {OUTPUT_FILE}")
    return OUTPUT_FILE


def main() -> None:
    print("=" * 60)
    print("  Generate Synthetic Evaluation Dataset")
    print("=" * 60)
    print()

    num_queries = int(os.environ.get("EVAL_NUM_QUERIES", "15"))
    max_turns = int(os.environ.get("EVAL_MAX_TURNS", "2"))

    try:
        output = asyncio.run(generate_dataset(num_queries=num_queries, max_turns=max_turns))
        print()
        print(f"  PASS: Dataset written to {output}")
    except Exception as exc:
        print(f"  ERROR: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
