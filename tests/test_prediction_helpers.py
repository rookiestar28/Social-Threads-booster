import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "prediction_helpers.py"


def load_module():
    spec = importlib.util.spec_from_file_location("prediction_helpers", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load prediction_helpers module")
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


def snapshot() -> dict:
    return {
        "predicted_at": "2026-04-21T10:00:00+00:00",
        "data_path": "full tracker",
        "comparable_posts_used": 5,
        "confidence_level": "Usable",
        "ranges": {
            "views": {"conservative": 100, "baseline": 150, "optimistic": 240},
            "likes": {"conservative": 10, "baseline": 15, "optimistic": 24},
            "replies": {"conservative": 1, "baseline": 2, "optimistic": 4},
            "reposts": {"conservative": 0, "baseline": 1, "optimistic": 2},
            "shares": {"conservative": 2, "baseline": 3, "optimistic": 5},
        },
        "upside_drivers": ["clear hook"],
        "uncertainty_factors": ["small sample"],
    }


class PredictionHelpersTests(unittest.TestCase):
    def test_validate_prediction_snapshot_rejects_quotes_range(self) -> None:
        helpers = load_module()
        bad = snapshot()
        bad["ranges"]["quotes"] = {"conservative": 0, "baseline": 1, "optimistic": 2}

        with self.assertRaisesRegex(ValueError, "quotes"):
            helpers.validate_prediction_snapshot(bad)

    def test_render_prediction_range_table(self) -> None:
        helpers = load_module()

        table = helpers.render_prediction_range_table(snapshot())

        self.assertIn("| Metric | Conservative | Baseline | Optimistic |", table)
        self.assertIn("| Views | 100 | 150 | 240 |", table)
        self.assertIn("| Shares | 2 | 3 | 5 |", table)

    def test_persist_keep_both_preserves_existing_snapshot_history(self) -> None:
        helpers = load_module()
        tracker_utils = helpers.tracker_utils
        old_snapshot = snapshot()
        new_snapshot = snapshot()
        new_snapshot["predicted_at"] = "2026-04-22T10:00:00+00:00"
        tracker = tracker_utils.build_empty_tracker(
            posts=[
                tracker_utils.build_post_record(
                    post_id="post-1",
                    text="Post",
                    created_at="2026-04-21T09:00:00+00:00",
                    source_path="api",
                    data_completeness="full",
                    prediction_snapshot=old_snapshot,
                )
            ]
        )

        result = helpers.persist_prediction_snapshot(
            tracker,
            new_snapshot,
            post_id="post-1",
            overwrite_policy="keep-both",
            now="2026-04-22T10:00:00+00:00",
        )

        post = tracker["posts"][0]
        self.assertTrue(result["persisted"])
        self.assertEqual(post["prediction_snapshot"]["predicted_at"], "2026-04-22T10:00:00+00:00")
        self.assertEqual(post["prediction_snapshot_history"][0]["predicted_at"], "2026-04-21T10:00:00+00:00")

    def test_persist_prediction_creates_pending_placeholder_for_draft(self) -> None:
        helpers = load_module()
        tracker_utils = helpers.tracker_utils
        tracker = tracker_utils.build_empty_tracker(posts=[])

        result = helpers.persist_prediction_snapshot(
            tracker,
            snapshot(),
            draft_text="This is an unpublished draft",
            overwrite_policy="replace",
            now="2026-04-22T10:00:00+00:00",
        )

        self.assertTrue(result["persisted"])
        self.assertTrue(tracker["posts"][0]["id"].startswith("pending-"))
        self.assertEqual(tracker["posts"][0]["source"]["import_path"], "prediction-placeholder")
        self.assertEqual(tracker["posts"][0]["prediction_snapshot"]["confidence_level"], "Usable")


if __name__ == "__main__":
    unittest.main()
