import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "legacy_migration.py"


def load_module():
    spec = importlib.util.spec_from_file_location("legacy_migration", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load legacy_migration module")
    module = importlib.util.module_from_spec(spec)
    scripts_dir = str(MODULE_PATH.parent)
    original_sys_path = list(sys.path)
    try:
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = original_sys_path
    return module


class LegacyMigrationTests(unittest.TestCase):
    def test_detects_legacy_tracker_heuristics(self) -> None:
        migration = load_module()

        self.assertTrue(migration.is_legacy_tracker({"_meta": {"account": "@old"}, "posts": {}}))
        self.assertTrue(
            migration.is_legacy_tracker(
                {"posts": [{"id": "p1", "data_snapshots": [{"views": 1}]}]}
            )
        )
        self.assertFalse(migration.is_legacy_tracker({"account": {}, "posts": []}))

    def test_migrates_legacy_fields_snapshots_and_author_replies(self) -> None:
        migration = load_module()
        legacy = {
            "_meta": {"account": "@old", "last_updated": "2026-04-18"},
            "posts": {
                "legacy-1": {
                    "title": "Short title",
                    "date": "2026-04-17 13:36",
                    "topic": "SEO",
                    "type": "opinion",
                    "data_snapshots": [
                        {
                            "snapshot_date": "2026-04-18 13:36",
                            "views": 100,
                            "likes": 10,
                            "replies_count": 3,
                            "reposts": 2,
                            "shares": 1,
                        }
                    ],
                    "my_replies": [{"text": "Thanks", "created_at": "2026-04-18 14:00"}],
                }
            },
        }

        tracker, report = migration.migrate_legacy_tracker(legacy)

        self.assertEqual(tracker["account"]["handle"], "@old")
        self.assertEqual(tracker["account"]["source"], "legacy-migration")
        self.assertEqual(tracker["last_updated"], "2026-04-18T00:00:00+00:00")
        self.assertEqual(report["posts_migrated"], 1)
        self.assertEqual(report["author_replies_preserved"], 1)
        post = tracker["posts"][0]
        self.assertEqual(post["id"], "legacy-1")
        self.assertEqual(post["text"], "Short title")
        self.assertEqual(post["topics"], ["SEO"])
        self.assertEqual(post["metrics"]["views"], 100)
        self.assertEqual(post["metrics"]["replies"], 3)
        self.assertEqual(post["snapshots"][0]["captured_at"], "2026-04-18T13:36:00+00:00")
        self.assertTrue(post["my_replies"])
        self.assertEqual(post["author_replies"][0]["text"], "Thanks")

    def test_markdown_enrichment_replaces_thin_text_and_attaches_comments(self) -> None:
        migration = load_module()
        legacy = {
            "_meta": {"account": "@old"},
            "posts": {
                "legacy-1": {
                    "title": "Short title",
                    "date": "2026-04-17 13:36",
                    "topic": "SEO",
                    "data_snapshots": [],
                }
            },
        }
        posts_markdown = """### 2026-04-17 13:40
**分類：** SEO

This is the recovered full post body from the archive.
It has enough detail to replace the legacy title.
---
"""
        comments_markdown = """### 2026-04-18 10:00
This is a likely comment for the prior post.
---
### 2026-05-10 10:00
This comment is too far away.
---
"""

        tracker, report = migration.migrate_legacy_tracker(
            legacy,
            posts_markdown=posts_markdown,
            comments_markdown=comments_markdown,
        )

        post = tracker["posts"][0]
        self.assertIn("recovered full post body", post["text"])
        self.assertEqual(post["title"], "Short title")
        self.assertEqual(len(post["comments"]), 1)
        self.assertEqual(len(tracker["unmatched_comments"]), 1)
        self.assertEqual(report["comments_attached"], 1)
        self.assertEqual(report["unmatched_comments"], 1)


if __name__ == "__main__":
    unittest.main()
