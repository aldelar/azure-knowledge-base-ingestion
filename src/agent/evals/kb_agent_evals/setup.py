"""
Story 7 — Orchestrate all evaluation setup steps.

Runs all evaluation automation in the correct order:
  1. Verify App Insights connection
  2. Bootstrap baseline eval definitions (returns eval_ids)
  3. Configure continuous evaluation rule  (uses quality eval_id)
  4. Configure scheduled daily evaluation  (uses dataset eval_id)

Note: Red-team scheduling is **not implemented** — see bootstrap.py docstring.

Usage:
    uv run python -m kb_agent_evals.setup
"""

from __future__ import annotations

import sys

from kb_agent_evals.config import get_env_name, get_project_endpoint


def run_step(name: str, func, soft_fail: bool = False) -> bool:
    """Run a setup step and handle errors."""
    print(f"\n{'─' * 60}")
    print(f"  Step: {name}")
    print(f"{'─' * 60}\n")
    try:
        func()
        return True
    except Exception as exc:
        if soft_fail:
            print(f"\n  WARNING: {name} failed (soft-fail): {exc}")
            return False
        else:
            print(f"\n  ERROR: {name} failed: {exc}")
            raise


def main() -> None:
    env = get_env_name()
    soft_fail = env == "dev"

    print("=" * 60)
    print("  KB Agent Evaluation Setup Orchestrator")
    print("=" * 60)
    print()
    print(f"  Environment  : {env}")
    print(f"  Project      : {get_project_endpoint()}")
    print(f"  Soft-fail    : {soft_fail}")

    from kb_agent_evals.verify_appinsights import verify_appinsights_connection
    from kb_agent_evals.bootstrap import bootstrap
    from kb_agent_evals.continuous import setup_continuous_eval
    from kb_agent_evals.scheduled_eval import setup_scheduled_eval

    results: list[tuple[str, bool]] = []

    # Step 1 — App Insights
    ok = run_step("Verify App Insights", verify_appinsights_connection, soft_fail=soft_fail)
    results.append(("Verify App Insights", ok))

    # Step 2 — Bootstrap eval definitions
    eval_ids: dict[str, str] = {}

    def _bootstrap():
        nonlocal eval_ids
        eval_ids = bootstrap()

    ok = run_step("Bootstrap baseline eval definitions", _bootstrap, soft_fail=soft_fail)
    results.append(("Bootstrap baseline eval definitions", ok))

    if not eval_ids:
        print("\n  SKIP: Cannot proceed without eval_ids from bootstrap.")
        results.extend([
            ("Configure continuous evaluation", False),
            ("Configure daily scheduled evaluation", False),
        ])
    else:
        # Step 3 — Continuous rule
        ok = run_step(
            "Configure continuous evaluation",
            lambda: setup_continuous_eval(eval_ids["quality"]),
            soft_fail=soft_fail,
        )
        results.append(("Configure continuous evaluation", ok))

        # Step 4 — Daily schedule
        ok = run_step(
            "Configure daily scheduled evaluation",
            lambda: setup_scheduled_eval(eval_ids["dataset"]),
            soft_fail=soft_fail,
        )
        results.append(("Configure daily scheduled evaluation", ok))

    # Summary
    print(f"\n{'=' * 60}")
    print("  Setup Summary")
    print(f"{'=' * 60}\n")
    for name, ok in results:
        icon = "PASS" if ok else "WARN" if soft_fail else "FAIL"
        print(f"  [{icon}] {name}")

    failed = [n for n, ok in results if not ok]
    if failed:
        print(f"\n  {len(failed)} step(s) had issues: {', '.join(failed)}")
        if not soft_fail:
            sys.exit(1)
    else:
        print("\n  All steps completed successfully.")


if __name__ == "__main__":
    main()
