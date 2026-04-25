import importlib.util
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "check_internal_guardrails.py"
TMP_DIR = REPO_ROOT / ".tmp"


def load_module():
    spec = importlib.util.spec_from_file_location("check_internal_guardrails", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load check_internal_guardrails module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def remove_tree(path: Path) -> None:
    def clear_readonly(function, target, _exc_info):
        os.chmod(target, 0o700)
        function(target)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=clear_readonly)
    else:
        shutil.rmtree(path, onerror=clear_readonly)


class InternalGuardrailTests(unittest.TestCase):
    def setUp(self) -> None:
        self.case_dir = TMP_DIR / f"internal-guardrail-{uuid.uuid4().hex}"
        self.case_dir.mkdir(parents=True, exist_ok=True)
        run_git(self.case_dir, "init")
        run_git(self.case_dir, "config", "user.email", "test@example.invalid")
        run_git(self.case_dir, "config", "user.name", "Test User")

    def tearDown(self) -> None:
        if self.case_dir.exists():
            remove_tree(self.case_dir)

    def write_file(self, relative_path: str, content: str) -> None:
        path = self.case_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_passes_when_internal_paths_are_ignored_and_untracked(self) -> None:
        module = load_module()
        self.write_file(".gitignore", ".planning/\nreference/\nAGENTS.md\n")
        self.write_file(".planning/plan.md", "internal")
        self.write_file("reference/docs/note.md", "internal")
        self.write_file("AGENTS.md", "internal")

        results = module.check_paths(
            self.case_dir,
            [".planning/", "reference/", "AGENTS.md"],
        )

        self.assertTrue(all(result.ok for result in results))

    def test_fails_when_path_is_not_ignored(self) -> None:
        module = load_module()
        self.write_file(".gitignore", ".planning/\n")
        self.write_file("reference/docs/note.md", "internal")

        results = module.check_paths(self.case_dir, ["reference/"])

        self.assertFalse(results[0].ignored)
        self.assertFalse(results[0].ok)

    def test_fails_when_internal_path_is_tracked(self) -> None:
        module = load_module()
        self.write_file(".gitignore", "AGENTS.md\n")
        self.write_file("AGENTS.md", "internal")
        run_git(self.case_dir, "add", "-f", "AGENTS.md")
        run_git(self.case_dir, "commit", "-m", "track internal fixture")

        results = module.check_paths(self.case_dir, ["AGENTS.md"])

        self.assertTrue(results[0].ignored)
        self.assertEqual(results[0].tracked_paths, ("AGENTS.md",))
        self.assertFalse(results[0].ok)

    def test_cli_exits_nonzero_for_unignored_path(self) -> None:
        self.write_file(".gitignore", "")
        result = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                "--repo-root",
                str(self.case_dir),
                "--path",
                "reference/",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("reference/", result.stdout)


if __name__ == "__main__":
    unittest.main()
