import subprocess
import sys
import unittest
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "generate_style_guide.py"
TRACKER_FIXTURE = REPO_ROOT / "examples" / "tracker-example.json"
TMP_DIR = REPO_ROOT / ".tmp"


class GenerateStyleGuideCliTests(unittest.TestCase):
    def test_generates_style_guide_from_example_tracker(self) -> None:
        TMP_DIR.mkdir(exist_ok=True)
        output_path = TMP_DIR / f"style_guide-{uuid.uuid4().hex}.md"
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--tracker",
                    str(TRACKER_FIXTURE),
                    "--output",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertTrue(output_path.exists(), "style_guide.md was not created")

            content = output_path.read_text(encoding="utf-8")
            self.assertIn("# Personalized Style Guide", content)
            self.assertIn("## Data Coverage", content)
            self.assertIn("## Hook Types", content)
            self.assertIn("## Content Types", content)
            self.assertIn("story", content.lower())
        finally:
            if output_path.exists():
                output_path.unlink()


if __name__ == "__main__":
    unittest.main()
