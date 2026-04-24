#!/usr/bin/env python3
"""
Shared JSON-line logging helpers for /refresh execution.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from tracker_utils import utc_now_iso
from log_redaction import sanitize_log_value


ALLOWED_FAILURE_REASONS = {
    "login_wall",
    "handle_mismatch",
    "no_chrome_mcp",
    "selector_health_failed",
    "timeout",
    "backup_failed",
    "other",
}


def normalize_failure_reason(reason: str) -> str:
    return reason if reason in ALLOWED_FAILURE_REASONS else "other"


def build_refresh_failure_entry(
    *,
    reason: str,
    detail: str,
    ts: Optional[str] = None,
    **extra: object,
) -> dict:
    entry = {
        "ts": ts or utc_now_iso(),
        "ok": False,
        "reason": normalize_failure_reason(reason),
        "detail": detail,
    }
    entry.update(extra)
    return entry


def build_refresh_success_entry(
    *,
    posts_scraped: int,
    new_posts: int,
    updated_posts: int,
    replies_added: int,
    ts: Optional[str] = None,
    **extra: object,
) -> dict:
    entry = {
        "ts": ts or utc_now_iso(),
        "ok": True,
        "posts_scraped": posts_scraped,
        "new_posts": new_posts,
        "updated_posts": updated_posts,
        "replies_added": replies_added,
    }
    entry.update(extra)
    return entry


def append_refresh_log(log_path: str | Path, entry: dict) -> Path:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sanitized_entry = sanitize_log_value(entry)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(sanitized_entry, ensure_ascii=False, separators=(",", ":")))
        fh.write("\n")
    return path
