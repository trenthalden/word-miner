"""End-to-end through the real registered tool handlers (not only pure functions)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests._path import load_plugin_package


class TestE2ETools(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        pkg = load_plugin_package()
        self.tools = __import__(f"{pkg.__name__}.tools", fromlist=["*"])
        self.tools.configure(data_dir=Path(self.tmp.name), daily_new_cap=20)

    def tearDown(self):
        self.tools.configure(data_dir=None)  # release store handle
        self.tmp.cleanup()

    def test_add_session_grade_stats(self):
        items = [
            {
                "lemma": f"word{i}",
                "meaning": f"sense{i}",
                "reading": f"r{i}" if i % 2 == 0 else "",
                "pos": "noun",
                "example": f"example line {i}",
                "source": "fixture-verse",
            }
            for i in range(12)
        ]
        added = json.loads(
            self.tools.deck_add_words(deck="ja-en", items=items, source_lang="ja", target_lang="en")
        )
        self.assertTrue(added["ok"], added)
        self.assertEqual(added["added"], 12)
        self.assertEqual(added["merged"], 0)
        self.assertEqual(added["skipped"], 0)

        # Dedupe path through the handler.
        again = json.loads(
            self.tools.deck_add_words(
                deck="ja-en", items=[{"lemma": "word0", "meaning": "updated"}]
            )
        )
        self.assertEqual(again["merged"], 1)

        session = json.loads(self.tools.deck_session(deck="ja-en"))
        self.assertTrue(session["ok"], session)
        self.assertEqual(session["count"], 10)  # STUDY_SESSION_SIZE
        self.assertEqual(len(session["cards"]), 10)
        card = session["cards"][0]
        self.assertIn("card_id", card)
        self.assertIn("prompt", card)
        self.assertIn("hint", card)

        grade = json.loads(
            self.tools.deck_grade(
                card_id=card["card_id"],
                answer=card["expected"],
                response_ms=350,
            )
        )
        self.assertTrue(grade["ok"], grade)
        self.assertTrue(grade["correct"])
        self.assertIn(grade["mastery"], ("weak", "medium", "good", "mastered"))

        # Self-grade path.
        card2 = session["cards"][1]
        g2 = json.loads(
            self.tools.deck_grade(card_id=card2["card_id"], rating=3, response_ms=800)
        )
        self.assertTrue(g2["ok"], g2)

        stats = json.loads(self.tools.deck_stats(deck="ja-en"))
        self.assertTrue(stats["ok"], stats)
        self.assertEqual(stats["total"], 12)
        self.assertGreaterEqual(stats["streak_days"], 1)
        self.assertEqual(stats["levels"]["new"] + stats["levels"].get("good", 0)
                         + stats["levels"].get("medium", 0)
                         + stats["levels"].get("weak", 0)
                         + stats["levels"].get("mastered", 0), 12)

    def test_handler_validation_errors(self):
        bad = json.loads(self.tools.deck_add_words(deck="", items=[]))
        self.assertFalse(bad["ok"])
        bad2 = json.loads(self.tools.deck_grade(card_id="missing"))
        self.assertFalse(bad2["ok"])


if __name__ == "__main__":
    unittest.main()
