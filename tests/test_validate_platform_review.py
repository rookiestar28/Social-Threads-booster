import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "validate_platform_review.py"
SCRIPT_PATH = MODULE_PATH
POLICY_PATH = REPO_ROOT / "knowledge" / "platform_api_policy.json"
EXAMPLE_PATH = REPO_ROOT / "examples" / "platform-adapter-review-example.json"
TMP_DIR = REPO_ROOT / ".tmp"


def load_module():
    spec = importlib.util.spec_from_file_location("validate_platform_review", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load validate_platform_review module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PlatformReviewValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.case_dir = TMP_DIR / f"platform-review-{uuid.uuid4().hex}"
        self.case_dir.mkdir(parents=True, exist_ok=True)
        self.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        self.review = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

    def tearDown(self) -> None:
        if self.case_dir.exists():
            shutil.rmtree(self.case_dir)

    def write_review(self, payload: dict) -> Path:
        path = self.case_dir / "review.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_example_review_validates(self) -> None:
        module = load_module()
        module.validate_platform_review(self.review, self.policy)

    def test_rejects_unknown_platform(self) -> None:
        module = load_module()
        review = copy.deepcopy(self.review)
        review["platform"] = "unknown"

        with self.assertRaises(module.PlatformReviewError):
            module.validate_platform_review(review, self.policy)

    def test_rejects_capability_status_mismatch(self) -> None:
        module = load_module()
        review = copy.deepcopy(self.review)
        review["capabilities_reviewed"]["read_posts"]["policy_status"] = "available"

        with self.assertRaises(module.PlatformReviewError):
            module.validate_platform_review(review, self.policy)

    def test_rejects_missing_required_policy_section(self) -> None:
        module = load_module()
        review = copy.deepcopy(self.review)
        del review["rate_limit_policy"]

        with self.assertRaises(module.PlatformReviewError):
            module.validate_platform_review(review, self.policy)

    def test_rejects_secret_like_evidence_keys(self) -> None:
        module = load_module()
        review = copy.deepcopy(self.review)
        review["credentialed_smoke"]["access_token"] = "secret"

        with self.assertRaises(module.PlatformReviewError):
            module.validate_platform_review(review, self.policy)

    def test_cli_validates_example(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--review", str(EXAMPLE_PATH)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        self.assertIn("validation passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
