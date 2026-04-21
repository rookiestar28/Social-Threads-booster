import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "parse_export.py"
TMP_DIR = REPO_ROOT / ".tmp"


class ParseExportCliTests(unittest.TestCase):
    def test_parses_minimal_json_export_into_tracker(self) -> None:
        case_dir = TMP_DIR / f"parse-export-{uuid.uuid4().hex}"
        input_path = case_dir / "threads-export.json"
        output_path = case_dir / "tracker.json"

        try:
            case_dir.mkdir(parents=True, exist_ok=True)
            input_path.write_text(
                json.dumps(
                    {
                        "threads": [
                            {
                                "id": "export-post-1",
                                "text": "這是一篇測試 Threads 貼文",
                                "timestamp": "2026-04-20T10:00:00+00:00",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8-sig",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            tracker = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(len(tracker["posts"]), 1)
            self.assertEqual(tracker["posts"][0]["id"], "export-post-1")
            self.assertEqual(tracker["posts"][0]["source"]["import_path"], "export")
            self.assertEqual(tracker["posts"][0]["metrics"]["views"], 0)
        finally:
            if case_dir.exists():
                shutil.rmtree(case_dir)


if __name__ == "__main__":
    unittest.main()
