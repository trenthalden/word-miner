"""Study-session composition: 3+3+3+1, active-pool cap 20, nearest-due top-up. Port of JpDeck.cs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional, Sequence
import random


ACTIVE_POOL_LIMIT = 20
STUDY_SESSION_SIZE = 10


@dataclass(frozen=True)
class DeckCandidate:
    sync_id: str
    mastery: str
    graduation_state: str
    srs_due_at: Optional[datetime]
    updated_at: datetime
    srs_reps: int = 0
    created_at: datetime = datetime.min
    has_image: bool = True


def in_active_pool(w: DeckCandidate) -> bool:
    return w.srs_reps > 0 and w.mastery != "mastered"


def count_active_rotation(words: Iterable[DeckCandidate]) -> int:
    return sum(1 for w in words if in_active_pool(w))


def new_budget(words: Iterable[DeckCandidate]) -> int:
    all_words = list(words)
    return max(0, ACTIVE_POOL_LIMIT - count_active_rotation(all_words))


def is_review_due(w: DeckCandidate, now: datetime) -> bool:
    if w.graduation_state == "learned":
        return False
    if w.mastery == "new" and w.srs_reps == 0:
        return False
    if w.mastery == "mastered":
        return w.srs_due_at is not None and w.srs_due_at <= now
    return w.srs_due_at is None or w.srs_due_at <= now


def count_review_due(words: Iterable[DeckCandidate], now: datetime) -> int:
    return sum(1 for w in words if is_review_due(w, now))


def is_due(w: DeckCandidate, now: datetime) -> bool:
    return w.graduation_state != "learned" and (w.srs_due_at is None or w.srs_due_at <= now)


def select_due_review(words: Iterable[DeckCandidate], now: datetime, take: int) -> List[str]:
    due = [w for w in words if is_review_due(w, now)]
    due.sort(key=lambda w: w.srs_due_at or datetime.min)
    return [w.sync_id for w in due[:take]]


def select_test_candidates(words: Iterable[DeckCandidate], take: int) -> List[str]:
    ready = [w for w in words if w.graduation_state in ("test_ready", "stage1_passed")]
    ready.sort(
        key=lambda w: (
            0 if w.graduation_state == "stage1_passed" else 1,
            w.updated_at,
        )
    )
    return [w.sync_id for w in ready[:take]]


def build_study_session(
    words: Iterable[DeckCandidate],
    now: datetime,
    rng: Optional[random.Random] = None,
) -> List[str]:
    all_words = list(words)
    picked: List[DeckCandidate] = []
    seen: set[str] = set()

    budget = new_budget(all_words)
    pool_full = budget == 0
    remaining = STUDY_SESSION_SIZE

    for mastery, count in (
        ("new", min(3, budget)),
        ("weak", 3),
        ("medium", 3),
        ("good", 1),
        ("mastered", 1),
    ):
        if remaining <= 0:
            break
        take = min(count, remaining)
        if take <= 0:
            continue
        remaining -= _add_range(picked, seen, _take_due(all_words, seen, mastery, now, take))

    if pool_full and not picked:
        remaining = STUDY_SESSION_SIZE - _add_range(
            picked, seen, _take_earliest_pool(all_words, seen, STUDY_SESSION_SIZE)
        )

    if remaining > 0:
        fallback = ("weak", "medium", "good") if pool_full else ("weak", "medium", "new", "good")
        for mastery in fallback:
            if remaining <= 0:
                break
            remaining -= _add_range(
                picked, seen, _take_due(all_words, seen, mastery, now, remaining)
            )

    if not picked:
        _add_range(picked, seen, _take_earliest_pool(all_words, seen, STUDY_SESSION_SIZE))

    _shuffle(picked, rng or random.Random())
    return [w.sync_id for w in picked]


def _take_due(
    all_words: Sequence[DeckCandidate],
    seen: set[str],
    mastery: str,
    now: datetime,
    take: int,
) -> List[DeckCandidate]:
    q = [w for w in all_words if w.mastery == mastery and w.sync_id not in seen]
    if mastery == "new":
        q = [w for w in q if w.has_image]
        q.sort(key=lambda w: (w.created_at, w.sync_id))
    else:
        q = [w for w in q if is_due(w, now)]
        q.sort(key=lambda w: w.srs_due_at or datetime.min)
    return q[:take]


def _take_earliest_pool(
    all_words: Sequence[DeckCandidate], seen: set[str], take: int
) -> List[DeckCandidate]:
    q = [w for w in all_words if in_active_pool(w) and w.sync_id not in seen]
    q.sort(key=lambda w: w.srs_due_at or datetime.min)
    return q[:take]


def _add_range(
    picked: List[DeckCandidate], seen: set[str], batch: List[DeckCandidate]
) -> int:
    for w in batch:
        if w.sync_id in seen:
            continue
        seen.add(w.sync_id)
        picked.append(w)
    return len(batch)


def _shuffle(cards: List[DeckCandidate], rng: random.Random) -> None:
    for i in range(len(cards) - 1, 0, -1):
        j = rng.randrange(i + 1)
        cards[i], cards[j] = cards[j], cards[i]
