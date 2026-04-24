#!/usr/bin/env python3
"""
Deterministic Chrome-refresh seam helpers.

This module does not call browser/MCP tools. It only validates selector-health
results, normalizes already-extracted page data, and merges it into the tracker.
"""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import tracker_utils


CHECKPOINT_TARGETS = {
    "24h": 24.0,
    "72h": 72.0,
    "7d": 168.0,
}


class ChromeRefreshError(RuntimeError):
    def __init__(self, reason: str, detail: str):
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


def check_selector_health(post_card_count: int, *, login_wall_found: bool) -> bool:
    if post_card_count > 0:
        return True
    if login_wall_found:
        raise ChromeRefreshError("login_wall", "Threads login wall detected before post cards loaded")
    raise ChromeRefreshError("selector_health_failed", "No post cards matched the configured selector")


def parse_metric_token(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    match = re.fullmatch(r"(?i)(\d+(?:\.\d+)?)([km]?)", text)
    if not match:
        return None
    number = float(match.group(1))
    suffix = match.group(2).lower()
    if suffix == "k":
        number *= 1_000
    elif suffix == "m":
        number *= 1_000_000
    return int(number)


def _merge_metric(raw_metrics: dict, existing_metrics: dict, key: str) -> int:
    parsed = parse_metric_token(raw_metrics.get(key))
    if parsed is not None:
        return parsed
    existing = existing_metrics.get(key, 0)
    return int(existing) if isinstance(existing, (int, float)) and not isinstance(existing, bool) else 0


def normalize_scraped_post(raw: dict, *, existing_post: dict | None = None) -> dict:
    existing = existing_post or {}
    existing_metrics = existing.get("metrics") if isinstance(existing.get("metrics"), dict) else {}
    raw_metrics = raw.get("metrics") if isinstance(raw.get("metrics"), dict) else {}
    metrics = {
        key: _merge_metric(raw_metrics, existing_metrics, key)
        for key in ("views", "likes", "replies", "reposts", "quotes", "shares")
    }

    return tracker_utils.build_post_record(
        post_id=str(raw.get("id") or existing.get("id") or ""),
        text=str(raw.get("text") if raw.get("text") is not None else existing.get("text", "")),
        created_at=str(raw.get("created_at") or existing.get("created_at") or tracker_utils.utc_now_iso()),
        permalink=str(raw.get("permalink") or existing.get("permalink") or ""),
        media_type=str(raw.get("media_type") or existing.get("media_type") or "TEXT"),
        source_path="chrome-scrape",
        data_completeness="partial",
        content_type=existing.get("content_type") if existing else None,
        topics=existing.get("topics") if isinstance(existing.get("topics"), list) else None,
        hook_type=existing.get("hook_type"),
        ending_type=existing.get("ending_type"),
        emotional_arc=existing.get("emotional_arc"),
        algorithm_signals=existing.get("algorithm_signals") if isinstance(existing.get("algorithm_signals"), dict) else None,
        psychology_signals=existing.get("psychology_signals") if isinstance(existing.get("psychology_signals"), dict) else None,
        performance_windows=existing.get("performance_windows") if isinstance(existing.get("performance_windows"), dict) else None,
        snapshots=existing.get("snapshots") if isinstance(existing.get("snapshots"), list) else None,
        prediction_snapshot=existing.get("prediction_snapshot"),
        review_state=existing.get("review_state") if isinstance(existing.get("review_state"), dict) else None,
        comments=existing.get("comments") if isinstance(existing.get("comments"), list) else None,
        metrics=metrics,
        source_extra={
            key: value
            for key, value in (existing.get("source") or {}).items()
            if key not in {"import_path", "data_completeness"}
        },
    )


def _snapshot_distance(snapshot: dict, target_hours: float) -> float:
    hours = snapshot.get("hours_since_publish") if isinstance(snapshot, dict) else None
    if hours is None:
        return float("inf")
    return abs(hours - target_hours)


def _update_performance_windows(post: dict, snapshot: dict) -> None:
    performance_windows = post.setdefault("performance_windows", {})
    for key, target_hours in CHECKPOINT_TARGETS.items():
        new_distance = _snapshot_distance(snapshot, target_hours)
        if new_distance == float("inf"):
            continue
        if key == "24h" and new_distance > 12:
            continue
        if key == "72h" and new_distance > 24:
            continue
        if key == "7d" and new_distance > 48:
            continue
        current_distance = _snapshot_distance(performance_windows.get(key) or {}, target_hours)
        if performance_windows.get(key) is None or new_distance < current_distance:
            performance_windows[key] = snapshot


def _append_snapshot(post: dict, captured_at: str) -> None:
    snapshot = tracker_utils.build_metric_snapshot(post["metrics"], post["created_at"], captured_at=captured_at)
    snapshots = post.setdefault("snapshots", [])
    if snapshots and snapshots[-1].get("captured_at") == captured_at:
        snapshots[-1] = snapshot
    else:
        snapshots.append(snapshot)
    _update_performance_windows(post, snapshot)


def _merge_comments(existing: list, incoming: list) -> tuple[list, int]:
    known = {
        (str(item.get("user")), str(item.get("text")), str(item.get("created_at")))
        for item in existing
        if isinstance(item, dict)
    }
    merged = list(existing)
    added = 0
    for item in incoming:
        if not isinstance(item, dict):
            continue
        key = (str(item.get("user")), str(item.get("text")), str(item.get("created_at")))
        if key in known:
            continue
        known.add(key)
        merged.append(item)
        added += 1
    return merged, added


def _sweep_expired_pending_posts(tracker: dict, captured_at: str) -> int:
    captured_dt = tracker_utils.parse_iso_datetime(captured_at) or datetime.now(timezone.utc)
    kept = []
    discarded = tracker.setdefault("discarded_drafts", [])
    count = 0
    for post in tracker.get("posts") or []:
        post_id = str(post.get("id") or "")
        expires_at = tracker_utils.parse_iso_datetime(post.get("pending_expires_at"))
        if post_id.startswith("pending-") and expires_at is not None and expires_at < captured_dt:
            moved = deepcopy(post)
            moved["discarded_at"] = captured_at
            discarded.append(moved)
            count += 1
            continue
        kept.append(post)
    tracker["posts"] = kept
    return count


def merge_scraped_posts(
    tracker: dict,
    scraped_posts: list[dict],
    *,
    captured_at: str | None = None,
) -> dict:
    captured = captured_at or tracker_utils.utc_now_iso()
    discarded_count = _sweep_expired_pending_posts(tracker, captured)
    posts = tracker.setdefault("posts", [])
    by_id = {str(post.get("id")): post for post in posts}
    new_posts = 0
    updated_posts = 0
    replies_added = 0
    prediction_snapshots_merged = 0

    for raw in scraped_posts:
        post_id = str(raw.get("id") or "")
        if not post_id:
            continue
        existing = by_id.get(post_id)
        normalized = normalize_scraped_post(raw, existing_post=existing)
        incoming_comments = raw.get("comments") if isinstance(raw.get("comments"), list) else []

        if existing is None:
            placeholder_id = raw.get("prediction_placeholder_id")
            if placeholder_id:
                placeholder = next((post for post in posts if post.get("id") == placeholder_id), None)
                if placeholder and placeholder.get("prediction_snapshot") is not None:
                    normalized["prediction_snapshot"] = placeholder["prediction_snapshot"]
                    posts.remove(placeholder)
                    prediction_snapshots_merged += 1
            _append_snapshot(normalized, captured)
            normalized["comments"], added = _merge_comments(normalized.get("comments") or [], incoming_comments)
            replies_added += added
            posts.append(normalized)
            by_id[post_id] = normalized
            new_posts += 1
            continue

        previous_metrics = deepcopy(existing.get("metrics") or {})
        existing.update(normalized)
        existing["comments"], added = _merge_comments(existing.get("comments") or [], incoming_comments)
        replies_added += added
        if existing.get("metrics") != previous_metrics:
            _append_snapshot(existing, captured)
            updated_posts += 1

    tracker["posts"] = tracker_utils.sort_posts_newest_first(posts)
    tracker["last_updated"] = captured
    tracker_utils.validate_tracker(tracker)
    return {
        "posts_scraped": len(scraped_posts),
        "new_posts": new_posts,
        "updated_posts": updated_posts,
        "replies_added": replies_added,
        "discarded_drafts": discarded_count,
        "prediction_snapshots_merged": prediction_snapshots_merged,
    }
