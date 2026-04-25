import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "platform_workflow_routing.py"
SCHEMA_PATH = REPO_ROOT / "scripts" / "platform_schema.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    scripts_dir = str(path.parent)
    original_sys_path = list(sys.path)
    try:
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = original_sys_path
    return module


def build_tracker():
    schema = load_module("platform_schema", SCHEMA_PATH)
    posts = [
        schema.build_platform_post(
            platform="threads",
            account_id="threads:@brand",
            platform_post_id="th_1",
            text="Text-native post",
            created_at="2026-04-01T00:00:00+00:00",
            content_format="text",
            metrics={"view_count": 100, "reaction_count": 10, "comment_count": 2, "share_count": 1},
        ),
        schema.build_platform_post(
            platform="youtube",
            account_id="youtube:channel-1",
            platform_post_id="yt_1",
            text="Video post",
            created_at="2026-04-02T00:00:00+00:00",
            content_format="video",
            metrics={"view_count": 1000, "reaction_count": 50, "comment_count": 5, "watch_time_seconds": 300},
        ),
        schema.build_platform_post(
            platform="pinterest",
            account_id="pinterest:user:brand",
            platform_post_id="pin_1",
            text="Pin post",
            created_at="2026-04-03T00:00:00+00:00",
            content_format="image",
            metrics={"view_count": 800, "save_count": 30, "click_count": 10},
        ),
    ]
    return schema.build_platform_tracker(posts=posts)


class PlatformWorkflowRoutingTests(unittest.TestCase):
    def test_filters_to_target_platform_and_reports_video_constraints(self):
        routing = load_module("platform_workflow_routing", MODULE_PATH)

        plan = routing.route_tracker_for_workflow(build_tracker(), workflow="draft", target_platforms=["youtube"])

        self.assertEqual(plan.workflow, "draft")
        self.assertEqual(plan.selected_platforms, ("youtube",))
        self.assertEqual(len(plan.routes), 1)
        route = plan.routes[0]
        self.assertEqual(route.platform, "youtube")
        self.assertEqual(route.post_count, 1)
        self.assertIn("video", route.content_formats)
        self.assertIn("video-first", " ".join(route.workflow_notes))
        self.assertIn("save_count", route.unavailable_metrics)

    def test_mixed_platform_selection_warns_and_keeps_metrics_per_platform(self):
        routing = load_module("platform_workflow_routing", MODULE_PATH)

        plan = routing.route_tracker_for_workflow(build_tracker(), workflow="predict", target_platforms=["threads", "youtube"])

        self.assertEqual(plan.selected_platforms, ("threads", "youtube"))
        self.assertIn("mixed-platform", " ".join(plan.global_warnings).lower())
        by_platform = {route.platform: route for route in plan.routes}
        self.assertIn("watch_time_seconds", by_platform["youtube"].supported_metrics)
        self.assertNotIn("watch_time_seconds", by_platform["threads"].supported_metrics)
        self.assertTrue(any("fewer than 5" in note for note in by_platform["threads"].workflow_notes))

    def test_unknown_target_platform_is_rejected(self):
        routing = load_module("platform_workflow_routing", MODULE_PATH)

        with self.assertRaisesRegex(routing.PlatformWorkflowRoutingError, "unknown platform"):
            routing.route_tracker_for_workflow(build_tracker(), workflow="topics", target_platforms=["threads", "unknown"])

    def test_routes_all_platforms_when_no_target_is_provided(self):
        routing = load_module("platform_workflow_routing", MODULE_PATH)

        plan = routing.route_tracker_for_workflow(build_tracker(), workflow="analyze")

        self.assertEqual(plan.selected_platforms, ("pinterest", "threads", "youtube"))
        self.assertEqual({route.platform for route in plan.routes}, {"threads", "youtube", "pinterest"})
        pinterest = [route for route in plan.routes if route.platform == "pinterest"][0]
        self.assertIn("media-centric", " ".join(pinterest.workflow_notes))

    def test_invalid_workflow_is_rejected(self):
        routing = load_module("platform_workflow_routing", MODULE_PATH)

        with self.assertRaisesRegex(routing.PlatformWorkflowRoutingError, "unsupported workflow"):
            routing.route_tracker_for_workflow(build_tracker(), workflow="review")


if __name__ == "__main__":
    unittest.main()
