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


ALLOWED_STATUS = {"performed", "unavailable", "skipped_by_user"}
ALLOWED_OUTCOME = {"green", "yellow", "red"}


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
) -> dict:
    return {
        "ts": ts or utc_now_iso(),
        "run_id": run_id or new_run_id(),
        "skill": "draft",
        "topic": topic,
        "status": _validate_status(status),
        "decision": _validate_outcome(decision),
        "web_search_query": web_search_query,
    }


def append_freshness_log(log_path: str | Path, entry: dict) -> Path:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")))
        fh.write("\n")
    return path
