import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "review_helpers.py"


def load_module():
    spec = importlib.util.spec_from_file_location("review_helpers", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load review_helpers module")
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


def prediction_snapshot() -> dict:
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
        "upside_drivers": [],
        "uncertainty_factors": [],
    }


class ReviewHelpersTests(unittest.TestCase):
    def test_build_prediction_comparison_classifies_band_hits(self) -> None:
        helpers = load_module()

        rows = helpers.build_prediction_comparison(
            prediction_snapshot(),
            {"views": 260, "likes": 15, "replies": 0, "reposts": 1, "shares": 4},
        )
        by_metric = {row["metric"]: row for row in rows}

        self.assertEqual(by_metric["views"]["band_hit"], "Over")
        self.assertEqual(by_metric["likes"]["band_hit"], "In")
        self.assertEqual(by_metric["replies"]["band_hit"], "Under")
        self.assertEqual(by_metric["views"]["deviation_vs_baseline_pct"], 73.33)

    def test_render_prediction_comparison_table(self) -> None:
        helpers = load_module()
        rows = helpers.build_prediction_comparison(
            prediction_snapshot(),
            {"views": 150, "likes": 15, "replies": 2, "reposts": 1, "shares": 3},
        )

        table = helpers.render_prediction_comparison_table(rows)

        self.assertIn("| Metric | Conservative | Baseline | Optimistic | Actual | Band hit? | Deviation vs baseline |", table)
        self.assertIn("| Views | 100 | 150 | 240 | 150 | In | 0.0% |", table)

    def test_apply_review_state_update_preserves_schema(self) -> None:
        helpers = load_module()
        tracker_utils = helpers.tracker_utils
        post = tracker_utils.build_post_record(
            post_id="post-1",
            text="Post",
            created_at="2026-04-21T09:00:00+00:00",
            source_path="api",
            data_completeness="full",
        )

        helpers.apply_review_state_update(
            post,
            checkpoint_hours=24,
            deviation_summary="Views landed inside baseline band.",
            calibration_notes=["Prediction was well calibrated."],
            now="2026-04-22T10:00:00+00:00",
        )

        self.assertEqual(post["review_state"]["actual_checkpoint_hours"], 24)
        self.assertEqual(post["review_state"]["deviation_summary"], "Views landed inside baseline band.")
        self.assertEqual(post["review_state"]["calibration_notes"], ["Prediction was well calibrated."])
        self.assertEqual(post["review_state"]["last_reviewed_at"], "2026-04-22T10:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
