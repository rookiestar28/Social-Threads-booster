#!/usr/bin/env python3
"""
Validate platform adapter policy review evidence against the policy matrix.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_POLICY_PATH = REPO_ROOT / "knowledge" / "platform_api_policy.json"

REQUIRED_REVIEW_FIELDS = {
    "reviewed_at",
    "adapter_item",
    "platform",
    "official_docs_reviewed",
    "capabilities_reviewed",
    "rate_limit_policy",
    "data_retention_policy",
    "disallowed_fallbacks",
    "credentialed_smoke",
}

FORBIDDEN_EVIDENCE_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "client_secret",
    "api_key",
    "password",
    "cookie",
    "secret",
}


class PlatformReviewError(ValueError):
    pass


def load_json(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PlatformReviewError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PlatformReviewError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PlatformReviewError(f"JSON root must be an object: {path}")
    return payload


def find_forbidden_keys(value: Any, *, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            if key_text.lower() in FORBIDDEN_EVIDENCE_KEYS:
                found.append(path)
            found.extend(find_forbidden_keys(nested, prefix=path))
    elif isinstance(value, list):
        for idx, nested in enumerate(value):
            found.extend(find_forbidden_keys(nested, prefix=f"{prefix}[{idx}]"))
    return found


def require_text(review: dict[str, Any], field: str) -> None:
    if not str(review.get(field) or "").strip():
        raise PlatformReviewError(f"{field} is required")


def validate_platform_review(review: dict[str, Any], policy: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_REVIEW_FIELDS - set(review))
    if missing:
        raise PlatformReviewError("missing required fields: " + ", ".join(missing))

    forbidden = find_forbidden_keys(review)
    if forbidden:
        raise PlatformReviewError("review evidence contains forbidden secret fields: " + ", ".join(forbidden))

    require_text(review, "reviewed_at")
    require_text(review, "adapter_item")
    platform_key = str(review.get("platform") or "")
    platforms = policy.get("platforms")
    if not isinstance(platforms, dict) or platform_key not in platforms:
        raise PlatformReviewError(f"unknown platform: {platform_key}")

    platform_policy = platforms[platform_key]
    docs_reviewed = review.get("official_docs_reviewed")
    if not isinstance(docs_reviewed, list) or not docs_reviewed:
        raise PlatformReviewError("official_docs_reviewed must be a non-empty array")
    for url in docs_reviewed:
        if url not in platform_policy["official_docs"]:
            raise PlatformReviewError(f"official doc is not listed in policy for {platform_key}: {url}")

    capabilities_reviewed = review.get("capabilities_reviewed")
    if not isinstance(capabilities_reviewed, dict) or not capabilities_reviewed:
        raise PlatformReviewError("capabilities_reviewed must be a non-empty object")

    policy_capabilities = platform_policy["capabilities"]
    for capability, payload in capabilities_reviewed.items():
        if capability not in policy_capabilities:
            raise PlatformReviewError(f"unknown capability for {platform_key}: {capability}")
        if not isinstance(payload, dict):
            raise PlatformReviewError(f"{capability} review must be an object")
        expected_status = policy_capabilities[capability]["status"]
        actual_status = str(payload.get("policy_status") or "")
        if actual_status != expected_status:
            raise PlatformReviewError(
                f"{capability} status mismatch: review={actual_status} policy={expected_status}"
            )
        if not str(payload.get("implementation_decision") or "").strip():
            raise PlatformReviewError(f"{capability}.implementation_decision is required")

    for field in ("rate_limit_policy", "data_retention_policy", "credentialed_smoke"):
        payload = review.get(field)
        if not isinstance(payload, dict):
            raise PlatformReviewError(f"{field} must be an object")
        if not str(payload.get("decision") or "").strip():
            raise PlatformReviewError(f"{field}.decision is required")
        if not str(payload.get("evidence") or "").strip():
            raise PlatformReviewError(f"{field}.evidence is required")

    fallbacks = review.get("disallowed_fallbacks")
    if not isinstance(fallbacks, list) or not fallbacks:
        raise PlatformReviewError("disallowed_fallbacks must be a non-empty array")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate platform adapter policy review JSON.")
    parser.add_argument("--review", required=True, help="Path to platform review JSON.")
    parser.add_argument(
        "--policy",
        default=str(DEFAULT_POLICY_PATH),
        help="Path to platform policy JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        policy = load_json(args.policy)
        review = load_json(args.review)
        validate_platform_review(review, policy)
    except PlatformReviewError as exc:
        print(f"Platform review validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"Platform review validation passed: {args.review}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
