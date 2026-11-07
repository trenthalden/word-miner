"""Store: dedupe, daily cap, fold rebuild vs derived state."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from tests._path import ROOT  # noqa: F401
from core.store import WordMinerStore


class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = WordMinerStore(Path(self.tmp.name) / "data.db", daily_new_cap=5)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_dedupe_by_deck_lemma(self):
        r1 = self.store.add_words(
            "ja-en",
            [{"lemma": "雨", "meaning": "rain", "reading": "あめ"}],
        )
        self.assertEqual(r1["added"], 1)
        r2 = self.store.add_words(
            "ja-en",
            [{"lemma": "雨", "meaning": "rainfall", "reading": "あめ"}],
        )
        self.assertEqual(r2["merged"], 1)
        self.assertEqual(r2["added"], 0)
        stats = self.store.stats("ja-en")
        self.assertEqual(stats["total"], 1)
        card = self.store._load_cards("ja-en")[0]
        self.assertEqual(card.meaning, "rainfall")

    def test_daily_cap(self):
        items = [{"lemma": f"w{i}", "meaning": f"m{i}"} for i in range(8)]
        result = self.store.add_words("es-ru", items)
        self.assertEqual(result["added"], 5)
        self.assertEqual(result["skipped"], 3)
        self.assertEqual(result["daily_new_cap"], 5)

    def test_fold_rebuild_equals_incremental(self):
        self.store.add_words("ja-en", [{"lemma": "水", "meaning": "water", "reading": "みず"}])
        card = self.store._load_cards("ja-en")[0]
        # Reviews must be after the seed timestamp (seed uses wall clock on insert).
        t0 = card.created_at
        from datetime import timedelta

        g1 = self.store.grade(card.id, rating=3, response_ms=200, now=t0 + timedelta(hours=1))
        self.assertTrue(g1["ok"])
        g2 = self.store.grade(card.id, rating=4, response_ms=150, now=t0 + timedelta(days=1))
        self.assertTrue(g2["ok"])
        derived = self.store.get_card(card.id).state
        folded = self.store.rebuild_card_from_events(card.id)
        self.assertEqual(folded.mastery, derived.mastery)
        self.assertEqual(folded.srs_reps, derived.srs_reps)
        self.assertAlmostEqual(folded.srs_interval_days, derived.srs_interval_days, places=4)

    def test_session_and_grade_answer(self):
        words = [{"lemma": f"l{i}", "meaning": f"m{i}"} for i in range(12)]
        self.store.add_words("fr-en", words)
        session = self.store.build_session("fr-en", seed=42)
        self.assertGreaterEqual(session["count"], 1)
        self.assertLessEqual(session["count"], 10)
        card = session["cards"][0]
        # Wrong typed answer on produce path after we force recognition (default).
        result = self.store.grade(card["card_id"], answer=card["expected"], response_ms=400)
        self.assertTrue(result["ok"])
        self.assertTrue(result["correct"])


if __name__ == "__main__":
    unittest.main()
