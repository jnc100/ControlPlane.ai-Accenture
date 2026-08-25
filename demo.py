#!/usr/bin/env python3
"""
ControlPlane Checker — end-to-end prototype demo.

Runs a set of simulated AI responses through the full pipeline
(PII detection -> AI-as-judge scoring -> policy-driven tiered decision ->
audit logging) and prints a report. Also demonstrates the core
configurability claim: the *same* response is evaluated under two
different use-case policies to show the decision changing.

Usage:
    python demo.py                  # run the full sample set
    python demo.py --use-case customer_support_chatbot   # filter by use case
"""

import argparse
import json
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from controlplane.detectors import pii_detector, judge_detector
from controlplane.policy.loader import load_policy, list_use_cases
from controlplane.engine.decision import decide
from controlplane.audit.logger import log_decision, LOG_PATH

console = Console()

TIER_STYLE = {
    "allow": "bold green",
    "edit": "bold yellow",
    "block": "bold red",
    "escalate": "bold cyan",
}

SAMPLE_PATH = Path(__file__).parent / "sample_data" / "sample_responses.json"


def run_one(item: dict, use_case_override: str = None) -> tuple:
    use_case = use_case_override or item["use_case"]
    policy = load_policy(use_case)

    pii_result = pii_detector.detect(item["response"])
    judge_result = judge_detector.score(item["prompt"], item["response"])
    decision = decide(item["id"], policy, pii_result, judge_result)
    log_decision(decision, item["response"])
    return decision, judge_result


def print_report(rows: list):
    table = Table(title="ControlPlane Checker \u2014 Decision Report", show_lines=False)
    table.add_column("ID", style="dim")
    table.add_column("Use Case")
    table.add_column("Judge", justify="right")
    table.add_column("Mode")
    table.add_column("Tier")
    table.add_column("Reason", overflow="fold")

    for decision, judge in rows:
        table.add_row(
            decision.response_id,
            decision.use_case,
            str(decision.judge_score),
            judge.mode,
            f"[{TIER_STYLE.get(decision.tier, '')}]{decision.tier.upper()}[/]",
            decision.reason,
        )
    console.print(table)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-case", default=None, help="filter sample data to one use case")
    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold]ControlPlane Checker[/bold] \u2014 real-time, configurable AI oversight\n"
        f"Available policies: {', '.join(list_use_cases())}",
        border_style="magenta",
    ))

    items = json.loads(SAMPLE_PATH.read_text())
    if args.use_case:
        items = [i for i in items if i["use_case"] == args.use_case]

    rows = [run_one(i) for i in items if i["id"] != "policy-demo"]
    print_report(rows)

    # --- Configurability demo: same input, two policies -------------------
    demo_item = next(i for i in json.loads(SAMPLE_PATH.read_text()) if i["id"] == "policy-demo")
    console.print(Panel.fit(
        f"[bold]Configurability demo[/bold]\nPrompt: {demo_item['prompt']}\n"
        f"Response: {demo_item['response']}",
        border_style="blue",
    ))
    demo_rows = [
        run_one(demo_item, use_case_override="customer_support_chatbot"),
        run_one(demo_item, use_case_override="credit_decision_support"),
    ]
    print_report(demo_rows)
    console.print(
        "[dim]Same response, same judge score \u2014 different tiers, because the "
        "policy config (not the detection logic) differs by use case.[/dim]"
    )

    console.print(f"\n[dim]Full audit trail written to {LOG_PATH}[/dim]")


if __name__ == "__main__":
    main()
