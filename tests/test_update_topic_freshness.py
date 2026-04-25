import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "update_topic_freshness.py"


def load_module():
    spec = importlib.util.spec_from_file_location("update_topic_freshness", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load update_topic_freshness module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_post(post_id, text, created_at, topics, content_type="data-insight"):
    return {
        "id": post_id,
        "text": text,
        "created_at": created_at,
        "topics": topics,
        "content_type": content_type,
        "algorithm_signals": {"topic_freshness": {}},
    }


class UpdateTopicFreshnessTests(unittest.TestCase):
    def test_mixed_language_topic_terms_cluster_without_online_services(self) -> None:
        freshness = load_module()
        posts = [
            build_post(
                "post-ai-zh",
                "這篇在講 AI 生成文章要加入真實案例和第一手經驗，才有可信度。",
                "2026-04-01T09:00:00+08:00",
                ["AI內容", "E-E-A-T"],
            ),
            build_post(
                "post-ai-en",
                "ChatGPT drafts need firsthand proof, screenshots, and editorial judgment before publishing.",
                "2026-04-04T09:00:00+08:00",
                ["AI content", "EEAT"],
            ),
            build_post(
                "post-link",
                "Backlink outreach should stop once a new site has enough external trust signals.",
                "2026-04-05T09:00:00+08:00",
                ["backlinks", "link building"],
                content_type="opinion",
            ),
        ]

        features = [freshness.build_semantic_features(post) for post in posts]
        clusters, _ = freshness.build_clusters(posts, features, threshold=0.24)
        cluster_for_post = {
            post_idx: cluster_id
            for cluster_id, members in clusters.items()
            for post_idx in members
        }

        self.assertEqual(cluster_for_post[0], cluster_for_post[1])
        self.assertNotEqual(cluster_for_post[0], cluster_for_post[2])

    def test_cluster_label_prefers_normalized_topic_terms(self) -> None:
        freshness = load_module()
        posts = [
            build_post(
                "post-ai-zh",
                "AI 文章需要真實案例。",
                "2026-04-01T09:00:00+08:00",
                ["AI內容", "E-E-A-T"],
            ),
            build_post(
                "post-ai-en",
                "AI content needs firsthand evidence.",
                "2026-04-04T09:00:00+08:00",
                ["AI content", "EEAT"],
            ),
        ]
        features = [freshness.build_semantic_features(post) for post in posts]

        label = freshness.best_cluster_label(posts, features, cluster_id=0)

        self.assertIn("eeat", label)
        self.assertNotIn("e-e-a-t", label)

    def test_freshness_counts_prior_mixed_language_similar_post(self) -> None:
        freshness = load_module()
        posts = [
            build_post(
                "post-ai-zh",
                "這篇在講 AI 生成文章要加入真實案例和第一手經驗，才有可信度。",
                "2026-04-01T09:00:00+08:00",
                ["AI內容", "E-E-A-T"],
            ),
            build_post(
                "post-ai-en",
                "ChatGPT drafts need firsthand proof, screenshots, and editorial judgment before publishing.",
                "2026-04-05T09:00:00+08:00",
                ["AI content", "EEAT"],
            ),
        ]
        features = [freshness.build_semantic_features(post) for post in posts]
        clusters, _ = freshness.build_clusters(posts, features, threshold=0.24)
        cluster_labels = {
            cluster_id: freshness.best_cluster_label(
                [posts[idx] for idx in members],
                [features[idx] for idx in members],
                cluster_id,
            )
            for cluster_id, members in clusters.items()
        }

        freshness.annotate_topic_freshness(
            posts=posts,
            clusters=clusters,
            cluster_labels=cluster_labels,
            recent_post_window=10,
            recent_day_window=30,
        )

        second_freshness = posts[1]["algorithm_signals"]["topic_freshness"]
        self.assertEqual(second_freshness["similar_recent_posts"], 1)
        self.assertEqual(second_freshness["recent_cluster_frequency"], 1)
        self.assertEqual(second_freshness["days_since_last_similar_post"], 4.0)
        self.assertLess(second_freshness["freshness_score"], 100)


if __name__ == "__main__":
    unittest.main()
