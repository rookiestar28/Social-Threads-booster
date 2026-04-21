#!/usr/bin/env python3
"""
Generate the core /setup artifacts from a tracker JSON file.

Usage:
    python scripts/run_setup_artifacts.py --tracker threads_daily_tracker.json --output-dir .
    python scripts/run_setup_artifacts.py --tracker threads_daily_tracker.json --output-dir . --include-brand-voice
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from generate_brand_voice import build_brand_voice
from generate_concept_library import build_concept_library
from generate_style_guide import build_style_guide, load_tracker
from render_companions import (
    HEADER_NOTICE_EN,
    HEADER_NOTICE_ZH,
    backup_if_user_modified,
    parse_iso,
    render_by_date,
    render_by_topic,
    render_comments,
    resolve_filenames,
)


def sorted_posts(tracker: dict) -> list[dict]:
    posts = tracker.get("posts") or []
    return sorted(
        posts,
        key=lambda post: parse_iso(post.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )


def write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate_artifacts(
    tracker_path: Path,
    output_dir: Path,
    lang: str,
    include_brand_voice: bool,
) -> list[Path]:
    tracker = load_tracker(tracker_path)
    posts = sorted_posts(tracker)
    notice = HEADER_NOTICE_ZH if lang == "zh" else HEADER_NOTICE_EN

    writes: list[tuple[Path, str]] = [
        (output_dir / "style_guide.md", build_style_guide(tracker)),
        (output_dir / "concept_library.md", build_concept_library(tracker)),
    ]

    if include_brand_voice:
        writes.append((output_dir / "brand_voice.md", build_brand_voice(tracker)))

    output_dir.mkdir(parents=True, exist_ok=True)
    tracker_mtime = tracker_path.stat().st_mtime
    companion_paths = resolve_filenames(output_dir, lang)
    for path in companion_paths.values():
        backup_if_user_modified(path, tracker_mtime)

    writes.extend(
        [
            (companion_paths["by_date"], render_by_date(posts, notice, lang)),
            (
                companion_paths["by_topic"],
                render_by_topic(posts, notice, lang, companion_paths["by_date"].name),
            ),
            (companion_paths["comments"], render_comments(posts, tracker, notice, lang)),
        ]
    )

    written_paths: list[Path] = []
    for path, content in writes:
        write_markdown(path, content)
        written_paths.append(path)

    return written_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the core /setup artifacts from a tracker JSON file.")
    parser.add_argument("--tracker", required=True, help="Path to threads_daily_tracker.json")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for generated artifacts (default: tracker's directory)",
    )
    parser.add_argument(
        "--lang",
        choices=["zh", "en"],
        default="zh",
        help="Default companion filename language when files do not already exist",
    )
    parser.add_argument(
        "--include-brand-voice",
        action="store_true",
        help="Also generate brand_voice.md",
    )
    args = parser.parse_args()

    tracker_path = Path(args.tracker).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else tracker_path.parent

    try:
        written_paths = generate_artifacts(
            tracker_path=tracker_path,
            output_dir=output_dir,
            lang=args.lang,
            include_brand_voice=args.include_brand_voice,
        )
    except Exception as exc:  # noqa: BLE001 - CLI should return actionable errors
        print(f"[run_setup_artifacts] {exc}", file=sys.stderr)
        return 1

    print("[run_setup_artifacts] wrote:")
    for path in written_paths:
        label = path.relative_to(output_dir) if path.is_relative_to(output_dir) else path
        print(f"  {label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
