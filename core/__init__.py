"""Language-agnostic spaced-repetition core (SM-2-like, response-time aware)."""

from .answer import matches, normalize, prompt_gloss, type_recall_required
from .deck import (
    ACTIVE_POOL_LIMIT,
    STUDY_SESSION_SIZE,
    DeckCandidate,
    build_study_session,
    count_active_rotation,
    count_review_due,
    is_review_due,
    new_budget,
    select_due_review,
    select_test_candidates,
)
from .fold import EventRecord, replay
from .graduation import apply_correct_test_event, apply_finalize_enroll, is_write_stage
from .import_words import ImportRow, parse_import
from .lemma import canonical as canonical_lemma
from .srs import (
    DEFAULT_EASE,
    FAST_THRESHOLD_MS,
    SLOW_THRESHOLD_MS,
    TYPED_RECALL_REACTION_MS,
    apply as srs_apply,
    compute_mastery,
)
from .state import LearningState, ReviewOutcome

__all__ = [
    "ACTIVE_POOL_LIMIT",
    "DEFAULT_EASE",
    "FAST_THRESHOLD_MS",
    "SLOW_THRESHOLD_MS",
    "STUDY_SESSION_SIZE",
    "TYPED_RECALL_REACTION_MS",
    "DeckCandidate",
    "EventRecord",
    "ImportRow",
    "LearningState",
    "ReviewOutcome",
    "apply_correct_test_event",
    "apply_finalize_enroll",
    "build_study_session",
    "canonical_lemma",
    "compute_mastery",
    "count_active_rotation",
    "count_review_due",
    "is_review_due",
    "is_write_stage",
    "matches",
    "new_budget",
    "normalize",
    "parse_import",
    "prompt_gloss",
    "replay",
    "select_due_review",
    "select_test_candidates",
    "srs_apply",
    "type_recall_required",
]
