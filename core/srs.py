"""SM-2-like SRS with response-time adjustment. Port of JpSrs.cs."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Sequence

from .state import LearningState, ReviewOutcome

FAST_THRESHOLD_MS = 500
SLOW_THRESHOLD_MS = 2000
# Typed recall cannot beat 500ms; wall-clock typing would always look "slow".
TYPED_RECALL_REACTION_MS = 1000

MASTERY_WINDOW_SIZE = 3

MIN_EASE_FACTOR = 1.3
MAX_EASE_FACTOR = 3.0
DEFAULT_EASE = 2.5


def apply(state: LearningState, rating: int, reaction_ms: int, reviewed_at: datetime) -> LearningState:
    """Apply one review (rating 1-4, reaction time in ms). Pure."""
    was_correct = rating >= 3

    reps = state.srs_reps
    lapses = state.srs_lapses
    interval_days = state.srs_interval_days
    ease = state.srs_ease

    if not was_correct:
        reps = 0
        lapses += 1
        interval_days = 10.0 / (24 * 60)  # 10 minutes
    else:
        reps += 1
        if reps == 1:
            interval_days = 1.0 / 24 if rating == 4 else 1.0 / 144  # Easy=1h, Good=10min
        elif reps == 2:
            interval_days = 3 if rating == 4 else 1  # Easy=3d, Good=1d
        elif reps == 3:
            interval_days = 10 if rating == 4 else 6  # Easy=10d, Good=6d
        else:
            interval_days = min(interval_days * ease, 365)

        ease += 0.1 - (5 - rating) * 0.08

        if reaction_ms < FAST_THRESHOLD_MS:
            ease += 0.05
        elif reaction_ms > SLOW_THRESHOLD_MS:
            ease -= 0.10

        ease = max(MIN_EASE_FACTOR, min(MAX_EASE_FACTOR, ease))

    recent_outcomes = _push_outcome(state.recent_outcomes, ReviewOutcome(was_correct, reaction_ms))
    mastery = compute_mastery(recent_outcomes)

    # Never downgrade a graduated word.
    if state.graduation_state == "learned" and mastery != "mastered":
        mastery = "mastered"

    # Mastered ladder: 7d -> 14d -> 30d -> 90d
    if mastery == "mastered":
        if interval_days < 7:
            interval_days = 7
        elif interval_days < 14:
            interval_days = 14
        elif interval_days < 30:
            interval_days = 30
        else:
            interval_days = 90

    due_at = reviewed_at + timedelta(days=interval_days)

    return state.with_updates(
        mastery=mastery,
        srs_interval_days=interval_days,
        srs_ease=ease,
        srs_due_at=due_at,
        srs_reps=reps,
        srs_lapses=lapses,
        recent_outcomes=recent_outcomes,
    )


def compute_mastery(recent_outcomes_desc: Sequence[ReviewOutcome]) -> str:
    """Mirrors the desktop's 'last N reviews DESC' mastery computation."""
    if not recent_outcomes_desc:
        return "new"

    all_correct = True
    reaction_sum = 0.0
    for outcome in recent_outcomes_desc:
        all_correct = all_correct and outcome.was_correct
        reaction_sum += outcome.reaction_ms
    avg_reaction_ms = reaction_sum / len(recent_outcomes_desc)

    consecutive_fast = 0
    for outcome in recent_outcomes_desc:
        if outcome.was_correct and outcome.reaction_ms < FAST_THRESHOLD_MS:
            consecutive_fast += 1
        else:
            break

    if consecutive_fast >= MASTERY_WINDOW_SIZE:
        return "mastered"
    if all_correct and avg_reaction_ms < FAST_THRESHOLD_MS:
        return "good"
    if all_correct and avg_reaction_ms < SLOW_THRESHOLD_MS:
        return "medium"
    return "weak"


def _push_outcome(current_desc: Sequence[ReviewOutcome], newest: ReviewOutcome) -> tuple:
    nxt: List[ReviewOutcome] = [newest]
    for outcome in current_desc:
        if len(nxt) >= MASTERY_WINDOW_SIZE:
            break
        nxt.append(outcome)
    return tuple(nxt)
