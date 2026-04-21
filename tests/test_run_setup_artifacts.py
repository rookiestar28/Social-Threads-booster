import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_setup_artifacts.py"
TRACKER_FIXTURE = REPO_ROOT / "examples" / "tracker-example.json"
TMP_DIR = REPO_ROOT / ".tmp"


class RunSetupArtifactsCliTests(unittest.TestCase):
    def test_generates_default_setup_artifacts_without_brand_voice(self) -> None:
        output_dir = TMP_DIR / f"setup-artifacts-{uuid.uuid4().hex}"
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--tracker",
                    str(TRACKER_FIXTURE),
                    "--output-dir",
                    str(output_dir),
                ],
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertTrue((output_dir / "style_guide.md").exists())
            self.assertTrue((output_dir / "concept_library.md").exists())
            self.assertFalse((output_dir / "brand_voice.md").exists())
            self.assertTrue((output_dir / "歷史貼文-按時間排序.md").exists())
            self.assertTrue((output_dir / "歷史貼文-按主題分類.md").exists())
            self.assertTrue((output_dir / "留言記錄.md").exists())
        finally:
            if output_dir.exists():
                shutil.rmtree(output_dir)

    def test_generates_brand_voice_when_flag_is_enabled(self) -> None:
        output_dir = TMP_DIR / f"setup-artifacts-{uuid.uuid4().hex}"
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--tracker",
                    str(TRACKER_FIXTURE),
                    "--output-dir",
                    str(output_dir),
                    "--include-brand-voice",
                ],
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertTrue((output_dir / "brand_voice.md").exists())
            brand_voice = (output_dir / "brand_voice.md").read_text(encoding="utf-8")
            self.assertIn("# Brand Voice Profile", brand_voice)
        finally:
            if output_dir.exists():
                shutil.rmtree(output_dir)


if __name__ == "__main__":
    unittest.main()
