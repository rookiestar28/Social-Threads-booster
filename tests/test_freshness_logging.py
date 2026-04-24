import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "freshness_logging.py"
SCRIPT_PATH = REPO_ROOT / "scripts" / "log_freshness_audit.py"
TMP_DIR = REPO_ROOT / ".tmp"


def load_module():
    spec = importlib.util.spec_from_file_location("freshness_logging", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load freshness_logging module")
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


class FreshnessLoggingTests(unittest.TestCase):
    def test_build_topics_entry_uses_contract_shape(self) -> None:
        freshness_logging = load_module()

        entry = freshness_logging.build_topics_freshness_entry(
            candidate="technical-seo-checklist",
            status="performed",
            verdict="green",
            web_search_query="technical seo checklist 2026",
            run_id="run-123",
        )

        self.assertEqual(entry["skill"], "topics")
        self.assertEqual(entry["candidate"], "technical-seo-checklist")
        self.assertEqual(entry["status"], "performed")
        self.assertEqual(entry["verdict"], "green")
        self.assertEqual(entry["run_id"], "run-123")
        self.assertIn("ts", entry)

    def test_cli_appends_draft_freshness_entry(self) -> None:
        case_dir = TMP_DIR / f"freshness-log-{uuid.uuid4().hex}"
        log_path = case_dir / "threads_freshness.log"

        try:
            case_dir.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--skill",
                    "draft",
                    "--target",
                    "seo-recovery-playbook",
                    "--status",
                    "skipped_by_user",
                    "--outcome",
                    "yellow",
                    "--web-search-query",
                    "seo recovery playbook 2026",
                    "--log-file",
                    str(log_path),
                ],
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertTrue(log_path.exists(), "freshness CLI did not create threads_freshness.log")

            lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertEqual(entry["skill"], "draft")
            self.assertEqual(entry["topic"], "seo-recovery-playbook")
            self.assertEqual(entry["status"], "skipped_by_user")
            self.assertEqual(entry["decision"], "yellow")
        finally:
            if case_dir.exists():
                shutil.rmtree(case_dir)

    def test_build_draft_entry_accepts_bounded_decision_audit_fields(self) -> None:
        freshness_logging = load_module()

        entry = freshness_logging.build_draft_freshness_entry(
            topic="seo-recovery-playbook",
            status="performed",
            decision="green",
            web_search_query="seo recovery playbook 2026",
            run_id="run-123",
            discussion_mode="discussion",
            discussion_ran=True,
            user_decisions=["accepted_yellow_reframe", "dropped_unverified_claim"],
            personal_fact_conflicts=["needs_confirmation"],
        )

        self.assertEqual(entry["discussion_mode"], "discussion")
        self.assertTrue(entry["discussion_ran"])
        self.assertEqual(entry["user_decisions"], ["accepted_yellow_reframe", "dropped_unverified_claim"])
        self.assertEqual(entry["personal_fact_conflicts"], ["needs_confirmation"])

    def test_cli_appends_draft_decision_audit_fields(self) -> None:
        case_dir = TMP_DIR / f"freshness-log-{uuid.uuid4().hex}"
        log_path = case_dir / "threads_freshness.log"

        try:
            case_dir.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--skill",
                    "draft",
                    "--target",
                    "seo-recovery-playbook",
                    "--status",
                    "performed",
                    "--outcome",
                    "green",
                    "--web-search-query",
                    "seo recovery playbook 2026",
                    "--discussion-mode",
                    "discussion",
                    "--discussion-ran",
                    "--user-decision",
                    "accepted_yellow_reframe",
                    "--personal-fact-conflict",
                    "needs_confirmation",
                    "--log-file",
                    str(log_path),
                ],
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            entry = json.loads(log_path.read_text(encoding="utf-8").strip())
            self.assertEqual(entry["discussion_mode"], "discussion")
            self.assertTrue(entry["discussion_ran"])
            self.assertEqual(entry["user_decisions"], ["accepted_yellow_reframe"])
            self.assertEqual(entry["personal_fact_conflicts"], ["needs_confirmation"])
        finally:
            if case_dir.exists():
                shutil.rmtree(case_dir)


if __name__ == "__main__":
    unittest.main()
