#!/usr/bin/env python3
"""
Migrate a Threads-shaped tracker to the platform-neutral tracker schema.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from platform_migration import build_migration_summary, migrate_threads_tracker_to_platform_tracker
from platform_schema import validate_platform_tracker


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate a Threads tracker to platform-neutral schema v2.")
    parser.add_argument("--input", required=True, help="Path to existing threads_daily_tracker.json")
    parser.add_argument("--output", default="social_posts_tracker.json", help="Output path for generic tracker")
    parser.add_argument("--write", action="store_true", help="Write the migrated tracker. Default is dry-run summary.")
    args = parser.parse_args()

    try:
        source_path = Path(args.input)
        output_path = Path(args.output)
        source_tracker = json.loads(source_path.read_text(encoding="utf-8"))
        migrated = migrate_threads_tracker_to_platform_tracker(source_tracker)
        validate_platform_tracker(migrated)
        summary = build_migration_summary(source_tracker, migrated, would_write=args.write)
        if args.write:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(migrated, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI should return actionable error text
        print(f"[migrate_platform_tracker] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
