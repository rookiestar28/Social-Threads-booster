#!/usr/bin/env python3
"""
Deterministic helpers for prediction report rendering and tracker persistence.
"""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import timedelta
from typing import Any

import tracker_utils


PREDICTED_METRICS = ("views", "likes", "replies", "reposts", "shares")
RANGE_KEYS = ("conservative", "baseline", "optimistic")


def validate_prediction_snapshot(snapshot: Any) -> None:
    if not isinstance(snapshot, dict):
        raise ValueError("prediction snapshot must be an object")
    for key in ("predicted_at", "data_path", "comparable_posts_used", "confidence_level", "ranges"):
        if key not in snapshot:
            raise ValueError(f"prediction snapshot missing {key}")
    if not isinstance(snapshot["ranges"], dict):
        raise ValueError("prediction ranges must be an object")

    range_keys = set(snapshot["ranges"])
    expected = set(PREDICTED_METRICS)
    if "quotes" in range_keys:
        raise ValueError("quotes must not be included in prediction ranges")
    if range_keys != expected:
        missing = ", ".join(sorted(expected - range_keys))
        extra = ", ".join(sorted(range_keys - expected))
        raise ValueError(f"prediction ranges mismatch; missing={missing or '-'} extra={extra or '-'}")

    for metric in PREDICTED_METRICS:
        band = snapshot["ranges"][metric]
        if not isinstance(band, dict):
            raise ValueError(f"ranges.{metric} must be an object")
        for key in RANGE_KEYS:
            if key not in band:
                raise ValueError(f"ranges.{metric}.{key} is required")
            if not isinstance(band[key], (int, float)) or isinstance(band[key], bool):
                raise ValueError(f"ranges.{metric}.{key} must be numeric")


def _metric_label(metric: str) -> str:
    return metric[:1].upper() + metric[1:]


def render_prediction_range_table(snapshot: dict) -> str:
    validate_prediction_snapshot(snapshot)
    lines = [
        "| Metric | Conservative | Baseline | Optimistic |",
        "|--------|--------------|----------|------------|",
    ]
    for metric in PREDICTED_METRICS:
        band = snapshot["ranges"][metric]
        lines.append(
            f"| {_metric_label(metric)} | {band['conservative']} | {band['baseline']} | {band['optimistic']} |"
        )
    return "\n".join(lines)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:40] or "draft"


def _pending_expires_at(now: str) -> str:
    parsed = tracker_utils.parse_iso_datetime(now)
    if parsed is None:
        parsed = tracker_utils.utc_now()
    return (parsed + timedelta(days=7)).isoformat()


def _find_post(tracker: dict, post_id: str | None) -> dict | None:
    if not post_id:
        return None
    for post in tracker.get("posts") or []:
        if str(post.get("id")) == str(post_id):
            return post
    return None


def _create_pending_post(tracker: dict, draft_text: str, snapshot: dict, now: str) -> dict:
    post_id = f"pending-{_slugify(draft_text)}"
    existing_ids = {str(post.get("id")) for post in tracker.get("posts") or []}
    base_id = post_id
    suffix = 2
    while post_id in existing_ids:
        post_id = f"{base_id}-{suffix}"
        suffix += 1

    post = tracker_utils.build_post_record(
        post_id=post_id,
        text=draft_text,
        created_at=now,
        source_path="prediction-placeholder",
        data_completeness="pending",
        prediction_snapshot=deepcopy(snapshot),
    )
    post["pending_expires_at"] = _pending_expires_at(now)
    tracker.setdefault("posts", []).insert(0, post)
    return post


def persist_prediction_snapshot(
    tracker: dict,
    snapshot: dict,
    *,
    post_id: str | None = None,
    draft_text: str | None = None,
    overwrite_policy: str = "no",
    now: str | None = None,
) -> dict:
    validate_prediction_snapshot(snapshot)
    if overwrite_policy not in {"no", "replace", "keep-both"}:
        raise ValueError("overwrite_policy must be no, replace, or keep-both")

    timestamp = now or tracker_utils.utc_now_iso()
    post = _find_post(tracker, post_id)
    created = False
    if post is None:
        if not draft_text:
            raise ValueError("post_id did not match and draft_text was not provided")
        post = _create_pending_post(tracker, draft_text, snapshot, timestamp)
        created = True
    else:
        existing_snapshot = post.get("prediction_snapshot")
        if existing_snapshot is not None:
            if overwrite_policy == "no":
                return {
                    "persisted": False,
                    "reason": "existing_prediction",
                    "post_id": post.get("id"),
                }
            if overwrite_policy == "keep-both":
                post.setdefault("prediction_snapshot_history", []).append(deepcopy(existing_snapshot))
        post["prediction_snapshot"] = deepcopy(snapshot)

    tracker["last_updated"] = timestamp
    tracker_utils.validate_tracker(tracker)
    return {
        "persisted": True,
        "created_pending": created,
        "post_id": post.get("id"),
        "overwrite_policy": overwrite_policy,
    }
