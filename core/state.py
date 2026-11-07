"""Pure learning state for one card."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True)
class ReviewOutcome:
    was_correct: bool
    reaction_ms: int


@dataclass(frozen=True)
class LearningState:
    mastery: str = "new"  # new|weak|medium|good|mastered
    srs_interval_days: float = 0.0
    srs_ease: float = 2.5
    srs_due_at: Optional[datetime] = None
    srs_reps: int = 0
    srs_lapses: int = 0
    graduation_state: str = "none"  # none|test_ready|stage1_passed|learned
    graduation_stage1_at: Optional[datetime] = None
    graduation_stage2_at: Optional[datetime] = None
    # Most-recent-first, capped at mastery window size.
    recent_outcomes: tuple = field(default_factory=tuple)

    @staticmethod
    def new() -> "LearningState":
        return LearningState()

    def with_updates(self, **kwargs) -> "LearningState":
        return replace(self, **kwargs)
