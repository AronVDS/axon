#!/usr/bin/env python3
"""
Quiet CLI wrapper for the Axon orchestrator.
Prints ONLY the final agent result to stdout; all internal logging goes to stderr.
Task is read from stdin.

Usage:
    echo "Toon mijn taken" | python run_task.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Redirect orchestrator's progress prints to stderr so stdout stays clean.
# Must happen before importing orchestrator, which sets up its print() calls.
import builtins
_real_print = builtins.print

def _stderr_print(*args, **kwargs):
    kwargs.setdefault("file", sys.stderr)
    _real_print(*args, **kwargs)

builtins.print = _stderr_print


def main() -> None:
    task = sys.stdin.read().strip()
    if not task:
        _real_print("Geen taak opgegeven.", file=sys.stderr)
        sys.exit(1)

    try:
        from orchestrator import run

        result = run(task)

        # Agents return plain Dutch strings — never JSON.
        # Write directly to stdout without any parsing or wrapping.
        output = result if isinstance(result, str) else str(result)
        sys.stdout.write(output)
        if not output.endswith("\n"):
            sys.stdout.write("\n")
        sys.stdout.flush()

    except Exception as exc:
        _real_print(f"[Fout] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
