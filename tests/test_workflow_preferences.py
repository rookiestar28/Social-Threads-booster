import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "workflow_preferences.py"


def load_module():
    spec = importlib.util.spec_from_file_location("workflow_preferences", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load workflow_preferences module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class WorkflowPreferencesTests(unittest.TestCase):
    def test_missing_config_returns_safe_defaults(self) -> None:
        module = load_module()

        config = module.load_preferences(Path("missing-social-booster-config.json"))

        self.assertEqual(config["version"], 1)
        self.assertEqual(config["workflows"]["draft"]["discussion_mode"], "fast")
        self.assertTrue(config["workflows"]["draft"]["research_angle_expansion"])
        self.assertEqual(config["workflows"]["analyze"]["discussion_mode"], "fast")
        self.assertEqual(config["workflows"]["review"]["discussion_mode"], "fast")

    def test_valid_config_merges_with_defaults(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "social_booster_config.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "workflows": {
                            "draft": {"discussion_mode": "discussion"},
                            "review": {"discussion_mode": "auto"},
                        },
                        "platforms": {"threads": {"content_profile": "default"}},
                    }
                ),
                encoding="utf-8",
            )

            config = module.load_preferences(path)

        self.assertEqual(config["workflows"]["draft"]["discussion_mode"], "discussion")
        self.assertTrue(config["workflows"]["draft"]["research_angle_expansion"])
        self.assertEqual(config["workflows"]["analyze"]["discussion_mode"], "fast")
        self.assertEqual(config["workflows"]["review"]["discussion_mode"], "auto")
        self.assertEqual(config["platforms"]["threads"]["content_profile"], "default")

    def test_invalid_discussion_mode_is_rejected(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "social_booster_config.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "workflows": {
                            "draft": {"discussion_mode": "chatty"},
                        },
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "draft.discussion_mode"):
                module.load_preferences(path)

    def test_secret_like_preference_keys_are_rejected(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "social_booster_config.json"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "workflows": {
                            "draft": {
                                "discussion_mode": "fast",
                                "api_token": "do-not-store",
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "secret-like"):
                module.load_preferences(path)


if __name__ == "__main__":
    unittest.main()
