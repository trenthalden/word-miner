"""Fold rebuild equals incremental state; order-independent."""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from tests._path import ROOT  # noqa: F401
from core.fold import EventRecord, replay
from core.srs import apply
from core.state import LearningState


def _review(eid: str, rating: int, reaction_ms: int, occurred_at: datetime) -> EventRecord:
    return EventRecord(
        eid,
        "review",
        json.dumps({"rating": rating, "reaction_ms": reaction_ms}),
        occurred_at.replace(tzinfo=timezone.utc) if occurred_at.tzinfo is None else occurred_at,
    )


class TestFold(unittest.TestCase):
    def test_replay_matches_direct_apply(self):
        t0 = datetime(2026, 1, 1, 10, 0, 0)
        direct = apply(LearningState.new(), 3, 200, t0)
        direct = apply(direct, 4, 150, t0.replace(day=2))

        replayed = replay(
            [
                _review("e1", 3, 200, t0),
                _review("e2", 4, 150, t0.replace(day=2)),
            ]
        )
        self.assertEqual(replayed.mastery, direct.mastery)
        self.assertEqual(replayed.srs_reps, direct.srs_reps)
        self.assertAlmostEqual(replayed.srs_interval_days, direct.srs_interval_days, places=4)

    def test_ignores_arrival_order(self):
        t0 = datetime(2026, 1, 1, 10, 0, 0)
        forward = replay([_review("e1", 3, 200, t0), _review("e2", 4, 150, t0.replace(day=2))])
        reversed_ = replay([_review("e2", 4, 150, t0.replace(day=2)), _review("e1", 3, 200, t0)])
        self.assertEqual(forward.mastery, reversed_.mastery)
        self.assertEqual(forward.srs_reps, reversed_.srs_reps)

    def test_finalize_then_write(self):
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        folded = replay(
            [
                EventRecord("f1", "finalize", json.dumps({"ok": True}), t0),
                EventRecord(
                    "t1",
                    "test",
                    json.dumps({"test_type": "write_kanji", "is_correct": True, "reaction_ms": 500}),
                    t0.replace(minute=1),
                ),
            ]
        )
        self.assertEqual(folded.graduation_state, "stage1_passed")


if __name__ == "__main__":
    unittest.main()
