import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "review_log_health.py"
SCRIPT_PATH = REPO_ROOT / "scripts" / "summarize_log_health.py"
TMP_DIR = REPO_ROOT / ".tmp"


def load_module():
    spec = importlib.util.spec_from_file_location("review_log_health", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load review_log_health module")
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


class ReviewLogHealthTests(unittest.TestCase):
    def test_summarizes_freshness_runs_by_run_id_and_topic_presence(self) -> None:
        review_log_health = load_module()

        entries = [
            {
                "ts": "2026-04-21T10:00:00+00:00",
                "run_id": "run-a",
                "skill": "topics",
                "candidate": "seo-recovery-playbook",
                "status": "performed",
                "verdict": "green",
                "web_search_query": "seo recovery playbook 2026",
            },
            {
                "ts": "2026-04-21T10:00:10+00:00",
                "run_id": "run-b",
                "skill": "draft",
                "topic": "technical-seo-checklist",
                "status": "skipped_by_user",
                "decision": "yellow",
                "web_search_query": "technical seo checklist 2026",
            },
        ]

        summary = review_log_health.summarize_freshness_log(
            entries,
            current_topic_slug="seo-recovery-playbook",
        )

        self.assertEqual(summary["healthy_runs"], 1)
        self.assertEqual(summary["degraded_runs"], 1)
        self.assertTrue(summary["current_topic_seen"])
        self.assertEqual(summary["draft_decision_runs"], 0)

    def test_summarizes_draft_decision_audit_evidence(self) -> None:
        review_log_health = load_module()

        entries = [
            {
                "ts": "2026-04-21T10:00:00+00:00",
                "run_id": "run-a",
                "skill": "draft",
                "topic": "seo-recovery-playbook",
                "status": "performed",
                "decision": "green",
                "discussion_mode": "discussion",
                "discussion_ran": True,
                "user_decisions": ["accepted_yellow_reframe", "dropped_unverified_claim"],
                "personal_fact_conflicts": ["needs_confirmation"],
            },
            {
                "ts": "2026-04-21T10:05:00+00:00",
                "run_id": "run-b",
                "skill": "draft",
                "topic": "technical-seo-checklist",
                "status": "performed",
                "decision": "green",
                "discussion_mode": "fast",
                "discussion_ran": False,
                "user_decisions": ["kept_original_hook"],
            },
        ]

        summary = review_log_health.summarize_freshness_log(entries)

        self.assertEqual(summary["draft_decision_runs"], 2)
        self.assertEqual(summary["discussion_runs"], 1)
        self.assertEqual(summary["personal_fact_conflict_runs"], 1)
        self.assertEqual(summary["user_decision_counts"]["accepted_yellow_reframe"], 1)
        self.assertEqual(summary["user_decision_counts"]["kept_original_hook"], 1)

    def test_cli_summarizes_refresh_and_freshness_logs(self) -> None:
        case_dir = TMP_DIR / f"review-log-health-{uuid.uuid4().hex}"
        refresh_log = case_dir / "threads_refresh.log"
        freshness_log = case_dir / "threads_freshness.log"

        try:
            case_dir.mkdir(parents=True, exist_ok=True)
            refresh_log.write_text(
                "\n".join(
                    [
                        json.dumps({"ts": "2026-04-21T08:00:00+00:00", "ok": True, "posts_scraped": 3, "new_posts": 0, "updated_posts": 3, "replies_added": 0}),
                        json.dumps({"ts": "2026-04-21T09:00:00+00:00", "ok": False, "reason": "selector_health_failed", "detail": "DOM drift"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            freshness_log.write_text(
                "\n".join(
                    [
                        json.dumps({"ts": "2026-04-21T10:00:00+00:00", "run_id": "run-a", "skill": "topics", "candidate": "seo-recovery-playbook", "status": "performed", "verdict": "green", "web_search_query": "seo recovery playbook 2026"}),
                        json.dumps({"ts": "2026-04-21T10:05:00+00:00", "run_id": "run-b", "skill": "draft", "topic": "technical-seo-checklist", "status": "skipped_by_user", "decision": "yellow", "web_search_query": "technical seo checklist 2026"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--refresh-log",
                    str(refresh_log),
                    "--freshness-log",
                    str(freshness_log),
                    "--current-topic-slug",
                    "seo-recovery-playbook",
                ],
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["refresh"]["ok_runs"], 1)
            self.assertEqual(payload["refresh"]["failed_runs"], 1)
            self.assertTrue(payload["refresh"]["recent_selector_health_failed"])
            self.assertTrue(payload["freshness"]["current_topic_seen"])
        finally:
            if case_dir.exists():
                shutil.rmtree(case_dir)


if __name__ == "__main__":
    unittest.main()
