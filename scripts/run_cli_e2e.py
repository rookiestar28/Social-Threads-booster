#!/usr/bin/env python3
"""
Run fixture-based CLI E2E validation for deterministic local scripts.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TMP_DIR = REPO_ROOT / ".tmp" / "cli-e2e"


class E2EFailure(RuntimeError):
    """Raised when a CLI E2E step fails its process or artifact checks."""


def run_command(label: str, command: list[str]) -> subprocess.CompletedProcess[str]:
    print(f"[cli-e2e] {label}")
    print(f"[cli-e2e] command: {' '.join(command)}")
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def assert_command_ok(label: str, result: subprocess.CompletedProcess[str]) -> None:
    if result.returncode != 0:
        raise E2EFailure(
            f"{label} failed with exit code {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


def assert_command_failed(label: str, result: subprocess.CompletedProcess[str]) -> None:
    if result.returncode == 0:
        raise E2EFailure(f"{label} was expected to fail but exited 0")


def assert_file_exists(path: Path) -> None:
    if not path.exists():
        raise E2EFailure(f"expected file to exist: {path}")


def assert_file_contains(path: Path, expected_text: str) -> None:
    assert_file_exists(path)
    content = path.read_text(encoding="utf-8")
    if expected_text not in content:
        raise E2EFailure(f"expected text {expected_text!r} in {path}")


def write_parse_export_fixture(case_dir: Path) -> Path:
    case_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = case_dir / "threads-export.json"
    payload = {
        "threads_media": [
            {
                "title": "E2E imported platform post",
                "creation_timestamp": 1770000000,
            }
        ]
    }
    fixture_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return fixture_path


def write_review_log_health_fixtures(case_dir: Path) -> tuple[Path, Path]:
    case_dir.mkdir(parents=True, exist_ok=True)
    refresh_log = case_dir / "threads_refresh.log"
    freshness_log = case_dir / "threads_freshness.log"

    refresh_log.write_text(
        json.dumps(
            {
                "timestamp": "2026-04-25T00:00:00+00:00",
                "ok": False,
                "reason": "other",
                "detail": "synthetic missing token",
                "mode": "api",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    freshness_log.write_text(
        json.dumps(
            {
                "timestamp": "2026-04-25T00:00:00+00:00",
                "skill": "draft",
                "target": "seo-recovery-playbook",
                "status": "skipped_by_user",
                "decision": "yellow",
                "run_id": "e2e-run",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return refresh_log, freshness_log


def validate_json_file(path: Path, required_keys: list[str] | None = None) -> dict:
    assert_file_exists(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise E2EFailure(f"expected object-shaped JSON in {path}")
    for key in required_keys or []:
        if key not in payload:
            raise E2EFailure(f"expected key {key!r} in {path}")
    return payload


def run_cli_e2e(output_dir: Path, clean: bool = True) -> None:
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    python = sys.executable
    tracker = REPO_ROOT / "examples" / "tracker-example.json"

    style_output = output_dir / "style_guide-e2e.md"
    result = run_command(
        "style guide generation",
        [python, "scripts/generate_style_guide.py", "--tracker", str(tracker), "--output", str(style_output)],
    )
    assert_command_ok("style guide generation", result)
    assert_file_contains(style_output, "# Personalized Style Guide")

    companions_dir = output_dir / "companions"
    result = run_command(
        "companion rendering",
        [
            python,
            "scripts/render_companions.py",
            "--tracker",
            str(tracker),
            "--output-dir",
            str(companions_dir),
            "--lang",
            "en",
        ],
    )
    assert_command_ok("companion rendering", result)
    for filename in ("posts_by_date.md", "posts_by_topic.md", "comments.md"):
        assert_file_exists(companions_dir / filename)

    concept_output = output_dir / "concept_library-e2e.md"
    result = run_command(
        "concept library generation",
        [python, "scripts/generate_concept_library.py", "--tracker", str(tracker), "--output", str(concept_output)],
    )
    assert_command_ok("concept library generation", result)
    assert_file_contains(concept_output, "# Concept Library")

    brand_output = output_dir / "brand_voice-e2e.md"
    result = run_command(
        "brand voice generation",
        [python, "scripts/generate_brand_voice.py", "--tracker", str(tracker), "--output", str(brand_output)],
    )
    assert_command_ok("brand voice generation", result)
    assert_file_contains(brand_output, "# Brand Voice Profile")

    setup_dir = output_dir / "setup-artifacts"
    result = run_command(
        "setup artifact pipeline",
        [
            python,
            "scripts/run_setup_artifacts.py",
            "--tracker",
            str(tracker),
            "--output-dir",
            str(setup_dir),
            "--lang",
            "en",
            "--include-brand-voice",
        ],
    )
    assert_command_ok("setup artifact pipeline", result)
    for filename in ("style_guide.md", "concept_library.md", "brand_voice.md", "posts_by_date.md", "posts_by_topic.md", "comments.md"):
        assert_file_exists(setup_dir / filename)

    freshness_tracker = output_dir / "tracker-topic-freshness.json"
    shutil.copy2(tracker, freshness_tracker)
    result = run_command(
        "topic freshness annotation",
        [python, "scripts/update_topic_freshness.py", "--tracker", str(freshness_tracker)],
    )
    assert_command_ok("topic freshness annotation", result)
    freshness_payload = validate_json_file(freshness_tracker, ["posts"])
    first_post = freshness_payload["posts"][0]
    if not ((first_post.get("algorithm_signals") or {}).get("topic_freshness")):
        raise E2EFailure("expected topic_freshness to be populated")

    parse_dir = output_dir / "parse-export"
    parse_fixture = write_parse_export_fixture(parse_dir)
    parse_output = parse_dir / "tracker.json"
    result = run_command(
        "export parsing",
        [python, "scripts/parse_export.py", "--input", str(parse_fixture), "--output", str(parse_output)],
    )
    assert_command_ok("export parsing", result)
    parse_payload = validate_json_file(parse_output, ["posts"])
    if not isinstance(parse_payload["posts"], list):
        raise E2EFailure("expected parse export output posts to be an array")

    refresh_log = output_dir / "threads_refresh.log"
    result = run_command(
        "headless refresh failure logging",
        [
            python,
            "scripts/update_snapshots.py",
            "--tracker",
            str(tracker),
            "--headless",
            "--log-file",
            str(refresh_log),
        ],
    )
    assert_command_failed("headless refresh failure logging", result)
    refresh_lines = [json.loads(line) for line in refresh_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not refresh_lines or refresh_lines[-1].get("ok") is not False:
        raise E2EFailure("expected headless refresh failure log with ok=false")

    freshness_log = output_dir / "threads_freshness.log"
    result = run_command(
        "freshness audit logging",
        [
            python,
            "scripts/log_freshness_audit.py",
            "--skill",
            "draft",
            "--target",
            "seo-recovery-playbook",
            "--status",
            "skipped_by_user",
            "--outcome",
            "yellow",
            "--web-search-query",
            "seo recovery playbook 2026",
            "--log-file",
            str(freshness_log),
        ],
    )
    assert_command_ok("freshness audit logging", result)
    freshness_lines = [json.loads(line) for line in freshness_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not freshness_lines or freshness_lines[-1].get("skill") != "draft":
        raise E2EFailure("expected freshness log draft entry")

    health_dir = output_dir / "review-log-health"
    synthetic_refresh_log, synthetic_freshness_log = write_review_log_health_fixtures(health_dir)
    result = run_command(
        "review log-health summary",
        [
            python,
            "scripts/summarize_log_health.py",
            "--refresh-log",
            str(synthetic_refresh_log),
            "--freshness-log",
            str(synthetic_freshness_log),
            "--current-topic-slug",
            "seo-recovery-playbook",
        ],
    )
    assert_command_ok("review log-health summary", result)
    payload = json.loads(result.stdout)
    if "refresh" not in payload or "freshness" not in payload:
        raise E2EFailure("expected refresh and freshness summaries in log-health output")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run fixture-based CLI E2E validation.")
    parser.add_argument("--output-dir", default=str(DEFAULT_TMP_DIR))
    parser.add_argument("--no-clean", action="store_true", help="Do not remove the output directory before running.")
    args = parser.parse_args()

    try:
        run_cli_e2e(Path(args.output_dir).resolve(), clean=not args.no_clean)
    except E2EFailure as exc:
        print(f"[cli-e2e] failed: {exc}", file=sys.stderr)
        return 1

    print("[cli-e2e] all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
