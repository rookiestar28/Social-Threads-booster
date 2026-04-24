#!/usr/bin/env python3
"""
Migrate existing Threads-shaped trackers into platform-neutral schema v2.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from platform_schema import (
    build_platform_comment,
    build_platform_post,
    build_platform_tracker,
    validate_platform_tracker,
)


class PlatformMigrationError(ValueError):
    """Raised when a tracker cannot be migrated to the platform-neutral schema."""


def _threads_account_id(tracker: dict[str, Any]) -> str:
    account = tracker.get("account") if isinstance(tracker.get("account"), dict) else {}
    handle = str(account.get("handle") or account.get("username") or "").strip()
    return f"threads:{handle}" if handle else "threads:unknown"


def _canonical_metrics(metrics: dict[str, Any] | None) -> dict[str, int | float | None]:
    source = metrics or {}
    share_values = [
        source.get("shares"),
        source.get("reposts"),
        source.get("quotes"),
    ]
    share_count = sum(value for value in share_values if isinstance(value, (int, float)) and not isinstance(value, bool))
    return {
        "view_count": source.get("views"),
        "reaction_count": source.get("likes"),
        "comment_count": source.get("replies"),
        "share_count": share_count,
    }


def _migrate_comment(comment: dict[str, Any], *, post_id: str, account_id: str, index: int) -> dict[str, Any]:
    comment_id = str(comment.get("id") or f"{post_id}:comment:{index}")
    return build_platform_comment(
        platform="threads",
        account_id=account_id,
        platform_comment_id=comment_id,
        text=str(comment.get("text", "")),
        created_at=str(comment.get("created_at", "")),
        author_id=comment.get("user"),
        metrics={"reaction_count": comment.get("likes")},
        platform_metadata={"threads": {"raw": dict(comment)}},
    )


def _migrate_post(post: dict[str, Any], *, account_id: str) -> dict[str, Any]:
    post_id = str(post.get("id", "")).strip()
    if not post_id:
        raise PlatformMigrationError("post id is required")
    raw_metrics = dict(post.get("metrics") or {})
    comments = [
        _migrate_comment(comment, post_id=post_id, account_id=account_id, index=index)
        for index, comment in enumerate(post.get("comments") or [])
        if isinstance(comment, dict)
    ]
    raw = {
        "metrics": raw_metrics,
        "source": dict(post.get("source") or {}),
        "media_type": post.get("media_type"),
        "content_type": post.get("content_type"),
        "topics": list(post.get("topics") or []),
        "legacy_id": post_id,
    }
    return build_platform_post(
        platform="threads",
        account_id=account_id,
        platform_post_id=post_id,
        canonical_post_id=f"threads:{account_id}:{post_id}",
        text=str(post.get("text", "")),
        created_at=str(post.get("created_at", "")),
        content_format=str(post.get("media_type") or "text").lower(),
        url=post.get("permalink"),
        metrics=_canonical_metrics(raw_metrics),
        comments=comments,
        source={"type": "migration", "data_completeness": str((post.get("source") or {}).get("data_completeness") or "partial")},
        platform_metadata={"threads": {"raw": raw}},
    )


def migrate_threads_tracker_to_platform_tracker(tracker: dict[str, Any]) -> dict[str, Any]:
    posts = tracker.get("posts")
    if not isinstance(posts, list):
        raise PlatformMigrationError("tracker.posts must be a list")
    account_id = _threads_account_id(tracker)
    generic_posts = [_migrate_post(post, account_id=account_id) for post in posts if isinstance(post, dict)]
    generic = build_platform_tracker(
        accounts=[
            {
                "platform": "threads",
                "account_id": account_id,
                "display_name": account_id.removeprefix("threads:"),
            }
        ],
        posts=generic_posts,
        last_updated=str(tracker.get("last_updated") or ""),
    )
    validate_platform_tracker(generic)
    return generic


def build_migration_summary(source_tracker: dict[str, Any], migrated_tracker: dict[str, Any], *, would_write: bool) -> dict[str, Any]:
    return {
        "source_posts": len(source_tracker.get("posts") or []),
        "migrated_posts": len(migrated_tracker.get("posts") or []),
        "platforms": sorted({post["platform"] for post in migrated_tracker.get("posts", [])}),
        "schema_version": migrated_tracker.get("schema_version"),
        "would_write": would_write,
    }
