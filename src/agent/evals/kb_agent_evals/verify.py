"""
Story 7 — Verify all evaluation automation artifacts.

Checks that all evaluation components are properly configured:
  1. App Insights connection
  2. Continuous evaluation rule
  3. Daily evaluation schedule
  4. Alert resources (via AZD env)

Note: Red-team schedule verification removed — Foundry red teaming does not
currently support hosted (container-based) agents.

Usage:
    uv run python -m kb_agent_evals.verify
"""

from __future__ import annotations

import os
import sys

from kb_agent_evals.config import (
    get_agent_name,
    get_appinsights_name,
    get_env_name,
    get_project_client,
    get_project_endpoint,
)
from kb_agent_evals.continuous import get_rule_id as get_continuous_rule_id
from kb_agent_evals.scheduled_eval import get_schedule_id as get_daily_schedule_id


class VerificationResult:
    def __init__(self) -> None:
        self.checks: list[tuple[str, bool, str]] = []

    def add(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append((name, passed, detail))

    @property
    def passed(self) -> bool:
        return all(ok for _, ok, _ in self.checks)

    def report(self) -> None:
        for name, ok, detail in self.checks:
            icon = "PASS" if ok else "FAIL"
            msg = f"  [{icon}] {name}"
            if detail:
                msg += f" — {detail}"
            print(msg)


def verify_all() -> VerificationResult:
    """Run all verification checks and return results."""
    result = VerificationResult()
    client = get_project_client()
    env = get_env_name()
    agent_name = get_agent_name()

    print(f"  Environment    : {env}")
    print(f"  Project        : {get_project_endpoint()}")
    print(f"  Agent          : {agent_name}")
    print()

    # --- Check 1: App Insights connection ---
    try:
        conn_str = client.telemetry.get_application_insights_connection_string()
        if conn_str:
            result.add("App Insights connection", True, f"connected ({get_appinsights_name()})")
        else:
            result.add("App Insights connection", False, "no connection string returned")
    except Exception as exc:
        result.add("App Insights connection", False, str(exc))

    # --- Check 2: Continuous evaluation rule ---
    expected_rule_id = get_continuous_rule_id()
    try:
        rule = client.evaluation_rules.get(id=expected_rule_id)
        enabled = getattr(rule, "enabled", False)
        agent_filter = ""
        if hasattr(rule, "filter") and rule.filter:
            agent_filter = getattr(rule.filter, "agent_name", "")
        if enabled and agent_filter == agent_name:
            result.add("Continuous eval rule", True, f"{expected_rule_id} (enabled, agent={agent_name})")
        elif enabled:
            result.add("Continuous eval rule", True, f"{expected_rule_id} (enabled, filter={agent_filter})")
        else:
            result.add("Continuous eval rule", False, f"{expected_rule_id} exists but is disabled")
    except Exception as exc:
        result.add("Continuous eval rule", False, f"{expected_rule_id}: {exc}")

    # --- Check 3: Daily evaluation schedule ---
    expected_daily_id = get_daily_schedule_id()
    try:
        schedule = client.beta.schedules.get(id=expected_daily_id)
        enabled = getattr(schedule, "enabled", False)
        if enabled:
            result.add("Daily eval schedule", True, f"{expected_daily_id} (enabled)")
        else:
            result.add("Daily eval schedule", False, f"{expected_daily_id} exists but is disabled")
    except Exception as exc:
        result.add("Daily eval schedule", False, f"{expected_daily_id}: {exc}")

    # --- Check 4: Alert resources (existence check via AZD env) ---
    alert_group = os.environ.get("ALERT_ACTION_GROUP_NAME", "").strip().strip('"')
    if alert_group:
        result.add("Alert action group", True, f"{alert_group} (from AZD env)")
    else:
        result.add("Alert action group", False, "ALERT_ACTION_GROUP_NAME not set — run 'azd provision'")

    return result


def main() -> None:
    print("=" * 60)
    print("  Evaluation Automation Verification Gate")
    print("=" * 60)
    print()

    env = get_env_name()
    soft_fail = env == "dev"

    try:
        result = verify_all()
    except Exception as exc:
        print(f"  ERROR: Verification failed to run: {exc}")
        sys.exit(1)

    print()
    result.report()
    print()

    if result.passed:
        print("  ALL CHECKS PASSED")
        sys.exit(0)
    else:
        failed = [name for name, ok, _ in result.checks if not ok]
        if soft_fail:
            print(f"  WARNING: {len(failed)} check(s) failed (soft-fail mode in dev)")
            print(f"  Failed: {', '.join(failed)}")
            print("  Continuing with non-zero exit for visibility.")
            sys.exit(1)
        else:
            print(f"  FAILED: {len(failed)} check(s) failed")
            print(f"  Failed: {', '.join(failed)}")
            sys.exit(1)


if __name__ == "__main__":
    main()
