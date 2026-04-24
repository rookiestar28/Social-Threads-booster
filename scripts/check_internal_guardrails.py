#!/usr/bin/env python3
"""
Verify that local-only internal paths are ignored and not tracked by Git.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_PROTECTED_PATHS = (
    ".planning/",
    "reference/",
    ".reference/",
    "AGENTS.md",
    "ROADMAP.md",
    "roadmap.md",
)


@dataclass(frozen=True)
class GuardrailResult:
    path: str
    ignored: bool
    tracked_paths: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.ignored and not self.tracked_paths


class GuardrailError(RuntimeError):
    pass


def run_git(repo_root: Path, args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=check,
        )
    except FileNotFoundError as exc:
        raise GuardrailError("git executable was not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise GuardrailError(detail) from exc


def is_git_repo(repo_root: Path) -> bool:
    result = run_git(repo_root, ["rev-parse", "--is-inside-work-tree"])
    return result.returncode == 0 and result.stdout.strip() == "true"


def is_ignored(repo_root: Path, path: str) -> bool:
    result = run_git(repo_root, ["check-ignore", "-q", "--no-index", path])
    return result.returncode == 0


def tracked_paths(repo_root: Path, path: str) -> tuple[str, ...]:
    result = run_git(repo_root, ["ls-files", "-z", "--", path], check=True)
    if not result.stdout:
        return ()
    return tuple(item for item in result.stdout.split("\0") if item)


def check_paths(repo_root: Path, paths: list[str]) -> list[GuardrailResult]:
    if not is_git_repo(repo_root):
        raise GuardrailError(f"not a Git work tree: {repo_root}")

    results: list[GuardrailResult] = []
    for path in paths:
        results.append(
            GuardrailResult(
                path=path,
                ignored=is_ignored(repo_root, path),
                tracked_paths=tracked_paths(repo_root, path),
            )
        )
    return results


def format_report(results: list[GuardrailResult]) -> str:
    lines = ["Internal file guardrail report:"]
    for result in results:
        status = "OK" if result.ok else "FAIL"
        tracked = ", ".join(result.tracked_paths) if result.tracked_paths else "-"
        lines.append(
            f"- {status} {result.path} ignored={str(result.ignored).lower()} tracked={tracked}"
        )
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check that internal-only paths are ignored and not tracked.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root to inspect (default: current directory).",
    )
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        help="Protected path to check. Can be supplied multiple times.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    repo_root = Path(args.repo_root).resolve()
    protected_paths = args.paths or list(DEFAULT_PROTECTED_PATHS)

    try:
        results = check_paths(repo_root, protected_paths)
    except GuardrailError as exc:
        print(f"Internal file guardrail failed: {exc}", file=sys.stderr)
        return 2

    print(format_report(results))
    failed = [result for result in results if not result.ok]
    if failed:
        print(
            "\nFix required: internal-only paths must be ignored and absent from Git tracking.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
