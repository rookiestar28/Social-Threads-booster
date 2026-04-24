#!/usr/bin/env python3
"""
Platform-neutral tracker schema helpers.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


CANONICAL_METRIC_KEYS = (
    "view_count",
    "reaction_count",
    "comment_count",
    "share_count",
    "save_count",
    "click_count",
    "watch_time_seconds",
)
SECRET_KEY_FRAGMENTS = ("secret", "token", "password", "cookie", "authorization", "credential")


class PlatformTrackerValidationError(ValueError):
    """Raised when a platform-neutral tracker fails schema validation."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_platform_metrics(metrics: dict[str, Any] | None = None) -> dict[str, int | float | None]:
    source = metrics or {}
    normalized: dict[str, int | float | None] = {}
    for key in CANONICAL_METRIC_KEYS:
        value = source.get(key)
        normalized[key] = value if value is not None else None
    return normalized


def build_platform_comment(
    *,
    platform: str,
    account_id: str,
    platform_comment_id: str,
    text: str,
    created_at: str,
    author_id: str | None = None,
    metrics: dict[str, Any] | None = None,
    platform_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "platform": platform,
        "account_id": account_id,
        "platform_comment_id": str(platform_comment_id),
        "text": text,
        "created_at": created_at,
        "author_id": author_id,
        "metrics": build_platform_metrics(metrics),
        "platform_metadata": deepcopy(platform_metadata or {}),
    }


def build_platform_post(
    *,
    platform: str,
    account_id: str,
    platform_post_id: str,
    text: str,
    created_at: str,
    canonical_post_id: str | None = None,
    content_format: str = "text",
    url: str | None = None,
    metrics: dict[str, Any] | None = None,
    comments: list[dict[str, Any]] | None = None,
    source: dict[str, Any] | None = None,
    platform_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stable_post_id = canonical_post_id or f"{platform}:{account_id}:{platform_post_id}"
    return {
        "platform": platform,
        "account_id": account_id,
        "platform_post_id": str(platform_post_id),
        "canonical_post_id": stable_post_id,
        "text": text,
        "created_at": created_at,
        "content_format": content_format,
        "url": url,
        "metrics": build_platform_metrics(metrics),
        "comments": list(comments or []),
        "source": deepcopy(source or {"type": "fixture", "data_completeness": "partial"}),
        "platform_metadata": deepcopy(platform_metadata or {}),
    }


def build_platform_tracker(
    *,
    accounts: list[dict[str, Any]] | None = None,
    posts: list[dict[str, Any]] | None = None,
    last_updated: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "tracker_type": "platform-neutral",
        "accounts": list(accounts or []),
        "posts": list(posts or []),
        "last_updated": last_updated or utc_now_iso(),
    }


def _fail(path: str, message: str) -> None:
    raise PlatformTrackerValidationError(f"{path} {message}")


def _require_type(value: Any, expected_type: type | tuple[type, ...], path: str) -> None:
    if not isinstance(value, expected_type):
        if isinstance(expected_type, tuple):
            expected = " or ".join(t.__name__ for t in expected_type)
        else:
            expected = expected_type.__name__
        _fail(path, f"must be {expected}")


def _require_non_empty_string(value: Any, path: str) -> None:
    if not isinstance(value, str) or not value.strip():
        _fail(path, "must be a non-empty string")


def _contains_secret_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            lowered = str(key).lower()
            if any(fragment in lowered for fragment in SECRET_KEY_FRAGMENTS):
                return True
            if _contains_secret_key(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_secret_key(item) for item in value)
    return False


def _validate_metrics(metrics: Any, path: str) -> None:
    _require_type(metrics, dict, path)
    for key in CANONICAL_METRIC_KEYS:
        if key not in metrics:
            _fail(f"{path}.{key}", "is required")
        value = metrics[key]
        if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            _fail(f"{path}.{key}", "must be numeric or null")


def _validate_platform_metadata(metadata: Any, path: str) -> None:
    _require_type(metadata, dict, path)
    if _contains_secret_key(metadata):
        _fail(path, "must not contain inline secret-like keys")


def _validate_comment(comment: Any, path: str) -> None:
    _require_type(comment, dict, path)
    for field in ("platform", "account_id", "platform_comment_id", "text", "created_at"):
        _require_non_empty_string(comment.get(field), f"{path}.{field}")
    _validate_metrics(comment.get("metrics"), f"{path}.metrics")
    _validate_platform_metadata(comment.get("platform_metadata"), f"{path}.platform_metadata")


def _validate_post(post: Any, path: str) -> None:
    _require_type(post, dict, path)
    for field in ("platform", "account_id", "platform_post_id", "canonical_post_id", "text", "created_at", "content_format"):
        _require_non_empty_string(post.get(field), f"{path}.{field}")
    _validate_metrics(post.get("metrics"), f"{path}.metrics")
    _require_type(post.get("comments"), list, f"{path}.comments")
    _require_type(post.get("source"), dict, f"{path}.source")
    _validate_platform_metadata(post.get("platform_metadata"), f"{path}.platform_metadata")
    for index, comment in enumerate(post.get("comments") or []):
        _validate_comment(comment, f"{path}.comments[{index}]")


def validate_platform_tracker(tracker: Any) -> None:
    _require_type(tracker, dict, "tracker")
    if tracker.get("schema_version") != 2:
        _fail("tracker.schema_version", "must be 2")
    if tracker.get("tracker_type") != "platform-neutral":
        _fail("tracker.tracker_type", "must be platform-neutral")
    _require_type(tracker.get("accounts"), list, "tracker.accounts")
    _require_type(tracker.get("posts"), list, "tracker.posts")
    _require_non_empty_string(tracker.get("last_updated"), "tracker.last_updated")

    for index, account in enumerate(tracker.get("accounts") or []):
        _require_type(account, dict, f"accounts[{index}]")
        _require_non_empty_string(account.get("platform"), f"accounts[{index}].platform")
        _require_non_empty_string(account.get("account_id"), f"accounts[{index}].account_id")

    for index, post in enumerate(tracker.get("posts") or []):
        _validate_post(post, f"posts[{index}]")
