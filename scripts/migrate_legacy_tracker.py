#!/usr/bin/env python3
"""
Deterministic CLI for migrating legacy tracker files into the current schema.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from legacy_migration import is_legacy_tracker, migrate_legacy_tracker
from render_companions import (
    HEADER_NOTICE_EN,
    HEADER_NOTICE_ZH,
    render_by_date,
    render_by_topic,
    render_comments,
    resolve_filenames,
)
from tracker_utils import save_tracker


def read_text_file(path: str | None) -> str | None:
    if not path:
        return None
    return Path(path).read_text(encoding="utf-8")


def backup_existing(path: Path) -> Path | None:
    if not path.exists():
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = path.with_name(f"{path.name}.legacy-{stamp}")
    shutil.copy2(path, backup_path)
    return backup_path


def render_companion_files(tracker_path: Path, tracker: dict, output_dir: Path, lang: str) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    names = resolve_filenames(output_dir, lang)
    notice = HEADER_NOTICE_ZH if lang == "zh" else HEADER_NOTICE_EN
    posts = tracker.get("posts") or []

    names["by_date"].write_text(render_by_date(posts, notice, lang), encoding="utf-8")
    names["by_topic"].write_text(
        render_by_topic(posts, notice, lang, names["by_date"].name),
        encoding="utf-8",
    )
    names["comments"].write_text(render_comments(posts, tracker, notice, lang), encoding="utf-8")
    return [str(path) for path in names.values()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate a legacy tracker into the current schema.")
    parser.add_argument("--input", required=True, help="Legacy tracker JSON path")
    parser.add_argument("--output", required=True, help="Output tracker JSON path")
    parser.add_argument("--posts-markdown", default=None, help="Optional time-sorted post archive markdown")
    parser.add_argument("--comments-markdown", default=None, help="Optional flat comment log markdown")
    parser.add_argument("--write", action="store_true", help="Persist migrated tracker; default is dry-run")
    parser.add_argument("--render-companions", action="store_true", help="Regenerate markdown companions after write")
    parser.add_argument("--companion-dir", default=None, help="Companion output directory; default is tracker directory")
    parser.add_argument("--lang", choices=["zh", "en"], default="zh", help="Companion filename language")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        if not is_legacy_tracker(payload):
            raise ValueError("input does not match legacy tracker heuristics")
        tracker, report = migrate_legacy_tracker(
            payload,
            posts_markdown=read_text_file(args.posts_markdown),
            comments_markdown=read_text_file(args.comments_markdown),
        )

        backup_path = None
        companion_paths: list[str] = []
        if args.write:
            backup = backup_existing(output_path)
            backup_path = str(backup) if backup else None
            save_tracker(output_path, tracker)
            if args.render_companions:
                companion_dir = Path(args.companion_dir).resolve() if args.companion_dir else output_path.parent
                companion_paths = render_companion_files(output_path, tracker, companion_dir, args.lang)

        summary = {
            "dry_run": not args.write,
            "wrote": bool(args.write),
            "input": str(input_path),
            "output": str(output_path),
            "backup_path": backup_path,
            "companions_rendered": companion_paths,
            "report": report,
        }
    except Exception as exc:  # noqa: BLE001 - CLI should provide actionable error text.
        print(f"[migrate_legacy_tracker] {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
