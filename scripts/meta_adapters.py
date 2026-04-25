#!/usr/bin/env python3
"""
Meta-family platform adapters for Instagram and Facebook Pages.

The adapters share Graph API client plumbing but keep platform capability
reports and normalization separate.
"""

from __future__ import annotations

import os
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
except ImportError:  # pragma: no cover - dependency is installed through scripts/requirements.txt
    requests = None


POLICY_PATH = REPO_ROOT / "knowledge" / "platform_api_policy.json"
DEFAULT_GRAPH_VERSION = os.environ.get("META_GRAPH_VERSION", "v24.0")


class MetaAdapterCredentialError(ValueError):
    """Raised when a Meta-family adapter operation needs credentials."""


class MetaGraphClient(Protocol):
    def list_instagram_media(self, account_id: str, token: str) -> list[dict]:
        ...

    def fetch_instagram_insights(self, media_id: str, token: str) -> dict:
        ...

    def fetch_instagram_comments(self, media_id: str, token: str) -> list[dict]:
        ...

    def list_facebook_page_posts(self, page_id: str, token: str) -> list[dict]:
        ...

    def fetch_facebook_post_insights(self, post_id: str, token: str) -> dict:
        ...

    def fetch_facebook_comments(self, post_id: str, token: str) -> list[dict]:
        ...


def _first_numeric(*values: Any) -> int | float | None:
    for value in values:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
    return None


def _summary_total(value: Any) -> int | float | None:
    if not isinstance(value, dict):
        return None
    summary = value.get("summary")
    if not isinstance(summary, dict):
        return None
    return _first_numeric(summary.get("total_count"))


def _count_value(value: Any) -> int | float | None:
    if isinstance(value, dict):
        return _first_numeric(value.get("count"))
    return _first_numeric(value)


