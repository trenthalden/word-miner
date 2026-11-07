"""Golden SRS behaviour cases."""

from __future__ import annotations

import unittest
from datetime import datetime

from tests._path import ROOT  # noqa: F401 — path side effect
from core.srs import (
    SLOW_THRESHOLD_MS,
    TYPED_RECALL_REACTION_MS,
    apply,
)
from core.state import LearningState


class TestSrs(unittest.TestCase):
    def test_three_consecutive_fast_correct_is_mastered(self):
        state = LearningState.new()
        now = datetime(2026, 1, 1, 12, 0, 0)
        for _ in range(3):
            state = apply(state, rating=4, reaction_ms=100, reviewed_at=now)
        self.assertEqual(state.mastery, "mastered")
        # reps==3 Easy sets 10d, mastered ladder rounds up to 14.
        self.assertEqual(state.srs_interval_days, 14)

    def test_single_good_fast_review_is_good(self):
        state = apply(LearningState.new(), rating=3, reaction_ms=200, reviewed_at=datetime.now())
        self.assertEqual(state.mastery, "good")

    def test_typed_recall_reaction_is_medium_not_weak(self):
        typed = apply(
            LearningState.new(), rating=4, reaction_ms=TYPED_RECALL_REACTION_MS, reviewed_at=datetime.now()
        )
        self.assertEqual(typed.mastery, "medium")
        slow = apply(
            LearningState.new(),
            rating=4,
            reaction_ms=SLOW_THRESHOLD_MS + 1,
            reviewed_at=datetime.now(),
        )
        self.assertEqual(slow.mastery, "weak")

    def test_incorrect_resets_reps_and_penalizes(self):
        state = LearningState.new().with_updates(srs_reps=5, srs_lapses=0)
        state = apply(state, rating=1, reaction_ms=3000, reviewed_at=datetime.now())
        self.assertEqual(state.srs_reps, 0)
        self.assertEqual(state.srs_lapses, 1)
        self.assertAlmostEqual(state.srs_interval_days, 10.0 / (24 * 60), places=6)

    def test_learned_graduation_clamps_mastery(self):
        state = LearningState.new().with_updates(graduation_state="learned", mastery="mastered")
        state = apply(state, rating=1, reaction_ms=5000, reviewed_at=datetime.now())
        self.assertEqual(state.mastery, "mastered")

    def test_mastered_interval_ladder(self):
        state = LearningState.new()
        now = datetime(2026, 2, 1)
        # Three fast Easy → mastered; pre-mastery Easy@reps3 is 10d → ladder rounds to 14.
        for _ in range(3):
            state = apply(state, 4, 100, now)
        self.assertEqual(state.mastery, "mastered")
        self.assertEqual(state.srs_interval_days, 14)
        # Next SM-2 step multiplies by ease (~2.7) → ~38d, ladder snaps to 90.
        state = apply(state, 4, 100, now)
        self.assertEqual(state.mastery, "mastered")
        self.assertIn(state.srs_interval_days, (30, 90))
        state = apply(state, 4, 100, now)
        self.assertEqual(state.srs_interval_days, 90)

    def test_fast_reaction_boosts_ease(self):
        slow = apply(LearningState.new(), 3, 1500, datetime.now())
        fast = apply(LearningState.new(), 3, 200, datetime.now())
        self.assertGreater(fast.srs_ease, slow.srs_ease)


if __name__ == "__main__":
    unittest.main()
