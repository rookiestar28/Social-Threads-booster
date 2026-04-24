#!/usr/bin/env python3
"""
Shared JSON-line logging helpers for topic/draft freshness audits.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional

from tracker_utils import utc_now_iso
from log_redaction import sanitize_log_value


ALLOWED_STATUS = {"performed", "unavailable", "skipped_by_user"}
ALLOWED_OUTCOME = {"green", "yellow", "red"}
ALLOWED_DISCUSSION_MODE = {"fast", "discussion", "auto"}
MAX_AUDIT_TAGS = 12
MAX_AUDIT_TAG_LENGTH = 64


def new_run_id() -> str:
    return str(uuid.uuid4())


def _validate_status(status: str) -> str:
    if status not in ALLOWED_STATUS:
        raise ValueError(f"invalid status: {status}")
    return status


def _validate_outcome(outcome: str) -> str:
    if outcome not in ALLOWED_OUTCOME:
        raise ValueError(f"invalid outcome: {outcome}")
    return outcome


def _validate_discussion_mode(mode: str) -> str:
    if mode not in ALLOWED_DISCUSSION_MODE:
        raise ValueError(f"invalid discussion_mode: {mode}")
    return mode


def _normalize_audit_tags(values: Optional[list[str]]) -> list[str]:
    tags = []
    for value in values or []:
        tag = str(value or "").strip().lower().replace(" ", "_")
        tag = "".join(ch for ch in tag if ch.isalnum() or ch in {"_", "-"})
        if tag:
            tags.append(tag[:MAX_AUDIT_TAG_LENGTH])
        if len(tags) >= MAX_AUDIT_TAGS:
            break
    return tags


def build_topics_freshness_entry(
    *,
    candidate: str,
    status: str,
    verdict: str,
    web_search_query: Optional[str],
    run_id: Optional[str] = None,
    ts: Optional[str] = None,
) -> dict:
    return {
        "ts": ts or utc_now_iso(),
        "run_id": run_id or new_run_id(),
        "skill": "topics",
        "candidate": candidate,
        "status": _validate_status(status),
        "verdict": _validate_outcome(verdict),
        "web_search_query": web_search_query,
    }


def build_draft_freshness_entry(
    *,
    topic: str,
    status: str,
    decision: str,
    web_search_query: Optional[str],
    run_id: Optional[str] = None,
    ts: Optional[str] = None,
    discussion_mode: Optional[str] = None,
    discussion_ran: Optional[bool] = None,
    user_decisions: Optional[list[str]] = None,
    personal_fact_conflicts: Optional[list[str]] = None,
) -> dict:
    entry = {
        "ts": ts or utc_now_iso(),
        "run_id": run_id or new_run_id(),
        "skill": "draft",
        "topic": topic,
        "status": _validate_status(status),
        "decision": _validate_outcome(decision),
        "web_search_query": web_search_query,
    }
    if discussion_mode is not None:
        entry["discussion_mode"] = _validate_discussion_mode(discussion_mode)
    if discussion_ran is not None:
        entry["discussion_ran"] = bool(discussion_ran)

    normalized_decisions = _normalize_audit_tags(user_decisions)
    if normalized_decisions:
        entry["user_decisions"] = normalized_decisions

    normalized_conflicts = _normalize_audit_tags(personal_fact_conflicts)
    if normalized_conflicts:
        entry["personal_fact_conflicts"] = normalized_conflicts

    return entry


def append_freshness_log(log_path: str | Path, entry: dict) -> Path:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sanitized_entry = sanitize_log_value(entry)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(sanitized_entry, ensure_ascii=False, separators=(",", ":")))
        fh.write("\n")
    return path
