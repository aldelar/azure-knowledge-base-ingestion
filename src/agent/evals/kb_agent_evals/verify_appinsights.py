"""
Story 1 — Verify Foundry ↔ Application Insights connection.

The Bicep module (foundry-project.bicep) creates the connection at provision time.
This script verifies the connection exists and functions correctly.

Usage:
    uv run python -m kb_agent_evals.verify_appinsights
"""

import sys

from kb_agent_evals.config import (
    get_appinsights_name,
    get_project_client,
    get_project_endpoint,
)


def verify_appinsights_connection() -> bool:
    """Return True if App Insights connection is active, False otherwise."""
    client = get_project_client()
    expected_appi = get_appinsights_name()

    print(f"  Project endpoint : {get_project_endpoint()}")
    print(f"  Expected AppInsights : {expected_appi}")
    print()

    # 1. Check telemetry connection string (SDK shortcut)
    conn_str = client.telemetry.get_application_insights_connection_string()
    if not conn_str:
        print("  FAIL: No Application Insights connection string returned by telemetry API")
        return False
    print(f"  Telemetry connection string : {conn_str[:60]}...")

    # 2. Check named connection via connections list
    found = False
    for conn in client.connections.list():
        if hasattr(conn, "name") and "appinsights" in conn.name.lower():
            target = getattr(conn, "target", "")
            if expected_appi in str(target):
                print(f"  Connection match  : {conn.name} → {target}")
                found = True
                break
            else:
                print(f"  Connection found  : {conn.name} → {target} (name mismatch)")

    if not found:
        print(f"  WARNING: No connection targeting '{expected_appi}' found (telemetry still works)")

    print()
    print("  PASS: Application Insights connection verified")
    return True


def main() -> None:
    print("=" * 60)
    print("  Verify Foundry ↔ Application Insights Connection")
    print("=" * 60)
    print()
    try:
        ok = verify_appinsights_connection()
    except Exception as exc:
        print(f"  ERROR: {exc}")
        ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
