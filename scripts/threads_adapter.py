#!/usr/bin/env python3
"""
First-class Threads platform adapter.

The existing Threads CLI scripts remain the compatibility entrypoints. This
adapter wraps their API helpers and converts Threads payloads into the
platform-neutral adapter contract.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from capability_registry import CapabilityRegistry
from credential_sources import CredentialSourceError, resolve_credential
from platform_adapters import (
    CapabilityReport,
    NormalizedComment,
    NormalizedMetrics,
    NormalizedPost,
    PublishResult,
)

try:
    import fetch_threads
except ImportError as exc:  # pragma: no cover - import failure is environment setup
    raise RuntimeError(f"could not import Threads API helpers: {exc}") from exc


POLICY_PATH = REPO_ROOT / "knowledge" / "platform_api_policy.json"


class ThreadsAdapterCredentialError(ValueError):
    """Raised when a Threads adapter operation needs credentials but none are available."""


class ThreadsClient(Protocol):
    def get_user_profile(self, token: str) -> dict:
        ...

    def fetch_all_threads(self, user_id: str, token: str) -> list[dict]:
        ...

    def fetch_thread_insights(self, thread_id: str, token: str) -> dict:
        ...

    def fetch_thread_replies(self, thread_id: str, token: str) -> list[dict]:
        ...


@dataclass(frozen=True)
class FetchThreadsClient:
    """Thin wrapper around the existing Threads API helper functions."""

    def get_user_profile(self, token: str) -> dict:
        return fetch_threads.get_user_profile(token)

    def fetch_all_threads(self, user_id: str, token: str) -> list[dict]:
        return fetch_threads.fetch_all_threads(user_id, token)

    def fetch_thread_insights(self, thread_id: str, token: str) -> dict:
        return fetch_threads.fetch_thread_insights(thread_id, token)

    def fetch_thread_replies(self, thread_id: str, token: str) -> list[dict]:
        return fetch_threads.fetch_thread_replies(thread_id, token)


def threads_metrics_to_normalized(metrics: dict[str, Any] | None) -> NormalizedMetrics:
    source = metrics or {}
    reposts = source.get("reposts")
    quotes = source.get("quotes")
    share_count = 0
    for value in (reposts, quotes):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            share_count += value

    return NormalizedMetrics(
        view_count=source.get("views"),
        reaction_count=source.get("likes"),
        comment_count=source.get("replies"),
        share_count=share_count,
    )


def normalize_threads_reply(reply: dict[str, Any], *, account_id: str, post_id: str, index: int = 0) -> NormalizedComment:
    reply_id = str(reply.get("id") or f"{post_id}:reply:{index}")
    created_at = str(reply.get("timestamp") or reply.get("created_at") or "")
    return NormalizedComment(
        platform="threads",
        account_id=account_id,
        platform_comment_id=reply_id,
        text=str(reply.get("text", "")),
        created_at=created_at,
        author_id=reply.get("username") or reply.get("user"),
        metrics=NormalizedMetrics(reaction_count=reply.get("likes") if isinstance(reply.get("likes"), (int, float)) else None),
        platform_metadata={"threads": {"raw": dict(reply)}},
    )


def normalize_threads_post(
    thread: dict[str, Any],
    *,
    account_id: str,
    metrics: dict[str, Any] | None = None,
    replies: list[dict[str, Any]] | None = None,
) -> NormalizedPost:
    post_id = str(thread.get("id", "")).strip()
    if not post_id:
        raise ValueError("Threads post id is required")

    normalized_comments = [
        normalize_threads_reply(reply, account_id=account_id, post_id=post_id, index=index)
        for index, reply in enumerate(replies or [])
        if isinstance(reply, dict)
    ]
    media_type = str(thread.get("media_type") or "TEXT").lower()
    raw = {
        "thread": dict(thread),
        "metrics": dict(metrics or {}),
    }
    return NormalizedPost(
        platform="threads",
        account_id=account_id,
        platform_post_id=post_id,
        canonical_post_id=f"threads:{account_id}:{post_id}",
        text=str(thread.get("text", "")),
        created_at=str(thread.get("timestamp") or thread.get("created_at") or ""),
        content_format=media_type,
        url=thread.get("permalink"),
        metrics=threads_metrics_to_normalized(metrics),
        comments=normalized_comments,
        source={"type": "adapter", "data_completeness": "full" if metrics is not None else "partial"},
        platform_metadata={"threads": {"raw": raw}},
    )


class ThreadsPlatformAdapter:
    platform = "threads"

    def __init__(
        self,
        *,
        account_id: str,
        token: str | None = None,
        token_file: str | None = None,
        client: ThreadsClient | None = None,
        policy_path: str | Path = POLICY_PATH,
    ) -> None:
        self.account_id = account_id
        self._token = token
        self._token_file = token_file
        self._client = client or FetchThreadsClient()
        self._policy_path = Path(policy_path)

    def _resolve_token(self) -> str:
        try:
            source = resolve_credential(
                label="Threads API token",
                direct_value=self._token,
                direct_source_name="ThreadsPlatformAdapter(token=...)",
                env_var="THREADS_API_TOKEN",
                file_path=self._token_file,
            )
        except CredentialSourceError as exc:
            raise ThreadsAdapterCredentialError(str(exc)) from exc

        if not source.value:
            raise ThreadsAdapterCredentialError(
                "missing Threads API token; set THREADS_API_TOKEN or pass token_file"
            )
        return source.value

    def capabilities(self) -> CapabilityReport:
        registry = CapabilityRegistry.from_policy_file(self._policy_path)
        read_posts = registry.decide("threads", "read_posts")
        read_comments = registry.decide("threads", "read_comments")
        refresh = registry.decide("threads", "refresh_snapshots")
        publish = registry.decide("threads", "publish_text")
        return CapabilityReport(
            platform="threads",
            can_import_history=read_posts.allowed,
            can_refresh_metrics=refresh.allowed,
            can_fetch_comments=read_comments.allowed,
            can_publish=publish.allowed,
            supported_metrics=("view_count", "reaction_count", "comment_count", "share_count"),
            auth_required=True,
            notes=(
                read_posts.gate,
                read_comments.gate,
                refresh.gate,
                f"publish_text: {publish.status} ({publish.gate})",
            ),
        )

    def list_posts(self) -> list[NormalizedPost]:
        token = self._resolve_token()
        profile = self._client.get_user_profile(token)
        user_id = str(profile["id"])
        if self.account_id in {"threads:unknown", "threads:"}:
            username = str(profile.get("username") or "").strip()
            if username:
                self.account_id = f"threads:@{username}"

        posts = []
        for thread in self._client.fetch_all_threads(user_id, token):
            post_id = str(thread.get("id", ""))
            metrics = self._client.fetch_thread_insights(post_id, token)
            replies = self._client.fetch_thread_replies(post_id, token)
            posts.append(
                normalize_threads_post(
                    thread,
                    account_id=self.account_id,
                    metrics=metrics,
                    replies=replies,
                )
            )
        return posts

    def refresh_metrics(self, platform_post_id: str) -> NormalizedMetrics:
        token = self._resolve_token()
        return threads_metrics_to_normalized(self._client.fetch_thread_insights(platform_post_id, token))

    def fetch_comments(self, platform_post_id: str) -> list[NormalizedComment]:
        token = self._resolve_token()
        replies = self._client.fetch_thread_replies(platform_post_id, token)
        return [
            normalize_threads_reply(reply, account_id=self.account_id, post_id=platform_post_id, index=index)
            for index, reply in enumerate(replies)
            if isinstance(reply, dict)
        ]

    def publish(self, text: str, **kwargs: Any) -> PublishResult:
        decision = CapabilityRegistry.from_policy_file(self._policy_path).decide("threads", "publish_text")
        return PublishResult(
            ok=False,
            platform="threads",
            reason="review_required" if decision.requires_review else "unsupported",
            detail=decision.gate,
        )


__all__ = [
    "FetchThreadsClient",
    "ThreadsAdapterCredentialError",
    "ThreadsClient",
    "ThreadsPlatformAdapter",
    "normalize_threads_post",
    "normalize_threads_reply",
    "threads_metrics_to_normalized",
]
