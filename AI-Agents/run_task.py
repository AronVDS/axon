#!/usr/bin/env python3
"""
Quiet CLI wrapper for the Axon orchestrator.
Prints ONLY the final agent result to stdout; suppresses all internal logging.
Task is read from stdin.

Usage:
    echo "Toon mijn taken" | python run_task.py
"""
import sys
import os
import contextlib
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    task = sys.stdin.read().strip()
    if not task:
        print("Geen taak opgegeven.", file=sys.stderr)
        sys.exit(1)

    try:
        from orchestrator import run

        # Suppress the progress/logging prints that orchestrator.run() emits;
        # we only want the clean return value on stdout for the API caller.
        buf = StringIO()
        with contextlib.redirect_stdout(buf):
            result = run(task)

        print(result, flush=True)
    except Exception as exc:
        print(f"[Fout] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
