#!/usr/bin/env python3
"""
Load and normalize offline platform fixture payloads.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from platform_adapters import NormalizedComment, NormalizedMetrics, NormalizedPost, normalized_post_to_schema_post
from platform_schema import build_platform_tracker, validate_platform_tracker


class PlatformFixtureError(ValueError):
    """Raised when an offline platform fixture has invalid shape."""


@dataclass(frozen=True)
class PlatformFixture:
    platform: str
    account: dict[str, Any]
    capability_expectations: dict[str, Any]
    posts: list[dict[str, Any]]
    path: Path


def load_fixture(path: str | Path) -> PlatformFixture:
    fixture_path = Path(path)
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    for field in ("platform", "account", "capability_expectations", "posts"):
        if field not in payload:
            raise PlatformFixtureError(f"{fixture_path}: missing {field}")
    if not isinstance(payload["posts"], list) or not payload["posts"]:
        raise PlatformFixtureError(f"{fixture_path}: posts must be a non-empty array")
    return PlatformFixture(
        platform=str(payload["platform"]),
        account=dict(payload["account"]),
        capability_expectations=dict(payload["capability_expectations"]),
        posts=list(payload["posts"]),
        path=fixture_path,
    )


def load_fixture_corpus(directory: str | Path) -> list[PlatformFixture]:
    fixture_dir = Path(directory)
    fixtures = [load_fixture(path) for path in sorted(fixture_dir.glob("*.json"))]
    if not fixtures:
        raise PlatformFixtureError(f"no fixture files found in {fixture_dir}")
    return fixtures


def _normalize_comment(platform: str, account_id: str, payload: dict[str, Any]) -> NormalizedComment:
    return NormalizedComment(
        platform=platform,
        account_id=account_id,
        platform_comment_id=str(payload["id"]),
        text=str(payload.get("text", "")),
        created_at=str(payload.get("created_at", "")),
        author_id=payload.get("author_id"),
        metrics=NormalizedMetrics(**payload.get("metrics", {})),
        platform_metadata={platform: {"raw": dict(payload.get("raw", {}))}},
    )


def normalize_fixture_posts(fixture: PlatformFixture) -> list[NormalizedPost]:
    platform = fixture.platform
    account_id = str(fixture.account["account_id"])
    normalized: list[NormalizedPost] = []
    for payload in fixture.posts:
        comments = [
            _normalize_comment(platform, account_id, comment)
            for comment in payload.get("comments", [])
        ]
        normalized.append(
            NormalizedPost(
                platform=platform,
                account_id=account_id,
                platform_post_id=str(payload["id"]),
                text=str(payload.get("text", "")),
                created_at=str(payload.get("created_at", "")),
                content_format=str(payload.get("content_format", "text")),
                url=payload.get("url"),
                metrics=NormalizedMetrics(**payload.get("metrics", {})),
                comments=comments,
                source={"type": "fixture", "data_completeness": str(payload.get("data_completeness", "partial"))},
                platform_metadata={platform: {"raw": dict(payload.get("raw", {}))}},
            )
        )
    return normalized


def build_tracker_from_fixtures(fixtures: list[PlatformFixture]) -> dict[str, Any]:
    accounts = []
    posts = []
    for fixture in fixtures:
        accounts.append(
            {
                "platform": fixture.platform,
                "account_id": str(fixture.account["account_id"]),
                "display_name": fixture.account.get("display_name"),
            }
        )
        posts.extend(normalized_post_to_schema_post(post) for post in normalize_fixture_posts(fixture))

    tracker = build_platform_tracker(accounts=accounts, posts=posts)
    validate_platform_tracker(tracker)
    return tracker
