"""Two-stage graduation test. Port of JpGraduation.cs + JpFinalize NeedsGate."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence, Tuple


def is_write_stage(test_type: str | None) -> bool:
    return test_type in ("write_kanji", "write_lemma")


def apply_finalize_enroll(current_state: str | None) -> str:
    if current_state in (None, "", "none"):
        return "test_ready"
    return current_state


def apply_correct_test_event(
    stage1_at: Optional[datetime],
    stage2_at: Optional[datetime],
    test_type: str,
    answered_at: datetime,
    current_state: str | None = None,
) -> Tuple[str, Optional[datetime], Optional[datetime]]:
    """Apply one correct test answer. Incorrect answers do not call this."""
    if is_write_stage(test_type) and stage1_at is None:
        stage1_at = answered_at
    if test_type == "recognition" and stage2_at is None:
        stage2_at = answered_at

    if stage1_at is not None and stage2_at is not None:
        state = "learned"
    elif stage1_at is not None:
        state = "stage1_passed"
    elif current_state == "test_ready":
        state = "test_ready"
    else:
        state = "none"

    return state, stage1_at, stage2_at


def needs_gate(last_review_ratings: Sequence[int], graduation_state: str | None = None) -> bool:
    """Three consecutive Easy reviews open the graduation enroll gate."""
    if graduation_state in ("test_ready", "stage1_passed", "learned"):
        return False
    if len(last_review_ratings) < 3:
        return False
    return all(r == 4 for r in last_review_ratings[-3:])
