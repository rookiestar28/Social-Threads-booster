#!/usr/bin/env python3
"""
Runtime capability registry backed by the platform API policy matrix.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ALLOWED_STATUSES = {"available", "available_with_owned_account", "limited"}
REVIEW_STATUSES = {"review_gated", "tier_gated", "unknown_verify_before_use"}


class CapabilityRegistryError(ValueError):
    """Raised when the capability registry cannot load or interpret policy data."""


@dataclass(frozen=True)
class CapabilityDecision:
    platform: str
    capability: str
    status: str
    gate: str
    allowed: bool
    requires_review: bool = False
    fallback: str | None = None


class CapabilityRegistry:
    def __init__(self, policy: dict[str, Any]) -> None:
        if not isinstance(policy.get("platforms"), dict):
            raise CapabilityRegistryError("policy.platforms must be an object")
        self.policy = policy
        self.platforms = policy["platforms"]

    @classmethod
    def from_policy_file(cls, path: str | Path) -> "CapabilityRegistry":
        policy_path = Path(path)
        return cls(json.loads(policy_path.read_text(encoding="utf-8")))

    def platform_exists(self, platform: str) -> bool:
        return platform in self.platforms

    def get_platform(self, platform: str) -> dict[str, Any] | None:
        row = self.platforms.get(platform)
        return row if isinstance(row, dict) else None

    def supports_account_context(self, platform: str, account_context: str) -> bool:
        row = self.get_platform(platform)
        if row is None:
            return False
        contexts = row.get("account_contexts") or []
        return account_context in contexts

    def get_capability(self, platform: str, capability: str) -> dict[str, Any] | None:
        row = self.get_platform(platform)
        if row is None:
            return None
        capabilities = row.get("capabilities") or {}
        payload = capabilities.get(capability)
        return payload if isinstance(payload, dict) else None

    def decide(self, platform: str, capability: str) -> CapabilityDecision:
        if not self.platform_exists(platform):
            return CapabilityDecision(
                platform=platform,
                capability=capability,
                status="unknown_platform",
                gate="platform is not defined in the capability registry",
                allowed=False,
                requires_review=True,
                fallback="stop",
            )

        payload = self.get_capability(platform, capability)
        if payload is None:
            return CapabilityDecision(
                platform=platform,
                capability=capability,
                status="unknown_capability",
                gate="capability is not defined for this platform",
                allowed=False,
                requires_review=True,
                fallback="stop",
            )

        status = str(payload.get("status", "unknown_verify_before_use"))
        gate = str(payload.get("gate", "verify capability before use"))
        if status in ALLOWED_STATUSES:
            return CapabilityDecision(
                platform=platform,
                capability=capability,
                status=status,
                gate=gate,
                allowed=True,
                requires_review=False,
                fallback=None,
            )

        if status == "not_publicly_available":
            fallback = "do_not_scrape"
        else:
            fallback = "review_required"

        return CapabilityDecision(
            platform=platform,
            capability=capability,
            status=status,
            gate=gate,
            allowed=False,
            requires_review=status in REVIEW_STATUSES,
            fallback=fallback,
        )
