#!/usr/bin/env python3
"""
Shared tracker IO, scaffold, and mutation utilities for AK-Threads-Booster.
"""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def parse_iso_datetime(timestamp: str | None) -> Optional[datetime]:
    if not timestamp:
        return None

    try:
        return datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except ValueError:
        return None


def classify_content_type(text: str) -> str:
    if not text:
        return "other"

    stripped = text.strip()
    if "?" in text or "？" in text:
        if stripped.endswith("?") or stripped.endswith("？"):
            return "question"
    if any(marker in text for marker in ["1.", "2.", "3.", "一、", "二、", "第一", "步驟"]):
        return "tutorial"
    if any(marker in text for marker in ["數據", "data", "%", "成長", "增長"]):
        return "data-insight"
    if any(marker in text for marker in ["我的經驗", "我之前", "那時候", "故事"]):
        return "story"
    return "opinion"


def count_words(text: str) -> int:
    return len(text.split()) if text else 0


def count_paragraphs(text: str) -> int:
    if not text:
        return 0
    return len([chunk for chunk in text.splitlines() if chunk.strip()])


def build_posting_time_slot(timestamp: str | None) -> Optional[str]:
    dt = parse_iso_datetime(timestamp)
    if dt is None:
        return None

    hour = dt.hour
    if hour < 6:
        window = "00:00-05:59"
    elif hour < 12:
        window = "06:00-11:59"
    elif hour < 18:
        window = "12:00-17:59"
    else:
        window = "18:00-23:59"

    return f"{dt.strftime('%a')} {window}"


def build_algorithm_signals() -> dict:
    return {
        "discovery_surface": {
            "threads": None,
            "instagram": None,
            "facebook": None,
            "profile": None,
            "topic_feed": None,
            "other": None,
        },
        "topic_graph": {
            "topic_tag_used": None,
            "topic_tag_count": None,
            "topic_match_clarity": None,
            "single_topic_clarity": None,
            "bio_topic_match": None,
        },
        "topic_freshness": {
            "semantic_cluster": None,
            "similar_recent_posts": None,
            "recent_cluster_frequency": None,
            "days_since_last_similar_post": None,
            "freshness_score": None,
            "fatigue_risk": None,
        },
        "originality_risk": {
            "caption_content_mismatch": None,
            "hashtag_stuffing_risk": None,
            "duplicate_cluster_risk": None,
            "minor_edit_repost_risk": None,
            "low_value_reaction_risk": None,
            "fake_engagement_pattern_risk": None,
        },
    }


def build_psychology_signals() -> dict:
    return {
        "hook_payoff": {
            "hook_strength": None,
            "payoff_strength": None,
            "hook_payoff_gap": None,
        },
        "share_motive_split": {
            "dm_forwardability": None,
            "public_repostability": None,
            "identity_signal_strength": None,
            "utility_share_strength": None,
        },
        "retellability": None,
    }


def build_review_state() -> dict:
    return {
        "last_reviewed_at": None,
        "actual_checkpoint_hours": None,
        "deviation_summary": None,
        "calibration_notes": [],
        "validated_signals": {
            "discovery_surface_notes": None,
            "topic_graph_notes": None,
            "topic_freshness_notes": None,
            "originality_risk_notes": None,
            "hook_payoff_gap_notes": None,
            "share_motive_split_notes": None,
            "retellability_notes": None,
        },
    }


def build_metrics(metrics: Optional[dict[str, Any]] = None) -> dict:
    base = {
        "views": 0,
        "likes": 0,
        "replies": 0,
        "reposts": 0,
        "quotes": 0,
        "shares": 0,
    }
    if metrics:
        for key, value in metrics.items():
            base[key] = value
    return base


def build_performance_windows() -> dict:
    return {
        "24h": None,
        "72h": None,
        "7d": None,
    }


def build_metric_snapshot(metrics: dict, created_at: str, captured_at: Optional[str] = None) -> dict:
    captured = captured_at or utc_now_iso()
    created_dt = parse_iso_datetime(created_at)
    captured_dt = parse_iso_datetime(captured)
    hours_since_publish = None

    if created_dt and captured_dt:
        delta = captured_dt - created_dt
        hours_since_publish = round(delta.total_seconds() / 3600, 2)

    normalized_metrics = build_metrics(metrics)
    return {
        "captured_at": captured,
        "hours_since_publish": hours_since_publish,
        "views": normalized_metrics["views"],
        "likes": normalized_metrics["likes"],
        "replies": normalized_metrics["replies"],
        "reposts": normalized_metrics["reposts"],
        "quotes": normalized_metrics["quotes"],
        "shares": normalized_metrics["shares"],
    }


