import argparse
import json
from pathlib import Path

from .core import evaluate, load_data, run
from .jev import DEFAULT_MODEL, RealJev, preview_requests


def main():
    parser = argparse.ArgumentParser(description="Support Decision Lab — offline by default; opt-in real Jev")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("tickets", help="List sample tickets")
    runner = commands.add_parser("run", help="Run a complete ticket workflow")
    source = runner.add_mutually_exclusive_group(required=True)
    source.add_argument("--ticket", help="Bundled ticket ID")
    source.add_argument("--text", help="Custom ticket text")
    runner.add_argument("--mode", choices=["hybrid", "frontier-only"], default="hybrid")
    runner.add_argument("--jev", choices=["mock", "real"], default="mock", help="Real sends ticket and draft to TypeSafe (up to 2 billable calls)")
    runner.add_argument("--model", default=DEFAULT_MODEL, help="Jev model ID; used only for real or dry-run requests")
    runner.add_argument("--timeout", type=float, default=30, help="Seconds per real request, at most 120; no retries")
    runner.add_argument("--dry-run", action="store_true", help="Show Jev request payloads without network access or keys")
    evaluator = commands.add_parser("evaluate", help="Compare both mock workflows")
    evaluator.add_argument("--split", choices=["dev", "test"], default="test")
    for command in (runner, evaluator):
        command.add_argument("--threshold", type=float, default=0.75)
        command.add_argument("--json", action="store_true", help="Print the complete JSON trace/report")
        command.add_argument("--output", type=Path, help="Save JSON to a new file (never overwrite)")
    args = parser.parse_args()
    try:
        if args.command == "tickets":
            for ticket in load_data("tickets"):
                print(f"{ticket['id']} [{ticket['split']}] {ticket['text']}")
            return
        if args.command == "run":
            text = args.text
            if args.ticket:
                ticket = next((t for t in load_data("tickets") if t["id"] == args.ticket), None)
                if ticket is None:
                    raise ValueError(f"Unknown ticket: {args.ticket}. Run 'python -m support_lab tickets'.")
                text = ticket["text"]
            if args.mode == "frontier-only" and (args.jev == "real" or args.dry_run):
                raise ValueError("Real Jev and --dry-run require --mode hybrid.")
            # Validate locally before constructing a provider or making a billable call.
            if not text or not text.strip() or len(text) > 10000 or not 0 <= args.threshold <= 1:
                raise ValueError("Provide 1–10,000 ticket characters and a threshold between 0 and 1.")
            if args.output and args.output.exists():
                raise ValueError("Output already exists. Choose a new filename before making any API calls.")
            if args.dry_run:
                result = preview_requests(text, args.model, args.threshold)
            else:
                provider = RealJev(model=args.model, timeout=args.timeout) if args.jev == "real" else None
                result = run(text, args.mode, args.threshold, decision_provider=provider)
        else:
            result = evaluate(args.split, args.threshold)
        serialized = json.dumps(result, indent=2, ensure_ascii=False)
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(serialized + "\n")
        if args.json or getattr(args, "dry_run", False):
            print(serialized)
        elif args.command == "run":
            spend = "$0" if result["usage"]["api_cost_usd"] == 0 else "not calculated; see TypeSafe billing"
            print(f"{result['limitation']}\n\nMode: {result['mode']} | API spend: {spend}\n")
            if result["usage"]["live_api_calls"]:
                print(f"Live Jev calls: {result['usage']['live_api_calls']} | Input tokens: {result['usage']['input_tokens']}")
            print(f"Category: {result['triage']['category']['choice']}\nOutcome: {result['routing']['action']}")
            print("\n".join("- " + reason for reason in result["routing"]["reasons"]))
            print(f"\nDRAFT (not sent)\n{result['draft']}\n\nUse --json to inspect distributions, evidence, and stage timings.")
        else:
            print(result["limitation"])
            for mode, metrics in result["modes"].items():
                print(f"\n{mode}: {metrics['count']} tickets; category accuracy {metrics['category_accuracy']:.0%}; urgent recall {metrics['urgent_recall']}; review rate {metrics['review_rate']:.0%}; API spend $0")
    except (ValueError, OSError) as error:
        parser.exit(2, f"Error: {error}\n")


if __name__ == "__main__":
    main()
