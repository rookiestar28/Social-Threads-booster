import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "validate_repo.py"


def load_module():
    spec = importlib.util.spec_from_file_location("validate_repo", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load validate_repo module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ValidateRepoTests(unittest.TestCase):
    def test_build_validation_steps_marks_precommit_optional_without_config(self) -> None:
        validate_repo = load_module()

        steps = validate_repo.build_validation_steps(
            python_executable="python",
            repo_root=REPO_ROOT,
            include_precommit=True,
        )

        self.assertEqual(steps[0].name, "pre-commit detect-secrets")
        self.assertTrue(steps[0].optional)
        self.assertIn(".pre-commit-config.yaml missing", steps[0].skip_reason)
        self.assertIn("python regression tests", [step.name for step in steps])
        self.assertIn("cli e2e", [step.name for step in steps])

    def test_required_step_failure_makes_summary_fail(self) -> None:
        validate_repo = load_module()
        results = [
            validate_repo.StepResult(name="optional", returncode=None, skipped=True, optional=True, skip_reason="missing"),
            validate_repo.StepResult(name="required", returncode=1, skipped=False, optional=False, skip_reason=None),
        ]

        self.assertFalse(validate_repo.results_passed(results))

    def test_skipped_optional_steps_do_not_fail_summary(self) -> None:
        validate_repo = load_module()
        results = [
            validate_repo.StepResult(name="optional", returncode=None, skipped=True, optional=True, skip_reason="missing"),
            validate_repo.StepResult(name="required", returncode=0, skipped=False, optional=False, skip_reason=None),
        ]

        self.assertTrue(validate_repo.results_passed(results))


if __name__ == "__main__":
    unittest.main()