def build_post_record(
    *,
    post_id: str,
    text: str,
    created_at: str,
    source_path: str,
    data_completeness: str,
    permalink: str = "",
    media_type: str = "TEXT",
    is_reply_post: bool = False,
    content_type: Optional[str] = None,
    topics: Optional[list] = None,
    hook_type: Any = None,
    ending_type: Any = None,
    emotional_arc: Any = None,
    word_count: Optional[int] = None,
    paragraph_count: Optional[int] = None,
    posting_time_slot: Optional[str] = None,
    algorithm_signals: Optional[dict] = None,
    psychology_signals: Optional[dict] = None,
    metrics: Optional[dict] = None,
    performance_windows: Optional[dict] = None,
    snapshots: Optional[list] = None,
    prediction_snapshot: Any = None,
    review_state: Optional[dict] = None,
    comments: Optional[list] = None,
    source_extra: Optional[dict] = None,
) -> dict:
    source = {
        "import_path": source_path,
        "data_completeness": data_completeness,
    }
    if source_extra:
        source.update(source_extra)

    return {
        "id": str(post_id),
        "text": text,
        "created_at": created_at,
        "permalink": permalink,
        "media_type": media_type,
        "is_reply_post": is_reply_post,
        "content_type": content_type if content_type is not None else classify_content_type(text),
        "topics": list(topics or []),
        "hook_type": hook_type,
        "ending_type": ending_type,
        "emotional_arc": emotional_arc,
        "word_count": word_count if word_count is not None else count_words(text),
        "paragraph_count": paragraph_count if paragraph_count is not None else count_paragraphs(text),
        "posting_time_slot": posting_time_slot if posting_time_slot is not None else build_posting_time_slot(created_at),
        "algorithm_signals": deepcopy(algorithm_signals) if algorithm_signals is not None else build_algorithm_signals(),
        "psychology_signals": deepcopy(psychology_signals) if psychology_signals is not None else build_psychology_signals(),
        "metrics": build_metrics(metrics),
        "performance_windows": deepcopy(performance_windows) if performance_windows is not None else build_performance_windows(),
        "snapshots": list(snapshots or []),
        "prediction_snapshot": prediction_snapshot,
        "review_state": deepcopy(review_state) if review_state is not None else build_review_state(),
        "comments": list(comments or []),
        "source": source,
    }


def _merge_missing(target: dict, defaults: dict) -> None:
    for key, value in defaults.items():
        if key not in target:
            target[key] = deepcopy(value)
            continue

        if isinstance(target[key], dict) and isinstance(value, dict):
            _merge_missing(target[key], value)


def hydrate_post_defaults(post: dict) -> None:
    defaults = build_post_record(
        post_id=str(post.get("id", "")),
        text=str(post.get("text", "")),
        created_at=str(post.get("created_at", "")),
        source_path=str((post.get("source") or {}).get("import_path") or "unknown"),
        data_completeness=str((post.get("source") or {}).get("data_completeness") or "partial"),
        permalink=str(post.get("permalink", "")),
        media_type=str(post.get("media_type", "TEXT")),
        is_reply_post=bool(post.get("is_reply_post", False)),
        content_type=post.get("content_type"),
        topics=post.get("topics") if isinstance(post.get("topics"), list) else None,
        hook_type=post.get("hook_type"),
        ending_type=post.get("ending_type"),
        emotional_arc=post.get("emotional_arc"),
        word_count=post.get("word_count") if isinstance(post.get("word_count"), int) else None,
        paragraph_count=post.get("paragraph_count") if isinstance(post.get("paragraph_count"), int) else None,
        posting_time_slot=post.get("posting_time_slot"),
        algorithm_signals=post.get("algorithm_signals") if isinstance(post.get("algorithm_signals"), dict) else None,
        psychology_signals=post.get("psychology_signals") if isinstance(post.get("psychology_signals"), dict) else None,
        metrics=post.get("metrics") if isinstance(post.get("metrics"), dict) else None,
        performance_windows=post.get("performance_windows") if isinstance(post.get("performance_windows"), dict) else None,
        snapshots=post.get("snapshots") if isinstance(post.get("snapshots"), list) else None,
        prediction_snapshot=post.get("prediction_snapshot"),
        review_state=post.get("review_state") if isinstance(post.get("review_state"), dict) else None,
        comments=post.get("comments") if isinstance(post.get("comments"), list) else None,
        source_extra={
            key: value
            for key, value in (post.get("source") or {}).items()
            if key not in {"import_path", "data_completeness"}
        },
    )
    _merge_missing(post, defaults)


def build_empty_tracker(
    *,
    account_handle: str = "",
    source: str = "api",
    timezone_name: str = "UTC",
    posts: Optional[list] = None,
    last_updated: Optional[str] = None,
) -> dict:
    return {
        "account": {
            "handle": account_handle,
            "source": source,
            "timezone": timezone_name,
        },
        "posts": list(posts or []),
        "last_updated": last_updated or utc_now_iso(),
    }


def sort_posts_newest_first(posts: list[dict]) -> list[dict]:
    return sorted(
        posts,
        key=lambda post: parse_iso_datetime(post.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )


def load_tracker(path: str | Path) -> dict:
    tracker_path = Path(path)
    if not tracker_path.exists():
        raise FileNotFoundError(f"tracker not found: {tracker_path}")

    tracker = json.loads(tracker_path.read_text(encoding="utf-8"))
    posts = tracker.get("posts")
    if not isinstance(posts, list):
        raise ValueError("tracker posts field must be an array")
    return tracker


def save_tracker(path: str | Path, tracker: dict) -> Path:
    tracker_path = Path(path)
    tracker_path.parent.mkdir(parents=True, exist_ok=True)
    tracker_path.write_text(json.dumps(tracker, ensure_ascii=False, indent=2), encoding="utf-8")
    return tracker_path


def backup_tracker(path: str | Path, keep: int = 5, stamp: Optional[str] = None) -> Optional[Path]:
    tracker_path = Path(path)
    if not tracker_path.exists():
        return None

    backup_stamp = stamp or utc_now().strftime("%Y%m%dT%H%M%SZ")
    backup_path = tracker_path.with_name(f"{tracker_path.name}.bak-{backup_stamp}")
    shutil.copy2(tracker_path, backup_path)

    backups = sorted(
        tracker_path.parent.glob(f"{tracker_path.name}.bak-*"),
        key=lambda candidate: candidate.name,
        reverse=True,
    )
    for stale in backups[keep:]:
        try:
            stale.unlink()
        except OSError:
            pass

    return backup_path
