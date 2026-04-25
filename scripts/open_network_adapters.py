#!/usr/bin/env python3
"""
Open-network adapters for Bluesky/AT Protocol and Mastodon.
"""

from __future__ import annotations

import re
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
BSKY_APPVIEW_BASE = "https://public.api.bsky.app/xrpc"
HTML_TAG_RE = re.compile(r"<[^>]+>")


class OpenNetworkAdapterCredentialError(ValueError):
    """Raised when open-network adapter operations need credentials."""


class BlueskyClient(Protocol):
    def list_actor_posts(self, actor: str, token: str) -> list[dict]:
        ...

    def fetch_post(self, uri: str, token: str) -> dict:
        ...

    def fetch_replies(self, uri: str, token: str) -> list[dict]:
        ...


class MastodonClient(Protocol):
    def list_account_statuses(self, account_id: str, token: str, instance_url: str) -> list[dict]:
        ...

    def fetch_status(self, status_id: str, token: str, instance_url: str) -> dict:
        ...

    def fetch_replies(self, status_id: str, token: str, instance_url: str) -> list[dict]:
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


def _strip_html(value: str) -> str:
    return re.sub(r"\s+", " ", HTML_TAG_RE.sub("", value or "")).strip()


@dataclass(frozen=True)
class RequestsBlueskyClient:
    """Thin Bluesky appview client for optional live smoke paths."""

    def _get(self, method: str, *, token: str, params: dict[str, Any]) -> dict[str, Any]:
        if requests is None:
            raise RuntimeError("requests package is required for live Bluesky calls")
        resp = requests.get(
            f"{BSKY_APPVIEW_BASE}/{method}",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def list_actor_posts(self, actor: str, token: str) -> list[dict]:
        payload = self._get("app.bsky.feed.getAuthorFeed", token=token, params={"actor": actor, "limit": 50})
        return [
            item.get("post")
            for item in payload.get("feed") or []
            if isinstance(item, dict) and isinstance(item.get("post"), dict)
        ]

    def fetch_post(self, uri: str, token: str) -> dict:
        payload = self._get("app.bsky.feed.getPosts", token=token, params={"uris": uri})
        posts = payload.get("posts") or []
        if not posts:
            raise KeyError(f"Bluesky post not found: {uri}")
        return dict(posts[0])

    def fetch_replies(self, uri: str, token: str) -> list[dict]:
        payload = self._get("app.bsky.feed.getPostThread", token=token, params={"uri": uri})
        thread = payload.get("thread") if isinstance(payload.get("thread"), dict) else {}
        replies = thread.get("replies") or []
        return [
            reply.get("post")
            for reply in replies
            if isinstance(reply, dict) and isinstance(reply.get("post"), dict)
        ]


@dataclass(frozen=True)
class RequestsMastodonClient:
    """Thin Mastodon client with per-instance base URL."""

    def _get(self, instance_url: str, path: str, *, token: str, params: dict[str, Any] | None = None) -> Any:
        if requests is None:
            raise RuntimeError("requests package is required for live Mastodon calls")
        resp = requests.get(
            f"{instance_url.rstrip('/')}/api/v1/{path.lstrip('/')}",
            params=params or {},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def list_account_statuses(self, account_id: str, token: str, instance_url: str) -> list[dict]:
        mastodon_id = account_id.rsplit("/", 1)[-1].lstrip("@")
        payload = self._get(instance_url, f"accounts/{mastodon_id}/statuses", token=token, params={"limit": 40})
        return list(payload or [])

    def fetch_status(self, status_id: str, token: str, instance_url: str) -> dict:
        return dict(self._get(instance_url, f"statuses/{status_id}", token=token))

    def fetch_replies(self, status_id: str, token: str, instance_url: str) -> list[dict]:
        payload = self._get(instance_url, f"statuses/{status_id}/context", token=token)
        return list((payload or {}).get("descendants") or [])


def bluesky_metrics(post: dict[str, Any]) -> NormalizedMetrics:
    return NormalizedMetrics(
        view_count=None,
        reaction_count=_to_number(post.get("likeCount")),
        comment_count=_to_number(post.get("replyCount")),
        share_count=_to_number(post.get("repostCount")),
    )


def mastodon_metrics(status: dict[str, Any]) -> NormalizedMetrics:
    return NormalizedMetrics(
        view_count=None,
        reaction_count=_to_number(status.get("favourites_count")),
        comment_count=_to_number(status.get("replies_count")),
        share_count=_to_number(status.get("reblogs_count")),
    )


def normalize_bluesky_reply(reply: dict[str, Any], *, account_id: str, parent_uri: str, index: int = 0) -> NormalizedComment:
    record = reply.get("record") if isinstance(reply.get("record"), dict) else {}
    author = reply.get("author") if isinstance(reply.get("author"), dict) else {}
    uri = str(reply.get("uri") or f"{parent_uri}:reply:{index}")
    return NormalizedComment(
        platform="bluesky",
        account_id=account_id,
        platform_comment_id=uri,
        text=str(record.get("text") or reply.get("text") or ""),
        created_at=str(record.get("createdAt") or reply.get("created_at") or ""),
        author_id=author.get("did") or author.get("handle"),
        metrics=NormalizedMetrics(reaction_count=_to_number(reply.get("likeCount"))),
        platform_metadata={"bluesky": {"raw": dict(reply)}},
    )


def normalize_mastodon_reply(reply: dict[str, Any], *, account_id: str, status_id: str, instance_url: str, index: int = 0) -> NormalizedComment:
    account = reply.get("account") if isinstance(reply.get("account"), dict) else {}
    reply_id = str(reply.get("id") or f"{status_id}:reply:{index}")
    return NormalizedComment(
        platform="mastodon",
        account_id=account_id,
        platform_comment_id=reply_id,
        text=_strip_html(str(reply.get("content") or reply.get("text") or "")),
        created_at=str(reply.get("created_at") or ""),
        author_id=account.get("id") or account.get("acct"),
        metrics=NormalizedMetrics(reaction_count=_to_number(reply.get("favourites_count"))),
        platform_metadata={"mastodon": {"raw": dict(reply), "instance_url": instance_url}},
    )


def normalize_bluesky_post(
    post: dict[str, Any],
    *,
    account_id: str,
    replies: list[dict[str, Any]] | None = None,
) -> NormalizedPost:
    uri = str(post.get("uri", "")).strip()
    if not uri:
        raise ValueError("Bluesky post uri is required")
    record = post.get("record") if isinstance(post.get("record"), dict) else {}
    normalized_replies = [
        normalize_bluesky_reply(reply, account_id=account_id, parent_uri=uri, index=index)
        for index, reply in enumerate(replies or [])
        if isinstance(reply, dict)
    ]
    return NormalizedPost(
        platform="bluesky",
        account_id=account_id,
        platform_post_id=uri,
        canonical_post_id=f"bluesky:{account_id}:{uri}",
        text=str(record.get("text") or post.get("text") or ""),
        created_at=str(record.get("createdAt") or post.get("created_at") or ""),
        content_format="text",
        url=post.get("url"),
        metrics=bluesky_metrics(post),
        comments=normalized_replies,
        source={"type": "adapter", "data_completeness": "full" if replies is not None else "partial"},
        platform_metadata={"bluesky": {"raw": {"post": dict(post)}}},
    )


def normalize_mastodon_status(
    status: dict[str, Any],
    *,
    account_id: str,
    instance_url: str,
    replies: list[dict[str, Any]] | None = None,
) -> NormalizedPost:
    status_id = str(status.get("id", "")).strip()
    if not status_id:
        raise ValueError("Mastodon status id is required")
    normalized_replies = [
        normalize_mastodon_reply(reply, account_id=account_id, status_id=status_id, instance_url=instance_url, index=index)
        for index, reply in enumerate(replies or [])
        if isinstance(reply, dict)
    ]
    return NormalizedPost(
        platform="mastodon",
        account_id=account_id,
        platform_post_id=status_id,
        canonical_post_id=f"mastodon:{account_id}:{status_id}",
        text=_strip_html(str(status.get("content") or status.get("text") or "")),
        created_at=str(status.get("created_at") or ""),
        content_format=str(status.get("content_format") or "text"),
        url=status.get("url"),
        metrics=mastodon_metrics(status),
        comments=normalized_replies,
        source={"type": "adapter", "data_completeness": "full" if replies is not None else "partial"},
        platform_metadata={"mastodon": {"raw": {"status": dict(status), "instance_url": instance_url}}},
    )


class BlueskyPlatformAdapter:
    platform = "bluesky"

    def __init__(
        self,
        *,
        actor: str,
        token: str | None = None,
        token_file: str | None = None,
        client: BlueskyClient | None = None,
        policy_path: str | Path = POLICY_PATH,
    ) -> None:
        self.actor = actor
        self.account_id = f"bluesky:{actor}" if not actor.startswith("bluesky:") else actor
        self._token = token
        self._token_file = token_file
        self._client = client or RequestsBlueskyClient()
        self._policy_path = Path(policy_path)

    def _resolve_token(self) -> str:
        try:
            source = resolve_credential(
                label="Bluesky app password or session token",
                direct_value=self._token,
                direct_source_name="BlueskyPlatformAdapter(token=...)",
                env_var="BSKY_APP_PASSWORD",
                file_path=self._token_file,
            )
        except CredentialSourceError as exc:
            raise OpenNetworkAdapterCredentialError(str(exc)) from exc
        if not source.value:
            raise OpenNetworkAdapterCredentialError(
                "missing Bluesky credential; set BSKY_APP_PASSWORD or pass token_file"
            )
        return source.value

    def capabilities(self) -> CapabilityReport:
        return _capability_report("bluesky")

    def list_posts(self) -> list[NormalizedPost]:
        token = self._resolve_token()
        posts = []
        for post in self._client.list_actor_posts(self.actor.removeprefix("bluesky:"), token):
            uri = str(post.get("uri", ""))
            replies = self._client.fetch_replies(uri, token)
            posts.append(normalize_bluesky_post(post, account_id=self.account_id, replies=replies))
        return posts

    def refresh_metrics(self, platform_post_id: str) -> NormalizedMetrics:
        token = self._resolve_token()
        return bluesky_metrics(self._client.fetch_post(platform_post_id, token))

    def fetch_comments(self, platform_post_id: str) -> list[NormalizedComment]:
        token = self._resolve_token()
        return [
            normalize_bluesky_reply(reply, account_id=self.account_id, parent_uri=platform_post_id, index=index)
            for index, reply in enumerate(self._client.fetch_replies(platform_post_id, token))
            if isinstance(reply, dict)
        ]

    def publish(self, text: str, **kwargs: Any) -> PublishResult:
        decision = CapabilityRegistry.from_policy_file(self._policy_path).decide("bluesky", "publish_text")
        return PublishResult(ok=False, platform="bluesky", reason="unsupported", detail=decision.gate)


class MastodonPlatformAdapter:
    platform = "mastodon"

    def __init__(
        self,
        *,
        account_id: str,
        instance_url: str,
        token: str | None = None,
        token_file: str | None = None,
        client: MastodonClient | None = None,
        policy_path: str | Path = POLICY_PATH,
    ) -> None:
        self.account_id = account_id
        self.instance_url = instance_url.rstrip("/")
        self._token = token
        self._token_file = token_file
        self._client = client or RequestsMastodonClient()
        self._policy_path = Path(policy_path)

    def _resolve_token(self) -> str:
        try:
            source = resolve_credential(
                label="Mastodon OAuth token",
                direct_value=self._token,
                direct_source_name="MastodonPlatformAdapter(token=...)",
                env_var="MASTODON_OAUTH_TOKEN",
                file_path=self._token_file,
            )
        except CredentialSourceError as exc:
            raise OpenNetworkAdapterCredentialError(str(exc)) from exc
        if not source.value:
            raise OpenNetworkAdapterCredentialError(
                "missing Mastodon OAuth token; set MASTODON_OAUTH_TOKEN or pass token_file"
            )
        return source.value

    def capabilities(self) -> CapabilityReport:
        return _capability_report("mastodon")

    def list_posts(self) -> list[NormalizedPost]:
        token = self._resolve_token()
        posts = []
        for status in self._client.list_account_statuses(self.account_id, token, self.instance_url):
            status_id = str(status.get("id", ""))
            replies = self._client.fetch_replies(status_id, token, self.instance_url)
            posts.append(normalize_mastodon_status(status, account_id=self.account_id, instance_url=self.instance_url, replies=replies))
        return posts

    def refresh_metrics(self, platform_post_id: str) -> NormalizedMetrics:
        token = self._resolve_token()
        return mastodon_metrics(self._client.fetch_status(platform_post_id, token, self.instance_url))

    def fetch_comments(self, platform_post_id: str) -> list[NormalizedComment]:
        token = self._resolve_token()
        return [
            normalize_mastodon_reply(reply, account_id=self.account_id, status_id=platform_post_id, instance_url=self.instance_url, index=index)
            for index, reply in enumerate(self._client.fetch_replies(platform_post_id, token, self.instance_url))
            if isinstance(reply, dict)
        ]

    def publish(self, text: str, **kwargs: Any) -> PublishResult:
        decision = CapabilityRegistry.from_policy_file(self._policy_path).decide("mastodon", "publish_text")
        return PublishResult(ok=False, platform="mastodon", reason="unsupported", detail=decision.gate)


def _capability_report(platform: str) -> CapabilityReport:
    registry = CapabilityRegistry.from_policy_file(POLICY_PATH)
    read_posts = registry.decide(platform, "read_posts")
    read_comments = registry.decide(platform, "read_comments")
    refresh = registry.decide(platform, "refresh_snapshots")
    publish = registry.decide(platform, "publish_text")
    return CapabilityReport(
        platform=platform,
        can_import_history=read_posts.allowed,
        can_refresh_metrics=refresh.allowed,
        can_fetch_comments=read_comments.allowed,
        can_publish=False,
        supported_metrics=("reaction_count", "comment_count", "share_count"),
        auth_required=platform in {"bluesky", "mastodon"},
        notes=(read_posts.gate, read_comments.gate, refresh.gate, f"publish_text: {publish.status} ({publish.gate})"),
    )


__all__ = [
    "BlueskyClient",
    "BlueskyPlatformAdapter",
    "MastodonClient",
    "MastodonPlatformAdapter",
    "OpenNetworkAdapterCredentialError",
    "RequestsBlueskyClient",
    "RequestsMastodonClient",
    "bluesky_metrics",
    "mastodon_metrics",
    "normalize_bluesky_post",
    "normalize_bluesky_reply",
    "normalize_mastodon_reply",
    "normalize_mastodon_status",
]
