#!/usr/bin/env python3
"""
X platform adapter with explicit tier-gated operation checks.
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
from platform_adapters import CapabilityReport, NormalizedComment, NormalizedMetrics, NormalizedPost, PublishResult

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


POLICY_PATH = REPO_ROOT / "knowledge" / "platform_api_policy.json"
X_API_BASE = "https://api.x.com/2"


class XAdapterCredentialError(ValueError):
    """Raised when X adapter operations need credentials."""


class XAdapterCapabilityError(ValueError):
    """Raised when X adapter operations need explicit tier/scope confirmation."""


class XClient(Protocol):
    def list_user_posts(self, account_id: str, token: str) -> list[dict]:
        ...

    def fetch_post(self, post_id: str, token: str) -> dict:
        ...

    def fetch_replies(self, post_id: str, token: str) -> list[dict]:
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


@dataclass(frozen=True)
class RequestsXClient:
    """Thin X API v2 client for optional live smoke paths."""

    def _get(self, path: str, *, token: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if requests is None:
            raise RuntimeError("requests package is required for live X API calls")
        resp = requests.get(
            f"{X_API_BASE}/{path.lstrip('/')}",
            params=params or {},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def list_user_posts(self, account_id: str, token: str) -> list[dict]:
        user_id = account_id.removeprefix("x:")
        payload = self._get(
            f"users/{user_id}/tweets",
            token=token,
            params={"tweet.fields": "created_at,public_metrics,author_id,conversation_id", "max_results": 100},
        )
        return list(payload.get("data") or [])

    def fetch_post(self, post_id: str, token: str) -> dict:
        payload = self._get(
            f"tweets/{post_id}",
            token=token,
            params={"tweet.fields": "created_at,public_metrics,author_id,conversation_id"},
        )
        return dict(payload.get("data") or {})

    def fetch_replies(self, post_id: str, token: str) -> list[dict]:
        payload = self._get(
            "tweets/search/recent",
            token=token,
            params={"query": f"conversation_id:{post_id}", "tweet.fields": "created_at,public_metrics,author_id,conversation_id"},
        )
        return [item for item in list(payload.get("data") or []) if str(item.get("id")) != str(post_id)]


def x_metrics(post: dict[str, Any]) -> NormalizedMetrics:
    metrics = post.get("public_metrics") if isinstance(post.get("public_metrics"), dict) else {}
    retweets = _to_number(metrics.get("retweet_count")) or 0
    quotes = _to_number(metrics.get("quote_count")) or 0
    return NormalizedMetrics(
        view_count=_to_number(metrics.get("impression_count")),
        reaction_count=_to_number(metrics.get("like_count")),
        comment_count=_to_number(metrics.get("reply_count")),
        share_count=retweets + quotes,
    )


def normalize_x_reply(reply: dict[str, Any], *, account_id: str, parent_id: str, index: int = 0) -> NormalizedComment:
    reply_id = str(reply.get("id") or f"{parent_id}:reply:{index}")
    return NormalizedComment(
        platform="x",
        account_id=account_id,
        platform_comment_id=reply_id,
        text=str(reply.get("text") or ""),
        created_at=str(reply.get("created_at") or ""),
        author_id=reply.get("author_id"),
        metrics=NormalizedMetrics(reaction_count=_to_number((reply.get("public_metrics") or {}).get("like_count"))),
        platform_metadata={"x": {"raw": dict(reply)}},
    )


def normalize_x_post(post: dict[str, Any], *, account_id: str, replies: list[dict[str, Any]] | None = None) -> NormalizedPost:
    post_id = str(post.get("id", "")).strip()
    if not post_id:
        raise ValueError("X post id is required")
    normalized_replies = [
        normalize_x_reply(reply, account_id=account_id, parent_id=post_id, index=index)
        for index, reply in enumerate(replies or [])
        if isinstance(reply, dict)
    ]
    return NormalizedPost(
        platform="x",
        account_id=account_id,
        platform_post_id=post_id,
        canonical_post_id=f"x:{account_id}:{post_id}",
        text=str(post.get("text") or ""),
        created_at=str(post.get("created_at") or ""),
        content_format="text",
        url=f"https://x.com/i/web/status/{post_id}",
        metrics=x_metrics(post),
        comments=normalized_replies,
        source={"type": "adapter", "data_completeness": "full" if replies is not None else "partial"},
        platform_metadata={"x": {"raw": {"post": dict(post)}}},
    )


class XPlatformAdapter:
    platform = "x"

    def __init__(
        self,
        *,
        account_id: str,
        token: str | None = None,
        token_file: str | None = None,
        tier_confirmed: bool = False,
        client: XClient | None = None,
        policy_path: str | Path = POLICY_PATH,
    ) -> None:
        self.account_id = account_id
        self._token = token
        self._token_file = token_file
        self._tier_confirmed = tier_confirmed
        self._client = client or RequestsXClient()
        self._policy_path = Path(policy_path)

    def _resolve_token(self) -> str:
        try:
            source = resolve_credential(
                label="X API bearer token",
                direct_value=self._token,
                direct_source_name="XPlatformAdapter(token=...)",
                env_var="X_API_BEARER_TOKEN",
                file_path=self._token_file,
            )
        except CredentialSourceError as exc:
            raise XAdapterCredentialError(str(exc)) from exc
        if not source.value:
            raise XAdapterCredentialError(
                "missing X API bearer token; set X_API_BEARER_TOKEN or pass token_file"
            )
        return source.value

    def _authorize_operation(self) -> str:
        token = self._resolve_token()
        if not self._tier_confirmed:
            raise XAdapterCapabilityError("X API operation is tier-gated; pass tier_confirmed=True after verifying access")
        return token

    def capabilities(self) -> CapabilityReport:
        registry = CapabilityRegistry.from_policy_file(self._policy_path)
        decisions = [registry.decide("x", name) for name in ("read_posts", "read_comments", "refresh_snapshots", "publish_text")]
        return CapabilityReport(
            platform="x",
            can_import_history=False,
            can_refresh_metrics=False,
            can_fetch_comments=False,
            can_publish=False,
            supported_metrics=("view_count", "reaction_count", "comment_count", "share_count"),
            auth_required=True,
            notes=tuple(
                f"{decision.capability}: {decision.status.replace('_', '-')} ({decision.gate})"
                for decision in decisions
            ),
        )

    def list_posts(self) -> list[NormalizedPost]:
        token = self._authorize_operation()
        posts = []
        for post in self._client.list_user_posts(self.account_id, token):
            post_id = str(post.get("id", ""))
            replies = self._client.fetch_replies(post_id, token)
            posts.append(normalize_x_post(post, account_id=self.account_id, replies=replies))
        return posts

    def refresh_metrics(self, platform_post_id: str) -> NormalizedMetrics:
        token = self._authorize_operation()
        return x_metrics(self._client.fetch_post(platform_post_id, token))

    def fetch_comments(self, platform_post_id: str) -> list[NormalizedComment]:
        token = self._authorize_operation()
        return [
            normalize_x_reply(reply, account_id=self.account_id, parent_id=platform_post_id, index=index)
            for index, reply in enumerate(self._client.fetch_replies(platform_post_id, token))
            if isinstance(reply, dict)
        ]

    def publish(self, text: str, **kwargs: Any) -> PublishResult:
        decision = CapabilityRegistry.from_policy_file(self._policy_path).decide("x", "publish_text")
        return PublishResult(ok=False, platform="x", reason="review_required", detail=decision.gate)


__all__ = [
    "RequestsXClient",
    "XAdapterCapabilityError",
    "XAdapterCredentialError",
    "XClient",
    "XPlatformAdapter",
    "normalize_x_post",
    "normalize_x_reply",
    "x_metrics",
]
