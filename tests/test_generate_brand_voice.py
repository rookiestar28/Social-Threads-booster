import subprocess
import sys
import unittest
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "generate_brand_voice.py"
TRACKER_FIXTURE = REPO_ROOT / "examples" / "tracker-example.json"
TMP_DIR = REPO_ROOT / ".tmp"


class GenerateBrandVoiceCliTests(unittest.TestCase):
    def test_generates_brand_voice_from_example_tracker(self) -> None:
        TMP_DIR.mkdir(exist_ok=True)
        output_path = TMP_DIR / f"brand-voice-{uuid.uuid4().hex}.md"
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
            self.assertTrue(output_path.exists(), "brand_voice.md was not created")

            content = output_path.read_text(encoding="utf-8")
            self.assertIn("# Brand Voice Profile", content)
            self.assertIn("## Sentence Structure Preferences", content)
            self.assertIn("## Manual Refinements (user-edited)", content)
            self.assertIn("## Tone Switching Patterns", content)
            self.assertIn("## Comment Reply Tone Characteristics", content)
            self.assertIn("## Quick Reference Summary for /draft", content)
        finally:
            if output_path.exists():
                output_path.unlink()

    def test_preserves_existing_manual_refinements_on_rerun(self) -> None:
        TMP_DIR.mkdir(exist_ok=True)
        output_path = TMP_DIR / f"brand-voice-{uuid.uuid4().hex}.md"
        manual_content = "\n".join(
            [
                "# Brand Voice Profile",
                "",
                "## Manual Refinements (user-edited)",
                "",
                "- Always keep my openings blunt.",
                "- Never use fake founder-story language.",
                "",
                "## Old Generated Section",
                "",
                "This should be replaced.",
                "",
            ]
        )
        output_path.write_text(manual_content, encoding="utf-8")
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
            content = output_path.read_text(encoding="utf-8")
            self.assertEqual(content.count("## Manual Refinements (user-edited)"), 1)
            self.assertIn("- Always keep my openings blunt.", content)
            self.assertIn("- Never use fake founder-story language.", content)
            self.assertNotIn("This should be replaced.", content)
        finally:
            if output_path.exists():
                output_path.unlink()


if __name__ == "__main__":
    unittest.main()
