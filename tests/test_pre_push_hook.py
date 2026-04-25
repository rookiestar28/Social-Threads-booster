import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = REPO_ROOT / ".githooks" / "pre-push"
PRE_PUSH_SCRIPT = REPO_ROOT / "scripts" / "pre_push_checks.sh"
INSTALLER_PATH = REPO_ROOT / "scripts" / "install_git_hooks.py"


def load_installer():
    spec = importlib.util.spec_from_file_location("install_git_hooks", INSTALLER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load install_git_hooks")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PrePushHookTests(unittest.TestCase):
    def test_tracked_pre_push_hook_delegates_to_repo_script(self) -> None:
        self.assertTrue(HOOK_PATH.exists(), ".githooks/pre-push must be tracked")
        content = HOOK_PATH.read_text(encoding="utf-8")

        self.assertIn("#!/usr/bin/env bash", content)
        self.assertIn("git rev-parse --show-toplevel", content)
        self.assertIn("scripts/pre_push_checks.sh", content)

    def test_pre_push_script_runs_validate_repo_with_project_venv(self) -> None:
        self.assertTrue(PRE_PUSH_SCRIPT.exists(), "scripts/pre_push_checks.sh must exist")
        content = PRE_PUSH_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("validate_repo.py", content)
        self.assertIn(".venv-wsl", content)
        self.assertIn(".venv", content)
        self.assertIn("scripts/requirements.txt", content)
        self.assertNotIn("npm test", content)
        self.assertNotIn("node -", content)

    def test_installer_configures_core_hooks_path(self) -> None:
        installer = load_installer()

        self.assertEqual(installer.HOOKS_PATH, ".githooks")
        self.assertEqual(installer.build_git_config_command(), ["git", "config", "core.hooksPath", ".githooks"])

    def test_installer_validates_pre_push_hook_presence(self) -> None:
        installer = load_installer()

        installer.validate_hook_layout(REPO_ROOT)


if __name__ == "__main__":
    unittest.main()
