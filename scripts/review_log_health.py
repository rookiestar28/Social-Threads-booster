#!/usr/bin/env python3
"""
Shared readers and summarizers for refresh/freshness audit logs.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


def parse_iso_datetime(timestamp: str | None) -> Optional[datetime]:
    if not timestamp:
        return None
    try:
        return datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except ValueError:
        return None


def load_jsonl_entries(path: str | Path) -> tuple[list[dict], int]:
    entries: list[dict] = []
    malformed = 0
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(payload, dict):
            entries.append(payload)
        else:
            malformed += 1
    return entries, malformed


def _freshness_group_key(entry: dict) -> str:
    run_id = str(entry.get("run_id") or "").strip()
    if run_id:
        return run_id
    dt = parse_iso_datetime(entry.get("ts"))
    if dt is None:
        return "unknown-minute"
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")


def summarize_freshness_log(
    entries: list[dict],
    *,
    current_topic_slug: str | None = None,
    recent_limit: int = 30,
) -> dict:
    recent_entries = entries[-recent_limit:]
    grouped: dict[str, list[dict]] = defaultdict(list)
    for entry in recent_entries:
        grouped[_freshness_group_key(entry)].append(entry)

    healthy_runs = 0
    degraded_runs = 0
    current_topic_seen = False

    for run_entries in grouped.values():
        statuses = {str(entry.get("status") or "") for entry in run_entries}
        if "performed" in statuses:
            healthy_runs += 1
        elif statuses and statuses.issubset({"unavailable", "skipped_by_user"}):
            degraded_runs += 1

        if current_topic_slug:
            for entry in run_entries:
                if entry.get("candidate") == current_topic_slug or entry.get("topic") == current_topic_slug:
                    current_topic_seen = True
                    break

    total_runs = len(grouped)
    degraded_ratio = (degraded_runs / total_runs) if total_runs else 0.0

    return {
        "total_runs": total_runs,
        "healthy_runs": healthy_runs,
        "degraded_runs": degraded_runs,
        "degraded_ratio": round(degraded_ratio, 4),
        "degraded_warning": degraded_ratio > 0.3,
        "current_topic_seen": current_topic_seen,
    }


def summarize_refresh_log(
    entries: list[dict],
    *,
    now: Optional[datetime] = None,
    recent_limit: int = 30,
) -> dict:
    recent_entries = entries[-recent_limit:]
    ok_runs = sum(1 for entry in recent_entries if bool(entry.get("ok")) is True)
    failed_entries = [entry for entry in recent_entries if bool(entry.get("ok")) is False]
    failed_runs = len(failed_entries)
    total_runs = len(recent_entries)
    failure_reasons = Counter(str(entry.get("reason") or "other") for entry in failed_entries)

    now_utc = now or datetime.now(timezone.utc)
    success_times = [
        parsed
        for entry in recent_entries
        if bool(entry.get("ok")) is True
        for parsed in [parse_iso_datetime(entry.get("ts"))]
        if parsed is not None
    ]
    last_success_at = max(success_times) if success_times else None
    hours_since_last_success = None
    if last_success_at is not None:
        hours_since_last_success = round((now_utc - last_success_at).total_seconds() / 3600, 2)

    recent_selector_health_failed = any(
        str(entry.get("reason") or "") == "selector_health_failed"
        for entry in recent_entries[-5:]
        if bool(entry.get("ok")) is False
    )
    failed_ratio = (failed_runs / total_runs) if total_runs else 0.0

    return {
        "total_runs": total_runs,
        "ok_runs": ok_runs,
        "failed_runs": failed_runs,
        "failed_ratio": round(failed_ratio, 4),
        "degraded_warning": failed_ratio > 0.3,
        "last_success_at": last_success_at.isoformat() if last_success_at else None,
        "hours_since_last_success": hours_since_last_success,
        "stale_warning": hours_since_last_success is not None and hours_since_last_success > 48,
        "recent_selector_health_failed": recent_selector_health_failed,
        "dominant_failure_reasons": dict(failure_reasons.most_common()),
    }


def summarize_log_health(
    *,
    refresh_log_path: str | Path | None = None,
    freshness_log_path: str | Path | None = None,
    current_topic_slug: str | None = None,
) -> dict:
    summary: dict[str, dict | None] = {
        "refresh": None,
        "freshness": None,
    }

    if refresh_log_path and Path(refresh_log_path).exists():
        refresh_entries, refresh_malformed = load_jsonl_entries(refresh_log_path)
        refresh_summary = summarize_refresh_log(refresh_entries)
        refresh_summary["malformed_lines"] = refresh_malformed
        summary["refresh"] = refresh_summary

    if freshness_log_path and Path(freshness_log_path).exists():
        freshness_entries, freshness_malformed = load_jsonl_entries(freshness_log_path)
        freshness_summary = summarize_freshness_log(
            freshness_entries,
            current_topic_slug=current_topic_slug,
        )
        freshness_summary["malformed_lines"] = freshness_malformed
        summary["freshness"] = freshness_summary

    return summary
