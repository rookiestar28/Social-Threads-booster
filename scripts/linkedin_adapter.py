#!/usr/bin/env python3
"""
LinkedIn platform adapter with explicit access-review gating.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote


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
LINKEDIN_REST_BASE = "https://api.linkedin.com/rest"
DEFAULT_LINKEDIN_VERSION = "202604"


class LinkedInAdapterCredentialError(ValueError):
    """Raised when LinkedIn adapter operations need credentials."""


class LinkedInAdapterCapabilityError(ValueError):
    """Raised when LinkedIn adapter operations need access-review confirmation."""


class LinkedInClient(Protocol):
    def list_posts(self, account_id: str, token: str) -> list[dict]:
        ...

    def fetch_post(self, post_urn: str, token: str) -> dict:
        ...

    def fetch_social_metadata(self, post_urn: str, token: str) -> dict:
        ...

    def fetch_comments(self, post_urn: str, token: str) -> list[dict]:
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


def _sum_reactions(payload: Any) -> int | float | None:
    if not isinstance(payload, dict):
        return None
    total: int | float = 0
    found = False
    for value in payload.values():
        count = value.get("count") if isinstance(value, dict) else value
        number = _to_number(count)
        if number is not None:
            total += number
            found = True
    return total if found else None


def _first_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, dict):
            nested = _first_text(value.get("text"), value.get("value"), value.get("localized"))
            if nested:
                return nested
    return ""


def _timestamp_to_iso(value: Any) -> str:
    number = _to_number(value)
    if number is not None:
        seconds = number / 1000 if number > 10_000_000_000 else number
        return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
    if isinstance(value, str):
        return value
    return ""


def linkedin_metrics(social_metadata: dict[str, Any] | None) -> NormalizedMetrics:
    metadata = social_metadata if isinstance(social_metadata, dict) else {}
    comment_summary = metadata.get("commentSummary") if isinstance(metadata.get("commentSummary"), dict) else {}
    reaction_count = _sum_reactions(metadata.get("reactionSummaries"))
    if reaction_count is None:
        reaction_count = _to_number(metadata.get("reactionCount"))
    return NormalizedMetrics(
        reaction_count=reaction_count,
        comment_count=(
            _to_number(comment_summary.get("totalFirstLevelComments"))
            or _to_number(comment_summary.get("count"))
            or _to_number(metadata.get("commentCount"))
        ),
        share_count=_to_number(metadata.get("shareCount")) or _to_number(metadata.get("shares")),
    )


def normalize_linkedin_comment(
    comment: dict[str, Any],
    *,
    account_id: str,
    parent_urn: str,
    index: int = 0,
) -> NormalizedComment:
    comment_id = str(comment.get("id") or f"{parent_urn}:comment:{index}")
    created = comment.get("created") if isinstance(comment.get("created"), dict) else {}
    likes = comment.get("likesSummary") if isinstance(comment.get("likesSummary"), dict) else {}
    return NormalizedComment(
        platform="linkedin",
        account_id=account_id,
        platform_comment_id=comment_id,
        text=_first_text(comment.get("message"), comment.get("commentary"), comment.get("text")),
        created_at=_timestamp_to_iso(created.get("time") or comment.get("createdAt") or comment.get("lastModifiedAt")),
        author_id=comment.get("actor") or comment.get("author"),
        metrics=NormalizedMetrics(
            reaction_count=_to_number(likes.get("totalLikes"))
            or _sum_reactions(comment.get("reactionSummaries"))
            or _to_number(comment.get("reactionCount"))
        ),
        platform_metadata={"linkedin": {"raw": dict(comment)}},
    )


def normalize_linkedin_post(
    post: dict[str, Any],
    *,
    account_id: str,
    account_type: str,
    social_metadata: dict[str, Any] | None = None,
    comments: list[dict[str, Any]] | None = None,
) -> NormalizedPost:
    post_urn = str(post.get("id") or post.get("urn") or "").strip()
    if not post_urn:
        raise ValueError("LinkedIn post id is required")
    author = post.get("author") or post.get("owner")
    normalized_comments = [
        normalize_linkedin_comment(comment, account_id=account_id, parent_urn=post_urn, index=index)
        for index, comment in enumerate(comments or [])
        if isinstance(comment, dict)
    ]
    return NormalizedPost(
        platform="linkedin",
        account_id=account_id,
        platform_post_id=post_urn,
        canonical_post_id=f"linkedin:{account_id}:{post_urn}",
        text=_first_text(post.get("commentary"), post.get("text"), post.get("content")),
        created_at=_timestamp_to_iso(post.get("createdAt") or post.get("publishedAt") or post.get("lastModifiedAt")),
        content_format="text",
        url=post.get("permalink") or post.get("url"),
        metrics=linkedin_metrics(social_metadata),
        comments=normalized_comments,
        source={"type": "adapter", "data_completeness": "full" if comments is not None else "partial"},
        platform_metadata={
            "linkedin": {
                "account_type": account_type,
                "author": author,
                "raw": {"post": dict(post), "social_metadata": dict(social_metadata or {})},
            }
        },
    )


@dataclass(frozen=True)
class RequestsLinkedInClient:
    """Thin LinkedIn REST.li client for optional credentialed smoke paths."""

    api_version: str = DEFAULT_LINKEDIN_VERSION

    def _headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "LinkedIn-Version": self.api_version,
            # IMPORTANT: LinkedIn REST.li endpoints require this protocol header.
            "X-Restli-Protocol-Version": "2.0.0",
        }

    def _get(self, path: str, *, token: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if requests is None:
            raise RuntimeError("requests package is required for live LinkedIn API calls")
        resp = requests.get(
            f"{LINKEDIN_REST_BASE}/{path.lstrip('/')}",
            params=params or {},
            headers=self._headers(token),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def list_posts(self, account_id: str, token: str) -> list[dict]:
        author_urn = _account_id_to_author_urn(account_id)
        payload = self._get("posts", token=token, params={"author": author_urn, "q": "author", "count": 100})
        return list(payload.get("elements") or [])

    def fetch_post(self, post_urn: str, token: str) -> dict:
        return self._get(f"posts/{quote(post_urn, safe='')}", token=token)

    def fetch_social_metadata(self, post_urn: str, token: str) -> dict:
        encoded = quote(post_urn, safe="")
        return self._get(f"socialMetadata/{encoded}", token=token)

    def fetch_comments(self, post_urn: str, token: str) -> list[dict]:
        encoded = quote(post_urn, safe="")
        payload = self._get(f"socialActions/{encoded}/comments", token=token)
        return list(payload.get("elements") or [])


def _account_id_to_author_urn(account_id: str) -> str:
    if account_id.startswith("urn:li:"):
        return account_id
    if account_id.startswith("linkedin:organization:"):
        return "urn:li:organization:" + account_id.rsplit(":", 1)[-1]
    if account_id.startswith("linkedin:person:"):
        return "urn:li:person:" + account_id.rsplit(":", 1)[-1]
    return account_id


class LinkedInPlatformAdapter:
    platform = "linkedin"

    def __init__(
        self,
        *,
        account_id: str,
        account_type: str = "linkedin_member",
        token: str | None = None,
        token_file: str | None = None,
        access_confirmed: bool = False,
        client: LinkedInClient | None = None,
        policy_path: str | Path = POLICY_PATH,
    ) -> None:
        self.account_id = account_id
        self.account_type = account_type
        self._token = token
        self._token_file = token_file
        self._access_confirmed = access_confirmed
        self._client = client or RequestsLinkedInClient()
        self._policy_path = Path(policy_path)

    def _resolve_token(self) -> str:
        try:
            source = resolve_credential(
                label="LinkedIn access token",
                direct_value=self._token,
                direct_source_name="LinkedInPlatformAdapter(token=...)",
                env_var="LINKEDIN_ACCESS_TOKEN",
                file_path=self._token_file,
            )
        except CredentialSourceError as exc:
            raise LinkedInAdapterCredentialError(str(exc)) from exc
        if not source.value:
            raise LinkedInAdapterCredentialError(
                "missing LinkedIn access token; set LINKEDIN_ACCESS_TOKEN or pass token_file"
            )
        return source.value

    def _authorize_operation(self) -> str:
        token = self._resolve_token()
        if not self._access_confirmed:
            raise LinkedInAdapterCapabilityError(
                "LinkedIn Community Management operation is review-gated; pass access_confirmed=True after verifying access"
            )
        return token

    def capabilities(self) -> CapabilityReport:
        registry = CapabilityRegistry.from_policy_file(self._policy_path)
        read_posts = registry.decide("linkedin", "read_posts")
        read_comments = registry.decide("linkedin", "read_comments")
        refresh = registry.decide("linkedin", "refresh_snapshots")
        publish = registry.decide("linkedin", "publish_text")
        return CapabilityReport(
            platform="linkedin",
            can_import_history=False,
            can_refresh_metrics=False,
            can_fetch_comments=False,
            can_publish=False,
            supported_metrics=("reaction_count", "comment_count", "share_count"),
            auth_required=True,
            notes=(
                f"read_posts: {read_posts.status.replace('_', '-')} ({read_posts.gate})",
                f"read_comments: {read_comments.status.replace('_', '-')} ({read_comments.gate})",
                f"refresh_snapshots: {refresh.status.replace('_', '-')} ({refresh.gate})",
                f"publish_text: {publish.status.replace('_', '-')} ({publish.gate})",
            ),
        )

    def list_posts(self) -> list[NormalizedPost]:
        token = self._authorize_operation()
        posts = []
        for post in self._client.list_posts(self.account_id, token):
            post_urn = str(post.get("id") or post.get("urn") or "")
            social_metadata = self._client.fetch_social_metadata(post_urn, token)
            comments = self._client.fetch_comments(post_urn, token)
            posts.append(
                normalize_linkedin_post(
                    post,
                    account_id=self.account_id,
                    account_type=self.account_type,
                    social_metadata=social_metadata,
                    comments=comments,
                )
            )
        return posts

    def refresh_metrics(self, platform_post_id: str) -> NormalizedMetrics:
        token = self._authorize_operation()
        return linkedin_metrics(self._client.fetch_social_metadata(platform_post_id, token))

    def fetch_comments(self, platform_post_id: str) -> list[NormalizedComment]:
        token = self._authorize_operation()
        return [
            normalize_linkedin_comment(comment, account_id=self.account_id, parent_urn=platform_post_id, index=index)
            for index, comment in enumerate(self._client.fetch_comments(platform_post_id, token))
            if isinstance(comment, dict)
        ]

    def publish(self, text: str, **kwargs: Any) -> PublishResult:
        decision = CapabilityRegistry.from_policy_file(self._policy_path).decide("linkedin", "publish_text")
        return PublishResult(ok=False, platform="linkedin", reason="review_required", detail=decision.gate)


__all__ = [
    "LinkedInAdapterCapabilityError",
    "LinkedInAdapterCredentialError",
    "LinkedInClient",
    "LinkedInPlatformAdapter",
    "RequestsLinkedInClient",
    "linkedin_metrics",
    "normalize_linkedin_comment",
    "normalize_linkedin_post",
]
