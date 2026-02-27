"""KB Agent — entry point for both local development and Foundry deployment.

Uses the ``from_agent_framework`` adapter from the Azure AI Agent Server SDK
to run the ChatAgent as an HTTP server on port 8088.  The adapter handles:

- The Responses protocol (``/responses`` endpoint)
- SSE streaming (``agent.run_stream`` → Server-Sent Events)
- Health / readiness probes (``/liveness``, ``/readiness``)

Run locally::

    cd src/agent && uv run python main.py

The same ``main.py`` is used in the Dockerfile for Foundry hosted deployment.
"""

from __future__ import annotations

import logging
import os

from azure.ai.agentserver.agentframework import from_agent_framework

from agent_framework.observability import enable_instrumentation

# Setup observability — two paths:
#   1. APPLICATIONINSIGHTS_CONNECTION_STRING set → use Azure Monitor (traces + logs + metrics)
#   2. OTEL_EXPORTER_OTLP_ENDPOINT set → use generic OTLP exporter (e.g., Aspire Dashboard)
#   3. Neither → instrumentation enabled but no export (local dev fallback)
#
# configure_azure_monitor() sets up the OTel providers (TracerProvider, LoggerProvider,
# MeterProvider) with Azure Monitor exporters.  enable_instrumentation() then tells the
# agent framework to emit spans for tool calls, model invocations, etc.
_appinsights_conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
if _appinsights_conn:
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(connection_string=_appinsights_conn)
    enable_instrumentation()
else:
    # Fall back to the standard configure_otel_providers which reads OTEL_EXPORTER_OTLP_ENDPOINT
    from agent_framework.observability import configure_otel_providers

    configure_otel_providers()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
for _name in ("azure.core", "azure.identity", "httpx"):
    logging.getLogger(_name).setLevel(logging.WARNING)
# Suppress noisy OpenTelemetry context-detach errors caused by async context
# propagation across task boundaries during SSE streaming.  These are harmless
# (open-telemetry/opentelemetry-python#4253).
logging.getLogger("opentelemetry.context").setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the KB Agent as a Foundry hosted agent."""
    logger.info("[KB-AGENT] Starting agent server (port 8088)…")

    from agent.kb_agent import create_agent

    agent = create_agent()
    logger.info("[KB-AGENT] Agent created, starting server…")

    from_agent_framework(agent).run()


if __name__ == "__main__":
    main()
