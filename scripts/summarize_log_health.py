#!/usr/bin/env python3
"""
Emit a machine-readable summary of refresh/freshness log health.
"""

from __future__ import annotations

import argparse
import json
import sys

from review_log_health import summarize_log_health


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize refresh/freshness log health as JSON.")
    parser.add_argument("--refresh-log", default=None)
    parser.add_argument("--freshness-log", default=None)
    parser.add_argument("--current-topic-slug", default=None)
    args = parser.parse_args()

    try:
        payload = summarize_log_health(
            refresh_log_path=args.refresh_log,
            freshness_log_path=args.freshness_log,
            current_topic_slug=args.current_topic_slug,
        )
    except Exception as exc:  # noqa: BLE001 - CLI should return actionable text
        print(f"[summarize_log_health] {exc}", file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
