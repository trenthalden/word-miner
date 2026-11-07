"""Deck composition: 3+3+3+1, active pool <20, top-up when nothing due."""

from __future__ import annotations

import random
import unittest
from datetime import datetime, timedelta

from tests._path import ROOT  # noqa: F401
from core.deck import (
    ACTIVE_POOL_LIMIT,
    STUDY_SESSION_SIZE,
    DeckCandidate,
    build_study_session,
    count_active_rotation,
    count_review_due,
    new_budget,
    select_due_review,
)


class TestDeck(unittest.TestCase):
    def test_new_budget_respects_active_pool_limit(self):
        now = datetime(2026, 9, 2)
        words = []
        for i in range(17):
            words.append(
                DeckCandidate(
                    f"pool-{i}", "weak", "none", now + timedelta(days=1), now, srs_reps=3
                )
            )
        for i in range(5):
            words.append(
                DeckCandidate(f"new-{i}", "new", "none", None, now, srs_reps=0, created_at=now)
            )
        self.assertEqual(count_active_rotation(words), 17)
        self.assertEqual(new_budget(words), ACTIVE_POOL_LIMIT - 17)

    def test_full_pool_fills_from_earliest_not_new(self):
        now = datetime(2026, 9, 2)
        words = []
        for i in range(25):
            words.append(
                DeckCandidate(
                    f"pool-{i}",
                    "weak",
                    "none",
                    now + timedelta(days=8 + i),
                    now,
                    srs_reps=3,
                    created_at=now.replace(year=2025),
                )
            )
        for i in range(10):
            words.append(
                DeckCandidate(
                    f"new-{i}", "new", "none", None, now, srs_reps=0, created_at=now - timedelta(days=i)
                )
            )
        session = build_study_session(words, now, rng=random.Random(1))
        self.assertEqual(len(session), STUDY_SESSION_SIZE)
        self.assertEqual(set(session), {f"pool-{i}" for i in range(10)})

    def test_new_cards_enter_oldest_first(self):
        now = datetime(2026, 9, 17)
        words = []
        for i in range(15):
            words.append(
                DeckCandidate(
                    f"new-{i}", "new", "none", None, now, srs_reps=0, created_at=now - timedelta(days=i)
                )
            )
        session = build_study_session(words, now, rng=random.Random(1))
        self.assertEqual(len(session), STUDY_SESSION_SIZE)
        for i in range(5, 15):
            self.assertIn(f"new-{i}", session)
        self.assertNotIn("new-0", session)
        self.assertNotIn("new-4", session)

    def test_excludes_future_due_words(self):
        now = datetime(2026, 1, 10)
        candidates = [
            DeckCandidate("due-today", "good", "none", now - timedelta(hours=1), now, srs_reps=2),
            DeckCandidate("due-in-30-days", "mastered", "none", now + timedelta(days=30), now, srs_reps=5),
            DeckCandidate("no-due-date-yet", "weak", "none", None, now, srs_reps=2),
        ]
        due = select_due_review(candidates, now, take=20)
        self.assertIn("due-today", due)
        self.assertIn("no-due-date-yet", due)
        self.assertNotIn("due-in-30-days", due)

    def test_review_due_ignores_unseen_catalog(self):
        now = datetime(2026, 9, 17)
        words = [DeckCandidate("due-weak", "weak", "none", now - timedelta(hours=1), now, srs_reps=2)]
        for i in range(50):
            words.append(
                DeckCandidate(f"new-{i}", "new", "none", None, now, srs_reps=0, created_at=now)
            )
        self.assertEqual(count_review_due(words, now), 1)

    def test_composition_slots_when_mixed_due(self):
        now = datetime(2026, 3, 1)
        words = []
        for i in range(3):
            words.append(DeckCandidate(f"n{i}", "new", "none", None, now, srs_reps=0, created_at=now - timedelta(days=i)))
        for i in range(3):
            words.append(DeckCandidate(f"w{i}", "weak", "none", now - timedelta(hours=1), now, srs_reps=2))
        for i in range(3):
            words.append(DeckCandidate(f"m{i}", "medium", "none", now - timedelta(hours=1), now, srs_reps=3))
        words.append(DeckCandidate("g0", "good", "none", now - timedelta(hours=1), now, srs_reps=4))
        words.append(DeckCandidate("x0", "mastered", "none", now - timedelta(hours=1), now, srs_reps=8))
        session = build_study_session(words, now, rng=random.Random(0))
        self.assertEqual(len(session), 10)
        # 3 new + 3 weak + 3 medium + 1 good (mastered slot starved by remaining=0)
        self.assertEqual(sum(1 for s in session if s.startswith("n")), 3)
        self.assertEqual(sum(1 for s in session if s.startswith("w")), 3)
        self.assertEqual(sum(1 for s in session if s.startswith("m")), 3)
        self.assertIn("g0", session)


if __name__ == "__main__":
    unittest.main()
