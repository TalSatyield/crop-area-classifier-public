#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent to safely edit config.py as requested and run main.py, summarizing results.

Usage examples:
  - Dry run planned edits:
      python agent.py --plan crops_to_process='["Corn","Soy"]' inference_year=2024
  - Apply edits then run main.py:
      python agent.py crops_to_process='["Corn","Soy"]' inference_year=2024
  - Run without edits (just execute main.py):
      python agent.py --run

Notes:
  - Only edits keys that already exist in config.py to avoid unintended changes.
  - Values are parsed as Python literals when possible (e.g., lists, dicts, ints, floats, booleans).
  - String values can be provided with or without quotes; internal quoting will be preserved.
"""

import argparse
import ast
import os
import re
import subprocess
import sys
from typing import Dict, Tuple, Optional

WORKDIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(WORKDIR, "config.py")
MAIN_PATH = os.path.join(WORKDIR, "main.py")


def parse_key_value(arg: str) -> Tuple[str, str]:
    if "=" not in arg:
        raise argparse.ArgumentTypeError(f"Invalid assignment '{arg}'. Use key=value")
    key, value = arg.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        raise argparse.ArgumentTypeError("Empty key in assignment")
    return key, value


def parse_value(value_str: str):
    try:
        return ast.literal_eval(value_str)
    except Exception:
        # Fallback: treat as plain string, strip surrounding quotes if present
        if (value_str.startswith("\"") and value_str.endswith("\"")) or (
            value_str.startswith("'") and value_str.endswith("'")
        ):
            return value_str[1:-1]
        return value_str


def python_repr(value) -> str:
    # Ensure strings are quoted with single quotes to match typical style
    if isinstance(value, str):
        return repr(value)
    return repr(value)


def load_config_text() -> str:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return f.read()


def write_config_text(text: str) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(text)


def update_config(config_text: str, updates: Dict[str, str], plan_only: bool = False) -> Tuple[str, Dict[str, Tuple[Optional[str], str]]]:
    """
    Update only existing top-level assignments in config.py.

    Returns new_text and a mapping of key -> (old_repr, new_repr).
    """
    changes: Dict[str, Tuple[Optional[str], str]] = {}

    # Build regex to match simple assignments at start of a line (allowing indentation and comments after value)
    # Preserve original indentation and inline comments.
    lines = config_text.splitlines()
    key_to_line_idx: Dict[str, int] = {}
    assign_pattern = re.compile(r"^([ \t]*)([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)(\s*(#.*)?)$")

    for idx, line in enumerate(lines):
        m = assign_pattern.match(line)
        if not m:
            continue
        indent, name, value_part, trailing = m.group(1), m.group(2), m.group(3), m.group(4) or ""
        key_to_line_idx[name] = idx

    for key, raw_value in updates.items():
        if key not in key_to_line_idx:
            raise ValueError(f"Key '{key}' not found in config.py; refusing to create new entries.")
        idx = key_to_line_idx[key]
        m = assign_pattern.match(lines[idx])
        assert m
        indent, name, old_value_part, trailing = m.group(1), m.group(2), m.group(3), m.group(4) or ""

        parsed_value = parse_value(raw_value)
        new_value_repr = python_repr(parsed_value)
        new_line = f"{indent}{name} = {new_value_repr}{trailing}"

        changes[key] = (old_value_part.strip(), new_value_repr)
        if not plan_only:
            lines[idx] = new_line

    return ("\n".join(lines) + ("\n" if config_text.endswith("\n") else "")), changes


def run_main() -> Tuple[int, str, str]:
    env = os.environ.copy()
    proc = subprocess.Popen(
        [sys.executable, MAIN_PATH],
        cwd=WORKDIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    out, err = proc.communicate()
    return proc.returncode, out, err


def summarize_output(stdout: str, stderr: str) -> str:
    # Extract key lines for a concise summary
    summary_lines = []

    def grep(lines, patterns):
        for pat in patterns:
            for line in lines:
                if pat in line:
                    summary_lines.append(line.rstrip())

    out_lines = stdout.splitlines()
    err_lines = stderr.splitlines()

    grep(out_lines, [
        "🚀 Starting crop area classification",
        "Configuration:",
        "Satellite Data:",
        "States:",
        "Features:",
        "Date Range:",
        "⏱️  State Processing Completed in:",
        "total_FINAL corn_area",
        "total_FINAL soy_area",
        "🎯 FINAL RESULTS:",
        "Corn Area (million acres):",
        "Soy Area (million acres):",
        "📊 VALIDATION vs USDA DATA",
    ])

    # Include last few lines of stdout and stderr for context
    tail_out = out_lines[-10:] if len(out_lines) > 10 else out_lines
    tail_err = err_lines[-10:] if len(err_lines) > 0 else []

    summary = []
    if summary_lines:
        summary.append("\n".join(summary_lines))
    if tail_out:
        summary.append("\n--- stdout tail ---\n" + "\n".join(tail_out))
    if tail_err:
        summary.append("\n--- stderr tail ---\n" + "\n".join(tail_err))
    return "\n".join(summary)


def main():
    parser = argparse.ArgumentParser(description="Edit config.py safely and run main.py, summarizing results.")
    parser.add_argument("assignments", nargs="*", type=str, help="Key=Value pairs to update in config.py")
    parser.add_argument("--plan", action="store_true", help="Plan only; show intended edits without modifying files")
    parser.add_argument("--run", action="store_true", help="Run main.py without making edits")
    args = parser.parse_args()

    if not os.path.isfile(CONFIG_PATH):
        print(f"Missing config.py at {CONFIG_PATH}", file=sys.stderr)
        sys.exit(2)
    if not os.path.isfile(MAIN_PATH):
        print(f"Missing main.py at {MAIN_PATH}", file=sys.stderr)
        sys.exit(2)

    planned_updates: Dict[str, str] = {}
    for a in args.assignments:
        key, raw_value = parse_key_value(a)
        planned_updates[key] = raw_value

    if planned_updates:
        config_text = load_config_text()
        new_text, changes = update_config(config_text, planned_updates, plan_only=args.plan)
        print("Planned changes to config.py:")
        for k, (old, new) in changes.items():
            print(f"  - {k}: {old} -> {new}")
        if not args.plan:
            write_config_text(new_text)
            print("Applied changes to config.py")

    if args.plan and not args.run and not planned_updates:
        print("Nothing to plan. Provide key=value or use --run.")
        sys.exit(0)

    # Run main.py if requested or if we made changes (default behavior)
    should_run = args.run or bool(planned_updates) or (not args.plan)
    if should_run:
        code, out, err = run_main()
        print(summarize_output(out, err))
        sys.exit(code)


if __name__ == "__main__":
    main()

