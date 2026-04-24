#!/usr/bin/env python3
"""
Run the repo-local validation gate for Social-Booster.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ValidationStep:
    name: str
    command: list[str]
    optional: bool = False
    skip_reason: str | None = None


@dataclass(frozen=True)
class StepResult:
    name: str
    returncode: int | None
    skipped: bool
    optional: bool
    skip_reason: str | None


def build_validation_steps(
    *,
    python_executable: str,
    repo_root: Path = REPO_ROOT,
    include_precommit: bool = True,
    include_cli_e2e: bool = True,
) -> list[ValidationStep]:
    steps: list[ValidationStep] = []
    precommit_config = repo_root / ".pre-commit-config.yaml"
    precommit_skip = None if precommit_config.exists() else ".pre-commit-config.yaml missing"

    if include_precommit:
        steps.extend(
            [
                ValidationStep(
                    name="pre-commit detect-secrets",
                    command=[python_executable, "-m", "pre_commit", "run", "detect-secrets", "--all-files"],
                    optional=precommit_skip is not None,
                    skip_reason=precommit_skip,
                ),
                ValidationStep(
                    name="pre-commit all hooks",
                    command=[python_executable, "-m", "pre_commit", "run", "--all-files", "--show-diff-on-failure"],
                    optional=precommit_skip is not None,
                    skip_reason=precommit_skip,
                ),
            ]
        )

    steps.extend(
        [
            ValidationStep(
                name="internal guardrails",
                command=[python_executable, "scripts/check_internal_guardrails.py"],
            ),
            ValidationStep(
                name="python regression tests",
                command=[python_executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
            ),
        ]
    )

    if include_cli_e2e:
        steps.append(
            ValidationStep(
                name="cli e2e",
                command=[python_executable, "scripts/run_cli_e2e.py"],
            )
        )

    return steps


def run_step(step: ValidationStep) -> StepResult:
    if step.skip_reason and step.optional:
        print(f"[validate] SKIP {step.name}: {step.skip_reason}")
        return StepResult(
            name=step.name,
            returncode=None,
            skipped=True,
            optional=True,
            skip_reason=step.skip_reason,
        )

    print(f"[validate] RUN {step.name}")
    print(f"[validate] command: {' '.join(step.command)}")
    result = subprocess.run(step.command, cwd=REPO_ROOT, text=True, check=False)
    status = "PASS" if result.returncode == 0 else "FAIL"
    print(f"[validate] {status} {step.name} ({result.returncode})")
    return StepResult(
        name=step.name,
        returncode=result.returncode,
        skipped=False,
        optional=step.optional,
        skip_reason=step.skip_reason,
    )


def results_passed(results: list[StepResult]) -> bool:
    for result in results:
        if result.skipped and result.optional:
            continue
        if result.returncode != 0:
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the repo-local validation gate.")
    parser.add_argument("--skip-precommit", action="store_true", help="Do not attempt pre-commit checks.")
    parser.add_argument("--skip-cli-e2e", action="store_true", help="Do not run the CLI E2E sweep.")
    args = parser.parse_args()

    steps = build_validation_steps(
        python_executable=sys.executable,
        include_precommit=not args.skip_precommit,
        include_cli_e2e=not args.skip_cli_e2e,
    )

    results: list[StepResult] = []
    for step in steps:
        result = run_step(step)
        results.append(result)
        if not result.skipped and result.returncode != 0:
            print(f"[validate] stopping after failed required step: {result.name}", file=sys.stderr)
            break

    print("[validate] summary:")
    for result in results:
        if result.skipped:
            print(f"  - SKIP {result.name}: {result.skip_reason}")
        else:
            status = "PASS" if result.returncode == 0 else "FAIL"
            print(f"  - {status} {result.name}")

    if not results_passed(results):
        return 1
    print("[validate] all required checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
