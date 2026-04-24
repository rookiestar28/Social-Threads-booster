import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "capability_registry.py"
POLICY_PATH = REPO_ROOT / "knowledge" / "platform_api_policy.json"


def load_module():
    spec = importlib.util.spec_from_file_location("capability_registry", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load capability_registry")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CapabilityRegistryTests(unittest.TestCase):
    def test_available_capability_is_allowed(self) -> None:
        registry_module = load_module()
        registry = registry_module.CapabilityRegistry.from_policy_file(POLICY_PATH)

        decision = registry.decide("youtube", "read_posts")

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.status, "available")
        self.assertEqual(decision.platform, "youtube")

    def test_review_gated_capability_fails_closed(self) -> None:
        registry_module = load_module()
        registry = registry_module.CapabilityRegistry.from_policy_file(POLICY_PATH)

        decision = registry.decide("threads", "publish_text")

        self.assertFalse(decision.allowed)
        self.assertTrue(decision.requires_review)
        self.assertEqual(decision.status, "review_gated")
        self.assertIn("publishing permissions", decision.gate)

    def test_unavailable_capability_blocks_scraping_fallback(self) -> None:
        registry_module = load_module()
        registry = registry_module.CapabilityRegistry.from_policy_file(POLICY_PATH)

        decision = registry.decide("threads", "search_public_content")

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.status, "not_publicly_available")
        self.assertIn("do not implement", decision.gate)

    def test_unknown_platform_returns_blocked_decision(self) -> None:
        registry_module = load_module()
        registry = registry_module.CapabilityRegistry.from_policy_file(POLICY_PATH)

        decision = registry.decide("unknown", "read_posts")

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.status, "unknown_platform")

    def test_account_context_validation_uses_policy_contexts(self) -> None:
        registry_module = load_module()
        registry = registry_module.CapabilityRegistry.from_policy_file(POLICY_PATH)

        self.assertTrue(registry.supports_account_context("reddit", "subreddit"))
        self.assertFalse(registry.supports_account_context("reddit", "youtube_channel"))


if __name__ == "__main__":
    unittest.main()
