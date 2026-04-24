#!/usr/bin/env python3
"""
Core helpers for migrating pre-v1 tracker data into the current tracker schema.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from tracker_utils import (
    build_empty_tracker,
    build_metric_snapshot,
    build_post_record,
    parse_iso_datetime,
    sort_posts_newest_first,
    utc_now_iso,
    validate_tracker,
)


POST_ARCHIVE_RE = re.compile(
    r"(?ms)^###\s+(?P<date>\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2})?).*?\n(?P<body>.*?)(?=^---\s*$|\Z)"
)
COMMENT_ARCHIVE_RE = POST_ARCHIVE_RE


def normalize_legacy_datetime(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return utc_now_iso()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}$", text):
        text = f"{text}T00:00:00+00:00"
    elif re.fullmatch(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}$", text):
        text = text.replace(" ", "T") + ":00+00:00"
    elif text.endswith("Z"):
        text = text[:-1] + "+00:00"
    else:
        parsed = parse_iso_datetime(text)
        if parsed is None and "T" not in text and " " in text:
            text = text.replace(" ", "T")
        parsed = parse_iso_datetime(text)
        if parsed is None:
            return utc_now_iso()
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat()

    parsed = parse_iso_datetime(text)
    if parsed is None:
        return utc_now_iso()
    return parsed.isoformat()


def _iter_legacy_posts(payload: dict) -> list[tuple[str, dict]]:
    posts = payload.get("posts")
    if isinstance(posts, dict):
        return [(str(post_id), post if isinstance(post, dict) else {}) for post_id, post in posts.items()]
    if isinstance(posts, list):
        return [(str(post.get("id") or f"legacy-{idx + 1}"), post) for idx, post in enumerate(posts) if isinstance(post, dict)]
    return []


def is_legacy_tracker(payload: dict) -> bool:
    if not isinstance(payload, dict):
        return False
    if isinstance(payload.get("posts"), dict):
        return True
    if "_meta" in payload and "account" not in payload:
        return True
    for _, post in _iter_legacy_posts(payload):
        if "data_snapshots" in post and "metrics" not in post:
            return True
        if isinstance(post.get("my_replies"), list):
            return True
    return False


def _snapshot_metrics(snapshot: dict) -> dict:
    return {
        "views": snapshot.get("views", 0),
        "likes": snapshot.get("likes", 0),
        "replies": snapshot.get("replies", snapshot.get("replies_count", 0)),
        "reposts": snapshot.get("reposts", 0),
        "quotes": snapshot.get("quotes", 0),
        "shares": snapshot.get("shares", 0),
    }


def _migrate_snapshots(legacy_post: dict, created_at: str) -> tuple[list[dict], dict]:
    snapshots = []
    for snapshot in legacy_post.get("data_snapshots") or []:
        if not isinstance(snapshot, dict):
            continue
        captured_at = normalize_legacy_datetime(snapshot.get("snapshot_date") or snapshot.get("captured_at"))
        metrics = _snapshot_metrics(snapshot)
        snapshots.append(build_metric_snapshot(metrics, created_at, captured_at=captured_at))

    latest_metrics = _snapshot_metrics(legacy_post.get("data_snapshots", [])[-1]) if legacy_post.get("data_snapshots") else {}
    return snapshots, latest_metrics


def _build_report(last_updated: str) -> dict:
    return {
        "posts_migrated": 0,
        "posts_added_from_markdown": 0,
        "author_replies_preserved": 0,
        "comments_attached": 0,
        "unmatched_comments": 0,
        "thin_text_posts": 0,
        "last_updated": last_updated,
    }


def _parse_markdown_blocks(markdown: str | None) -> list[dict]:
    if not markdown:
        return []
    blocks = []
    for match in POST_ARCHIVE_RE.finditer(markdown):
        raw_body = match.group("body").strip()
        body_lines = []
        topic = None
        for line in raw_body.splitlines():
            stripped = line.strip()
            if stripped.startswith("**分類：**"):
                topic = stripped.replace("**分類：**", "").strip()
                continue
            body_lines.append(line)
        body = "\n".join(body_lines).strip()
        if body:
            blocks.append(
                {
                    "created_at": normalize_legacy_datetime(match.group("date")),
                    "topic": topic,
                    "body": body,
                }
            )
    return blocks


def _is_thin_text(post: dict) -> bool:
    title = str(post.get("title") or "").strip()
    text = str(post.get("text") or "").strip()
    return bool(text) and (text == title or len(text) < 80)


def _find_nearest_post(posts: list[dict], created_at: str, *, max_delta: timedelta, require_prior: bool = False) -> dict | None:
    target = parse_iso_datetime(created_at)
    if target is None:
        return None
    best_post = None
    best_delta = max_delta
    for post in posts:
        post_dt = parse_iso_datetime(post.get("created_at"))
        if post_dt is None:
            continue
        delta = target - post_dt if require_prior else abs(target - post_dt)
        if require_prior and delta.total_seconds() < 0:
            continue
        if delta <= best_delta:
            best_delta = delta
            best_post = post
    return best_post


def enrich_posts_from_markdown(tracker: dict, posts_markdown: str | None, report: dict) -> None:
    for block in _parse_markdown_blocks(posts_markdown):
        match = _find_nearest_post(
            tracker["posts"],
            block["created_at"],
            max_delta=timedelta(minutes=60),
        )
        if match is not None:
            if _is_thin_text(match):
                match.setdefault("title", match.get("text", ""))
                match["text"] = block["body"]
            continue

        topics = [block["topic"]] if block.get("topic") else []
        tracker["posts"].append(
            build_post_record(
                post_id=f"legacy-md-{len(tracker['posts']) + 1}",
                text=block["body"],
                created_at=block["created_at"],
                source_path="legacy-markdown",
                data_completeness="text-only",
                topics=topics,
            )
        )
        report["posts_added_from_markdown"] += 1


def enrich_comments_from_markdown(tracker: dict, comments_markdown: str | None, report: dict) -> None:
    tracker.setdefault("unmatched_comments", [])
    for block in _parse_markdown_blocks(comments_markdown):
        comment = {
            "user": None,
            "text": block["body"],
            "created_at": block["created_at"],
            "likes": 0,
        }
        match = _find_nearest_post(
            tracker["posts"],
            block["created_at"],
            max_delta=timedelta(hours=72),
            require_prior=True,
        )
        if match is None:
            tracker["unmatched_comments"].append(comment)
            report["unmatched_comments"] += 1
            continue
        match.setdefault("comments", []).append(comment)
        report["comments_attached"] += 1


def migrate_legacy_tracker(
    payload: dict,
    *,
    posts_markdown: str | None = None,
    comments_markdown: str | None = None,
) -> tuple[dict, dict]:
    meta = payload.get("_meta") if isinstance(payload.get("_meta"), dict) else {}
    last_updated = normalize_legacy_datetime(meta.get("last_updated") or payload.get("last_updated"))
    tracker = build_empty_tracker(
        account_handle=str(meta.get("account") or ""),
        source="legacy-migration",
        timezone_name="UTC",
        posts=[],
        last_updated=last_updated,
    )
    report = _build_report(last_updated)

    for post_id, legacy_post in _iter_legacy_posts(payload):
        created_at = normalize_legacy_datetime(legacy_post.get("date") or legacy_post.get("created_at"))
        snapshots, metrics = _migrate_snapshots(legacy_post, created_at)
        title = str(legacy_post.get("title") or legacy_post.get("text") or "").strip()
        topics = [legacy_post["topic"]] if isinstance(legacy_post.get("topic"), str) and legacy_post.get("topic").strip() else []
        migrated = build_post_record(
            post_id=post_id,
            text=title,
            created_at=created_at,
            source_path="legacy-tracker",
            data_completeness="legacy-partial",
            content_type=legacy_post.get("type"),
            topics=topics,
            metrics=metrics,
            snapshots=snapshots,
        )
        if title:
            migrated["title"] = title
        if isinstance(legacy_post.get("my_replies"), list):
            migrated["author_replies"] = list(legacy_post.get("my_replies") or [])
            migrated["my_replies"] = bool(migrated["author_replies"])
            report["author_replies_preserved"] += len(migrated["author_replies"])
        tracker["posts"].append(migrated)
        report["posts_migrated"] += 1

    enrich_posts_from_markdown(tracker, posts_markdown, report)
    enrich_comments_from_markdown(tracker, comments_markdown, report)
    tracker["posts"] = sort_posts_newest_first(tracker["posts"])
    report["thin_text_posts"] = sum(1 for post in tracker["posts"] if _is_thin_text(post))

    validate_tracker(tracker)
    return tracker, report
