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
            self.assertIn("## Recurring Signature Words and Phrases", content)
            self.assertIn("## Opener and Closer Patterns", content)
            self.assertIn("## Punctuation and Rhythm Tics", content)
            self.assertIn("## Language Register Markers", content)
            self.assertIn("## Argumentation Style Inventory", content)
            self.assertIn("## Tone Switching Patterns", content)
            self.assertIn("## Comment Reply Tone Characteristics", content)
            self.assertIn("## Quick Reference Summary for /draft", content)
        finally:
            if output_path.exists():
                output_path.unlink()

    def test_inventory_counts_repeated_multilingual_phrases(self) -> None:
        TMP_DIR.mkdir(exist_ok=True)
        tracker_path = TMP_DIR / f"tracker-{uuid.uuid4().hex}.json"
        output_path = TMP_DIR / f"brand-voice-{uuid.uuid4().hex}.md"
        tracker_path.write_text(
            """{
              "posts": [
                {"text": "其實 SEO 不難。其實問題是方向。Here is the thing: test data wins."},
                {"text": "其實內容不是越長越好。Here is the thing: examples matter."},
                {"text": "問題是很多人只看工具。其實 Search Console 已經夠用。"},
                {"text": "如果你只看排名，你會誤判。結果就是改錯地方。"}
              ]
            }""",
            encoding="utf-8",
        )
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--tracker",
                    str(tracker_path),
                    "--output",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("其實 (4)", content)
            self.assertIn("Here is the thing (2)", content)
            self.assertIn("Evidence count:", content)
        finally:
            if tracker_path.exists():
                tracker_path.unlink()
            if output_path.exists():
                output_path.unlink()

    def test_sparse_tracker_inventory_uses_low_confidence(self) -> None:
        TMP_DIR.mkdir(exist_ok=True)
        tracker_path = TMP_DIR / f"tracker-{uuid.uuid4().hex}.json"
        output_path = TMP_DIR / f"brand-voice-{uuid.uuid4().hex}.md"
        tracker_path.write_text(
            """{"posts": [{"text": "One short post."}]}""",
            encoding="utf-8",
        )
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--tracker",
                    str(tracker_path),
                    "--output",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("Confidence: Low", content)
            self.assertIn("Do not treat this section as a strong style rule yet.", content)
        finally:
            if tracker_path.exists():
                tracker_path.unlink()
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
