import importlib.util
import json
import shutil
import unittest
from unittest import mock
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "tracker_utils.py"
TMP_DIR = REPO_ROOT / ".tmp"


def load_module():
    spec = importlib.util.spec_from_file_location("tracker_utils", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load tracker_utils module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TrackerUtilsTests(unittest.TestCase):
    def test_build_post_record_includes_required_defaults(self) -> None:
        tracker_utils = load_module()

        post = tracker_utils.build_post_record(
            post_id="post-1",
            text="Example post",
            created_at="2026-04-20T10:00:00+00:00",
            source_path="api",
            data_completeness="full",
            metrics={"views": 10, "likes": 2},
        )

        self.assertEqual(post["id"], "post-1")
        self.assertEqual(post["text"], "Example post")
        self.assertEqual(post["metrics"]["views"], 10)
        self.assertEqual(post["metrics"]["likes"], 2)
        self.assertEqual(post["metrics"]["replies"], 0)
        self.assertIn("algorithm_signals", post)
        self.assertIn("psychology_signals", post)
        self.assertIn("review_state", post)
        self.assertEqual(post["comments"], [])
        self.assertEqual(post["source"]["import_path"], "api")

    def test_hydrate_post_defaults_preserves_existing_values(self) -> None:
        tracker_utils = load_module()

        post = {
            "id": "post-2",
            "text": "Existing text",
            "created_at": "2026-04-20T10:00:00+00:00",
            "metrics": {"views": 99},
            "algorithm_signals": {"topic_freshness": {"semantic_cluster": "existing"}},
            "comments": [{"user": "x", "text": "y", "created_at": "", "likes": 0}],
        }

        tracker_utils.hydrate_post_defaults(post)

        self.assertEqual(post["metrics"]["views"], 99)
        self.assertEqual(post["algorithm_signals"]["topic_freshness"]["semantic_cluster"], "existing")
        self.assertEqual(len(post["comments"]), 1)
        self.assertIn("psychology_signals", post)
        self.assertIn("review_state", post)
        self.assertIn("performance_windows", post)
        self.assertIn("snapshots", post)

    def test_backup_tracker_rotates_with_bounded_retention(self) -> None:
        tracker_utils = load_module()

        case_dir = TMP_DIR / "tracker-utils-backups"
        tracker_path = case_dir / "threads_daily_tracker.json"

        try:
            case_dir.mkdir(parents=True, exist_ok=True)
            tracker_utils.save_tracker(
                tracker_path,
                tracker_utils.build_empty_tracker(account_handle="@example", source="api"),
            )

            for stamp in (
                "20260421T100000Z",
                "20260421T110000Z",
                "20260421T120000Z",
            ):
                tracker_utils.backup_tracker(tracker_path, keep=2, stamp=stamp)

            backups = sorted(case_dir.glob("threads_daily_tracker.json.bak-*"))
            self.assertEqual(len(backups), 2)
            self.assertEqual(
                [backup.name for backup in backups],
                [
                    "threads_daily_tracker.json.bak-20260421T110000Z",
                    "threads_daily_tracker.json.bak-20260421T120000Z",
                ],
            )
        finally:
            if case_dir.exists():
                shutil.rmtree(case_dir)

    def test_validate_tracker_accepts_shared_post_schema(self) -> None:
        tracker_utils = load_module()
        tracker = tracker_utils.build_empty_tracker(
            account_handle="@example",
            source="api",
            posts=[
                tracker_utils.build_post_record(
                    post_id="post-1",
                    text="Example post",
                    created_at="2026-04-20T10:00:00+00:00",
                    source_path="api",
                    data_completeness="full",
                    metrics={"views": 10},
                    snapshots=[
                        tracker_utils.build_metric_snapshot(
                            {"views": 10},
                            "2026-04-20T10:00:00+00:00",
                            captured_at="2026-04-20T11:00:00+00:00",
                        )
                    ],
                )
            ],
        )

        tracker_utils.validate_tracker(tracker)

    def test_validate_tracker_rejects_actionable_post_shape_errors(self) -> None:
        tracker_utils = load_module()
        tracker = tracker_utils.build_empty_tracker(
            posts=[
                {
                    "text": "Missing id",
                    "created_at": "2026-04-20T10:00:00+00:00",
                    "metrics": {"views": 1},
                    "comments": [],
                    "snapshots": [],
                    "source": {"import_path": "api", "data_completeness": "partial"},
                }
            ]
        )

        with self.assertRaisesRegex(tracker_utils.TrackerValidationError, r"posts\[0\]\.id"):
            tracker_utils.validate_tracker(tracker)

    def test_save_tracker_fails_before_writing_invalid_tracker(self) -> None:
        tracker_utils = load_module()
        case_dir = TMP_DIR / "tracker-utils-validation"
        tracker_path = case_dir / "threads_daily_tracker.json"
        invalid_tracker = tracker_utils.build_empty_tracker(posts=[{"id": "post-1"}])

        try:
            case_dir.mkdir(parents=True, exist_ok=True)
            with self.assertRaises(tracker_utils.TrackerValidationError):
                tracker_utils.save_tracker(tracker_path, invalid_tracker)
            self.assertFalse(tracker_path.exists())
        finally:
            if case_dir.exists():
                shutil.rmtree(case_dir)

    def test_save_tracker_preserves_existing_file_when_atomic_replace_fails(self) -> None:
        tracker_utils = load_module()
        case_dir = TMP_DIR / "tracker-utils-atomic"
        tracker_path = case_dir / "threads_daily_tracker.json"
        original_tracker = tracker_utils.build_empty_tracker(
            account_handle="@old",
            source="api",
            posts=[],
            last_updated="2026-04-20T10:00:00+00:00",
        )
        new_tracker = tracker_utils.build_empty_tracker(
            account_handle="@new",
            source="api",
            posts=[],
            last_updated="2026-04-21T10:00:00+00:00",
        )

        try:
            case_dir.mkdir(parents=True, exist_ok=True)
            tracker_path.write_text(json.dumps(original_tracker, ensure_ascii=False, indent=2), encoding="utf-8")

            with mock.patch.object(tracker_utils.os, "replace", side_effect=OSError("replace failed")):
                with self.assertRaisesRegex(OSError, "replace failed"):
                    tracker_utils.save_tracker(tracker_path, new_tracker)

            persisted = json.loads(tracker_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["account"]["handle"], "@old")
            self.assertEqual(list(case_dir.glob("threads_daily_tracker.json.tmp-*")), [])
        finally:
            if case_dir.exists():
                shutil.rmtree(case_dir)

    def test_append_metric_snapshot_updates_checkpoint_window(self) -> None:
        tracker_utils = load_module()
        post = tracker_utils.build_post_record(
            post_id="post-1",
            text="Post",
            created_at="2026-04-20T10:00:00+00:00",
            source_path="api",
            data_completeness="full",
            metrics={"views": 10},
        )

        snapshot = tracker_utils.append_metric_snapshot(
            post,
            {"views": 20, "likes": 2, "replies": 1, "reposts": 0, "quotes": 0, "shares": 0},
            captured_at="2026-04-21T10:00:00+00:00",
        )

        self.assertEqual(len(post["snapshots"]), 1)
        self.assertEqual(snapshot["hours_since_publish"], 24.0)
        self.assertEqual(post["performance_windows"]["24h"]["views"], 20)


if __name__ == "__main__":
    unittest.main()
