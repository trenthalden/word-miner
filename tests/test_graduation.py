"""Two-stage graduation flow."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from tests._path import ROOT  # noqa: F401
from core.graduation import (
    apply_correct_test_event,
    apply_finalize_enroll,
    needs_gate,
)


class TestGraduation(unittest.TestCase):
    def test_both_stages_correct_is_learned(self):
        now = datetime(2026, 1, 1)
        after1, stage1, _ = apply_correct_test_event(None, None, "write_kanji", now)
        self.assertEqual(after1, "stage1_passed")
        self.assertIsNotNone(stage1)
        after2, _, stage2 = apply_correct_test_event(stage1, None, "recognition", now + timedelta(minutes=1))
        self.assertEqual(after2, "learned")
        self.assertIsNotNone(stage2)

    def test_write_lemma_then_recognition(self):
        now = datetime(2026, 1, 1)
        state, stage1, _ = apply_correct_test_event(None, None, "write_lemma", now)
        self.assertEqual(state, "stage1_passed")
        learned, _, _ = apply_correct_test_event(stage1, None, "recognition", now + timedelta(minutes=1))
        self.assertEqual(learned, "learned")

    def test_only_stage1(self):
        state, stage1, stage2 = apply_correct_test_event(None, None, "write_kanji", datetime.now())
        self.assertEqual(state, "stage1_passed")
        self.assertIsNotNone(stage1)
        self.assertIsNone(stage2)

    def test_finalize_enroll(self):
        self.assertEqual(apply_finalize_enroll("none"), "test_ready")
        self.assertEqual(apply_finalize_enroll("test_ready"), "test_ready")
        self.assertEqual(apply_finalize_enroll("learned"), "learned")

    def test_needs_gate_three_easy(self):
        self.assertTrue(needs_gate([4, 4, 4], "none"))
        self.assertFalse(needs_gate([4, 4, 3], "none"))
        self.assertFalse(needs_gate([4, 4, 4], "test_ready"))


if __name__ == "__main__":
    unittest.main()
