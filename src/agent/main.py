"""KB Agent — entry point for both local development and Foundry deployment.

Uses the ``from_agent_framework`` adapter from the Azure AI Agent Server SDK
to run the ChatAgent as an HTTP server on port 8088.  The adapter handles:

- The Responses protocol (``/responses`` endpoint)
- SSE streaming (``agent.run_stream`` → Server-Sent Events)
- Health / readiness probes (``/liveness``, ``/readiness``)
- Lazy agent creation (agent is built on first request, not at import time)

Run locally::

    cd src/agent && uv run python main.py

The same ``main.py`` is used in the Dockerfile for Foundry hosted deployment.
"""

from __future__ import annotations

import logging

from azure.ai.agentserver.agentframework import from_agent_framework  # pyright: ignore[reportUnknownVariableType]

from agent_framework.observability import configure_otel_providers

# Setup observability — reads environment variables automatically:
#   - OTEL_EXPORTER_OTLP_ENDPOINT (for Aspire Dashboard/OTLP)
#   - APPLICATIONINSIGHTS_CONNECTION_STRING (for Azure Monitor)
#   - OTEL_SERVICE_NAME (defaults to agent_framework)
configure_otel_providers()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
for _name in ("azure.core", "azure.identity", "httpx"):
    logging.getLogger(_name).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def main():
    """Run the KB Agent as a Foundry hosted agent.

    The ``from_agent_framework`` adapter starts the HTTP server
    and wraps the ChatAgent with the Responses protocol.
    """
    logger.info("[KB-AGENT] Starting agent server (port 8088)...")
    from agent.kb_agent import create_agent  # triggers config.py validation
    agent = create_agent()
    from_agent_framework(agent).run()


if __name__ == "__main__":
    main()
