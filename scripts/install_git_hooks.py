#!/usr/bin/env python3
"""
Install repository-managed Git hooks for Social-Booster.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_PATH = ".githooks"
PRE_PUSH_HOOK = "pre-push"


def build_git_config_command() -> list[str]:
    return ["git", "config", "core.hooksPath", HOOKS_PATH]


def validate_hook_layout(repo_root: Path = REPO_ROOT) -> None:
    hooks_dir = repo_root / HOOKS_PATH
    pre_push = hooks_dir / PRE_PUSH_HOOK
    if not hooks_dir.is_dir():
        raise FileNotFoundError(f"missing hooks directory: {hooks_dir}")
    if not pre_push.is_file():
        raise FileNotFoundError(f"missing pre-push hook: {pre_push}")


def install_hooks(repo_root: Path = REPO_ROOT) -> str:
    validate_hook_layout(repo_root)
    subprocess.run(build_git_config_command(), cwd=repo_root, check=True)
    result = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"],
        cwd=repo_root,
        text=True,
        check=True,
        capture_output=True,
    )
    return result.stdout.strip()


def main() -> int:
    try:
        configured = install_hooks()
    except Exception as exc:  # noqa: BLE001 - CLI should print a concise installation error.
        print(f"[install-git-hooks] ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"[install-git-hooks] core.hooksPath={configured}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
