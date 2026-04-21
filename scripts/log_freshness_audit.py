#!/usr/bin/env python3
"""
Append one contract-compliant freshness audit entry to threads_freshness.log.
"""

from __future__ import annotations

import argparse
import sys

from freshness_logging import (
    append_freshness_log,
    build_draft_freshness_entry,
    build_topics_freshness_entry,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Append one freshness audit entry to threads_freshness.log.")
    parser.add_argument("--skill", choices=["topics", "draft"], required=True)
    parser.add_argument("--target", required=True, help="Candidate/topic slug")
    parser.add_argument(
        "--status",
        choices=["performed", "unavailable", "skipped_by_user"],
        required=True,
    )
    parser.add_argument("--outcome", choices=["green", "yellow", "red"], required=True)
    parser.add_argument("--web-search-query", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--log-file", default="threads_freshness.log")
    args = parser.parse_args()

    try:
        if args.skill == "topics":
            entry = build_topics_freshness_entry(
                candidate=args.target,
                status=args.status,
                verdict=args.outcome,
                web_search_query=args.web_search_query,
                run_id=args.run_id,
            )
        else:
            entry = build_draft_freshness_entry(
                topic=args.target,
                status=args.status,
                decision=args.outcome,
                web_search_query=args.web_search_query,
                run_id=args.run_id,
            )
        append_freshness_log(args.log_file, entry)
    except Exception as exc:  # noqa: BLE001 - CLI should return actionable text
        print(f"[log_freshness_audit] {exc}", file=sys.stderr)
        return 1

    print(f"[log_freshness_audit] wrote {args.log_file}")
    print(f"[log_freshness_audit] run_id={entry['run_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
