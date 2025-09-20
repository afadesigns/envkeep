#!/usr/bin/env python3
"""Generate release notes from conventional commits."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_git(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or "git command failed"
        raise RuntimeError(message) from exc
    return result.stdout


def collect_commits(since: str | None) -> list[str]:
    git_args = ["log", "--pretty=%s"]
    if since:
        git_args.append(f"{since}..HEAD")
    return [line.strip() for line in run_git(git_args).splitlines() if line.strip()]


def format_notes(commits: list[str]) -> str:
    sections: dict[str, list[str]] = {"Features": [], "Fixes": [], "Chores": [], "Other": []}
    for commit in commits:
        lowered = commit.lower()
        if lowered.startswith("feat"):
            sections["Features"].append(commit)
        elif lowered.startswith("fix") or lowered.startswith("bug"):
            sections["Fixes"].append(commit)
        elif lowered.startswith("chore") or lowered.startswith("docs"):
            sections["Chores"].append(commit)
        else:
            sections["Other"].append(commit)
    lines: list[str] = []
    for section, items in sections.items():
        if not items:
            continue
        lines.append(f"## {section}")
        lines.extend(f"- {item}" for item in items)
        lines.append("")
    return "\n".join(lines).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate release notes")
    parser.add_argument("--since", help="Git ref to start from", default=None)
    parser.add_argument(
        "--output",
        help="Where to write notes",
        type=Path,
        default=Path("RELEASE_NOTES.md"),
    )
    args = parser.parse_args()

    try:
        commits = collect_commits(args.since)
    except RuntimeError as exc:
        print(f"Failed to collect commits: {exc}", file=sys.stderr)
        return 1
    notes = format_notes(commits) if commits else "No notable changes."
    if args.output.parent:
        args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(notes + "\n", encoding="utf-8")
    print(f"Release notes written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
