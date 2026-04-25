#!/usr/bin/env python3
"""
Reddit platform adapter for submissions and comments.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from capability_registry import CapabilityRegistry
from credential_sources import CredentialSourceError, resolve_credential
from platform_adapters import CapabilityReport, NormalizedComment, NormalizedMetrics, NormalizedPost, PublishResult

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


POLICY_PATH = REPO_ROOT / "knowledge" / "platform_api_policy.json"
REDDIT_API_BASE = "https://oauth.reddit.com"
USER_AGENT = "Social-Threads-Booster/1.0"


class RedditAdapterCredentialError(ValueError):
    """Raised when Reddit adapter operations need credentials."""


class RedditClient(Protocol):
    def list_submissions(self, account_id: str, token: str) -> list[dict]:
        ...

    def fetch_submission(self, submission_id: str, token: str) -> dict:
        ...

    def fetch_comments(self, submission_id: str, token: str) -> list[dict]:
        ...


def _to_number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str) and value.strip():
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            return None
    return None


def _created_at(value: Any) -> str:
    number = _to_number(value)
    if number is None:
        return str(value or "")
    return datetime.fromtimestamp(float(number), tz=timezone.utc).isoformat()


def _reddit_username(account_id: str) -> str:
    value = account_id.removeprefix("reddit:")
    return value.removeprefix("u_").removeprefix("u/")


@dataclass(frozen=True)
class RequestsRedditClient:
    """Small OAuth Reddit client for optional live smoke paths."""

    def _get(self, path: str, *, token: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if requests is None:
            raise RuntimeError("requests package is required for live Reddit API calls")
        resp = requests.get(
            f"{REDDIT_API_BASE}/{path.lstrip('/')}",
            params=params or {},
            headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def list_submissions(self, account_id: str, token: str) -> list[dict]:
        username = _reddit_username(account_id)
        payload = self._get(f"user/{username}/submitted", token=token, params={"limit": 50, "raw_json": 1})
        return [
            item.get("data")
            for item in ((payload.get("data") or {}).get("children") or [])
            if isinstance(item, dict) and isinstance(item.get("data"), dict)
        ]

    def fetch_submission(self, submission_id: str, token: str) -> dict:
        payload = self._get(f"comments/{submission_id}", token=token, params={"limit": 1, "raw_json": 1})
        listing = payload[0] if isinstance(payload, list) and payload else {}
        children = ((listing.get("data") or {}).get("children") or []) if isinstance(listing, dict) else []
        if not children:
            raise KeyError(f"Reddit submission not found: {submission_id}")
        return dict(children[0].get("data") or {})

    def fetch_comments(self, submission_id: str, token: str) -> list[dict]:
        payload = self._get(f"comments/{submission_id}", token=token, params={"limit": 100, "raw_json": 1})
        listing = payload[1] if isinstance(payload, list) and len(payload) > 1 else {}
        children = ((listing.get("data") or {}).get("children") or []) if isinstance(listing, dict) else []
        return [
            item.get("data")
            for item in children
            if isinstance(item, dict) and isinstance(item.get("data"), dict)
        ]


def reddit_metrics(submission: dict[str, Any]) -> NormalizedMetrics:
    return NormalizedMetrics(
        view_count=None,
        reaction_count=_to_number(submission.get("score")),
        comment_count=_to_number(submission.get("num_comments")),
        share_count=None,
    )


def normalize_reddit_comment(comment: dict[str, Any], *, account_id: str, submission_id: str, index: int = 0) -> NormalizedComment:
    comment_id = str(comment.get("id") or f"{submission_id}:comment:{index}")
    return NormalizedComment(
        platform="reddit",
        account_id=account_id,
        platform_comment_id=comment_id,
        text=str(comment.get("body") or comment.get("text") or ""),
        created_at=_created_at(comment.get("created_utc") or comment.get("created_at")),
        author_id=comment.get("author"),
        metrics=NormalizedMetrics(reaction_count=_to_number(comment.get("score"))),
        platform_metadata={"reddit": {"raw": dict(comment)}},
    )


def normalize_reddit_submission(
    submission: dict[str, Any],
    *,
    account_id: str,
    comments: list[dict[str, Any]] | None = None,
) -> NormalizedPost:
    submission_id = str(submission.get("id", "")).strip()
    if not submission_id:
        raise ValueError("Reddit submission id is required")
    title = str(submission.get("title") or "")
    body = str(submission.get("selftext") or submission.get("body") or "")
    text = title if not body else f"{title}\n\n{body}"
    normalized_comments = [
        normalize_reddit_comment(comment, account_id=account_id, submission_id=submission_id, index=index)
        for index, comment in enumerate(comments or [])
        if isinstance(comment, dict)
    ]
    return NormalizedPost(
        platform="reddit",
        account_id=account_id,
        platform_post_id=submission_id,
        canonical_post_id=f"reddit:{account_id}:{submission_id}",
        text=text,
        created_at=_created_at(submission.get("created_utc") or submission.get("created_at")),
        content_format=str(submission.get("content_format") or "forum_post"),
        url=submission.get("url") or f"https://www.reddit.com{submission.get('permalink', '')}",
        metrics=reddit_metrics(submission),
        comments=normalized_comments,
        source={"type": "adapter", "data_completeness": "full" if comments is not None else "partial"},
        platform_metadata={"reddit": {"raw": {"submission": dict(submission)}}},
    )


class RedditPlatformAdapter:
    platform = "reddit"

    def __init__(
        self,
        *,
        account_id: str,
        token: str | None = None,
        token_file: str | None = None,
        client: RedditClient | None = None,
        policy_path: str | Path = POLICY_PATH,
    ) -> None:
        self.account_id = account_id
        self._token = token
        self._token_file = token_file
        self._client = client or RequestsRedditClient()
        self._policy_path = Path(policy_path)

    def _resolve_token(self) -> str:
        try:
            source = resolve_credential(
                label="Reddit OAuth token",
                direct_value=self._token,
                direct_source_name="RedditPlatformAdapter(token=...)",
                env_var="REDDIT_OAUTH_TOKEN",
                file_path=self._token_file,
            )
        except CredentialSourceError as exc:
            raise RedditAdapterCredentialError(str(exc)) from exc
        if not source.value:
            raise RedditAdapterCredentialError(
                "missing Reddit OAuth token; set REDDIT_OAUTH_TOKEN or pass token_file"
            )
        return source.value

    def capabilities(self) -> CapabilityReport:
        registry = CapabilityRegistry.from_policy_file(self._policy_path)
        read_posts = registry.decide("reddit", "read_posts")
        read_comments = registry.decide("reddit", "read_comments")
        refresh = registry.decide("reddit", "refresh_snapshots")
        publish = registry.decide("reddit", "publish_text")
        return CapabilityReport(
            platform="reddit",
            can_import_history=read_posts.allowed,
            can_refresh_metrics=refresh.allowed,
            can_fetch_comments=read_comments.allowed,
            can_publish=False,
            supported_metrics=("reaction_count", "comment_count"),
            auth_required=True,
            notes=(read_posts.gate, read_comments.gate, refresh.gate, f"publish_text: {publish.status} ({publish.gate})"),
        )

    def list_posts(self) -> list[NormalizedPost]:
        token = self._resolve_token()
        posts = []
        for submission in self._client.list_submissions(self.account_id, token):
            submission_id = str(submission.get("id", ""))
            comments = self._client.fetch_comments(submission_id, token)
            posts.append(normalize_reddit_submission(submission, account_id=self.account_id, comments=comments))
        return posts

    def refresh_metrics(self, platform_post_id: str) -> NormalizedMetrics:
        token = self._resolve_token()
        return reddit_metrics(self._client.fetch_submission(platform_post_id, token))

    def fetch_comments(self, platform_post_id: str) -> list[NormalizedComment]:
        token = self._resolve_token()
        return [
            normalize_reddit_comment(comment, account_id=self.account_id, submission_id=platform_post_id, index=index)
            for index, comment in enumerate(self._client.fetch_comments(platform_post_id, token))
            if isinstance(comment, dict)
        ]

    def publish(self, text: str, **kwargs: Any) -> PublishResult:
        decision = CapabilityRegistry.from_policy_file(self._policy_path).decide("reddit", "publish_text")
        return PublishResult(ok=False, platform="reddit", reason="unsupported", detail=decision.gate)


__all__ = [
    "RedditAdapterCredentialError",
    "RedditClient",
    "RedditPlatformAdapter",
    "RequestsRedditClient",
    "normalize_reddit_comment",
    "normalize_reddit_submission",
    "reddit_metrics",
]
