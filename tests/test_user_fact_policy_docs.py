import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


class UserFactPolicyDocsTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (REPO_ROOT / relative_path).read_text(encoding="utf-8")

    def test_shared_policy_contains_required_guardrails(self) -> None:
        policy = self.read("knowledge/user-fact-source-of-truth.md")
        required = [
            "Preserve chronology",
            "Do not infer biography",
            "Do not let web search override",
            "[confirm with user]",
            "Do not store private personal facts",
        ]
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, policy)

    def test_shared_principles_reference_user_fact_policy(self) -> None:
        principles = self.read("knowledge/_shared/principles.md")
        self.assertIn("knowledge/user-fact-source-of-truth.md", principles)

    def test_draft_analyze_review_reference_user_fact_policy(self) -> None:
        for relative_path in (
            "skills/draft/SKILL.md",
            "skills/analyze/SKILL.md",
            "skills/review/SKILL.md",
        ):
            with self.subTest(path=relative_path):
                content = self.read(relative_path)
                self.assertIn("user-fact-source-of-truth.md", content)

    def test_draft_requires_confirm_with_user_for_unverified_personal_facts(self) -> None:
        draft = self.read("skills/draft/SKILL.md")
        self.assertIn("[confirm with user]", draft)
        self.assertIn("unconfirmed personal facts", draft)


if __name__ == "__main__":
    unittest.main()