def _parse_graph_insights(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    if "data" not in payload:
        return dict(payload)

    parsed: dict[str, Any] = {}
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        values = item.get("values") or []
        if not name or not values or not isinstance(values[0], dict):
            continue
        parsed[name] = values[0].get("value")
    return parsed


@dataclass(frozen=True)
class RequestsMetaGraphClient:
    """Small requests-based Graph client with configurable API version."""

    graph_version: str = DEFAULT_GRAPH_VERSION

    @property
    def base_url(self) -> str:
        return f"https://graph.facebook.com/{self.graph_version}"

    def _get(self, path: str, *, token: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if requests is None:
            raise RuntimeError("requests package is required for live Meta Graph calls")
        query = dict(params or {})
        query["access_token"] = token
        resp = requests.get(f"{self.base_url}/{path.lstrip('/')}", params=query, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def list_instagram_media(self, account_id: str, token: str) -> list[dict]:
        payload = self._get(
            f"{account_id}/media",
            token=token,
            params={
                "fields": "id,caption,timestamp,media_type,media_product_type,permalink,like_count,comments_count",
                "limit": 50,
            },
        )
        return list(payload.get("data") or [])

    def fetch_instagram_insights(self, media_id: str, token: str) -> dict:
        payload = self._get(
            f"{media_id}/insights",
            token=token,
            params={"metric": "views,impressions,reach,saved,shares,plays"},
        )
        return _parse_graph_insights(payload)

    def fetch_instagram_comments(self, media_id: str, token: str) -> list[dict]:
        payload = self._get(
            f"{media_id}/comments",
            token=token,
            params={"fields": "id,text,timestamp,username,like_count", "limit": 50},
        )
        return list(payload.get("data") or [])

    def list_facebook_page_posts(self, page_id: str, token: str) -> list[dict]:
        payload = self._get(
            f"{page_id}/posts",
            token=token,
            params={
                "fields": "id,message,created_time,permalink_url,shares,reactions.summary(true),comments.summary(true)",
                "limit": 50,
            },
        )
        return list(payload.get("data") or [])

    def fetch_facebook_post_insights(self, post_id: str, token: str) -> dict:
        payload = self._get(
            f"{post_id}/insights",
            token=token,
            params={"metric": "post_impressions,post_impressions_unique"},
        )
        return _parse_graph_insights(payload)

    def fetch_facebook_comments(self, post_id: str, token: str) -> list[dict]:
        payload = self._get(
            f"{post_id}/comments",
            token=token,
            params={"fields": "id,from,message,created_time,like_count", "limit": 50},
        )
        return list(payload.get("data") or [])


def instagram_metrics(media: dict[str, Any], insights: dict[str, Any] | None = None) -> NormalizedMetrics:
    parsed = _parse_graph_insights(insights)
    return NormalizedMetrics(
        view_count=_first_numeric(parsed.get("views"), parsed.get("impressions"), parsed.get("plays")),
        reaction_count=_first_numeric(media.get("like_count")),
        comment_count=_first_numeric(media.get("comments_count")),
        share_count=_first_numeric(parsed.get("shares")),
        save_count=_first_numeric(parsed.get("saved")),
    )


def facebook_page_metrics(post: dict[str, Any], insights: dict[str, Any] | None = None) -> NormalizedMetrics:
    parsed = _parse_graph_insights(insights)
    return NormalizedMetrics(
        view_count=_first_numeric(parsed.get("post_impressions"), parsed.get("post_impressions_unique"), parsed.get("views")),
        reaction_count=_summary_total(post.get("reactions")),
        comment_count=_summary_total(post.get("comments")),
        share_count=_count_value(post.get("shares")),
    )


def normalize_instagram_comment(comment: dict[str, Any], *, account_id: str, media_id: str, index: int = 0) -> NormalizedComment:
    comment_id = str(comment.get("id") or f"{media_id}:comment:{index}")
    return NormalizedComment(
        platform="instagram",
        account_id=account_id,
        platform_comment_id=comment_id,
        text=str(comment.get("text", "")),
        created_at=str(comment.get("timestamp") or comment.get("created_at") or ""),
        author_id=comment.get("username") or comment.get("user"),
        metrics=NormalizedMetrics(reaction_count=_first_numeric(comment.get("like_count"), comment.get("likes"))),
        platform_metadata={"instagram": {"raw": dict(comment)}},
    )


def normalize_facebook_comment(comment: dict[str, Any], *, account_id: str, post_id: str, index: int = 0) -> NormalizedComment:
    author = comment.get("from") if isinstance(comment.get("from"), dict) else {}
    comment_id = str(comment.get("id") or f"{post_id}:comment:{index}")
    return NormalizedComment(
        platform="facebook_pages",
        account_id=account_id,
        platform_comment_id=comment_id,
        text=str(comment.get("message") or comment.get("text") or ""),
        created_at=str(comment.get("created_time") or comment.get("created_at") or ""),
        author_id=author.get("id") or comment.get("author_id"),
        metrics=NormalizedMetrics(reaction_count=_first_numeric(comment.get("like_count"), comment.get("likes"))),
        platform_metadata={"facebook_pages": {"raw": dict(comment)}},
    )


def normalize_instagram_media(
    media: dict[str, Any],
    *,
    account_id: str,
    insights: dict[str, Any] | None = None,
    comments: list[dict[str, Any]] | None = None,
) -> NormalizedPost:
    media_id = str(media.get("id", "")).strip()
    if not media_id:
        raise ValueError("Instagram media id is required")
    normalized_comments = [
        normalize_instagram_comment(comment, account_id=account_id, media_id=media_id, index=index)
        for index, comment in enumerate(comments or [])
        if isinstance(comment, dict)
    ]
    return NormalizedPost(
        platform="instagram",
        account_id=account_id,
        platform_post_id=media_id,
        canonical_post_id=f"instagram:{account_id}:{media_id}",
        text=str(media.get("caption") or media.get("text") or ""),
        created_at=str(media.get("timestamp") or media.get("created_at") or ""),
        content_format=str(media.get("media_type") or media.get("content_format") or "media").lower(),
        url=media.get("permalink") or media.get("url"),
        metrics=instagram_metrics(media, insights),
        comments=normalized_comments,
        source={"type": "adapter", "data_completeness": "full" if insights is not None else "partial"},
        platform_metadata={"instagram": {"raw": {"media": dict(media), "insights": dict(insights or {})}}},
    )


def normalize_facebook_page_post(
    post: dict[str, Any],
    *,
    account_id: str,
    insights: dict[str, Any] | None = None,
    comments: list[dict[str, Any]] | None = None,
) -> NormalizedPost:
    post_id = str(post.get("id", "")).strip()
    if not post_id:
        raise ValueError("Facebook Page post id is required")
    normalized_comments = [
        normalize_facebook_comment(comment, account_id=account_id, post_id=post_id, index=index)
        for index, comment in enumerate(comments or [])
        if isinstance(comment, dict)
    ]
    return NormalizedPost(
        platform="facebook_pages",
        account_id=account_id,
        platform_post_id=post_id,
        canonical_post_id=f"facebook_pages:{account_id}:{post_id}",
        text=str(post.get("message") or post.get("text") or ""),
        created_at=str(post.get("created_time") or post.get("created_at") or ""),
        content_format=str(post.get("content_format") or "page_post"),
        url=post.get("permalink_url") or post.get("url"),
        metrics=facebook_page_metrics(post, insights),
        comments=normalized_comments,
        source={"type": "adapter", "data_completeness": "full" if insights is not None else "partial"},
        platform_metadata={"facebook_pages": {"raw": {"post": dict(post), "insights": dict(insights or {})}}},
    )


class _MetaGraphPlatformAdapter:
    platform: str
    credential_label: str

    def __init__(
        self,
        *,
        account_id: str,
        token: str | None = None,
        token_file: str | None = None,
        client: MetaGraphClient | None = None,
        policy_path: str | Path = POLICY_PATH,
    ) -> None:
        self.account_id = account_id
        self._token = token
        self._token_file = token_file
        self._client = client or RequestsMetaGraphClient()
        self._policy_path = Path(policy_path)

    def _resolve_token(self) -> str:
        try:
            source = resolve_credential(
                label=self.credential_label,
                direct_value=self._token,
                direct_source_name=f"{self.__class__.__name__}(token=...)",
                env_var="META_GRAPH_API_TOKEN",
                file_path=self._token_file,
            )
        except CredentialSourceError as exc:
            raise MetaAdapterCredentialError(str(exc)) from exc
        if not source.value:
            raise MetaAdapterCredentialError(
                "missing Meta Graph API token; set META_GRAPH_API_TOKEN or pass token_file"
            )
        return source.value

    def capabilities(self) -> CapabilityReport:
        registry = CapabilityRegistry.from_policy_file(self._policy_path)
        read_posts = registry.decide(self.platform, "read_posts")
        read_comments = registry.decide(self.platform, "read_comments")
        refresh = registry.decide(self.platform, "refresh_snapshots")
        publish = registry.decide(self.platform, "publish_text")
        return CapabilityReport(
            platform=self.platform,
            can_import_history=read_posts.allowed,
            can_refresh_metrics=refresh.allowed,
            can_fetch_comments=read_comments.allowed,
            can_publish=False,
            supported_metrics=("view_count", "reaction_count", "comment_count", "share_count", "save_count"),
            auth_required=True,
            notes=(read_posts.gate, read_comments.gate, refresh.gate, f"publish_text: {publish.status} ({publish.gate})"),
        )

    def publish(self, text: str, **kwargs: Any) -> PublishResult:
        decision = CapabilityRegistry.from_policy_file(self._policy_path).decide(self.platform, "publish_text")
        return PublishResult(
            ok=False,
            platform=self.platform,
            reason="review_required" if decision.requires_review else "unsupported",
            detail=decision.gate,
        )


class InstagramPlatformAdapter(_MetaGraphPlatformAdapter):
    platform = "instagram"
    credential_label = "Meta Graph API token"

    def list_posts(self) -> list[NormalizedPost]:
        token = self._resolve_token()
        posts = []
        for media in self._client.list_instagram_media(self.account_id, token):
            media_id = str(media.get("id", ""))
            insights = self._client.fetch_instagram_insights(media_id, token)
            comments = self._client.fetch_instagram_comments(media_id, token)
            posts.append(normalize_instagram_media(media, account_id=self.account_id, insights=insights, comments=comments))
        return posts

    def refresh_metrics(self, platform_post_id: str) -> NormalizedMetrics:
        token = self._resolve_token()
        return instagram_metrics({}, self._client.fetch_instagram_insights(platform_post_id, token))

    def fetch_comments(self, platform_post_id: str) -> list[NormalizedComment]:
        token = self._resolve_token()
        return [
            normalize_instagram_comment(comment, account_id=self.account_id, media_id=platform_post_id, index=index)
            for index, comment in enumerate(self._client.fetch_instagram_comments(platform_post_id, token))
            if isinstance(comment, dict)
        ]


class FacebookPagesPlatformAdapter(_MetaGraphPlatformAdapter):
    platform = "facebook_pages"
    credential_label = "Meta Graph API token"

    def list_posts(self) -> list[NormalizedPost]:
        token = self._resolve_token()
        posts = []
        for post in self._client.list_facebook_page_posts(self.account_id, token):
            post_id = str(post.get("id", ""))
            insights = self._client.fetch_facebook_post_insights(post_id, token)
            comments = self._client.fetch_facebook_comments(post_id, token)
            posts.append(normalize_facebook_page_post(post, account_id=self.account_id, insights=insights, comments=comments))
        return posts

    def refresh_metrics(self, platform_post_id: str) -> NormalizedMetrics:
        token = self._resolve_token()
        return facebook_page_metrics({}, self._client.fetch_facebook_post_insights(platform_post_id, token))

    def fetch_comments(self, platform_post_id: str) -> list[NormalizedComment]:
        token = self._resolve_token()
        return [
            normalize_facebook_comment(comment, account_id=self.account_id, post_id=platform_post_id, index=index)
            for index, comment in enumerate(self._client.fetch_facebook_comments(platform_post_id, token))
            if isinstance(comment, dict)
        ]


__all__ = [
    "FacebookPagesPlatformAdapter",
    "InstagramPlatformAdapter",
    "MetaAdapterCredentialError",
    "MetaGraphClient",
    "RequestsMetaGraphClient",
    "facebook_page_metrics",
    "instagram_metrics",
    "normalize_facebook_comment",
    "normalize_facebook_page_post",
    "normalize_instagram_comment",
    "normalize_instagram_media",
]
