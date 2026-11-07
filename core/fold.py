"""Rebuild learning state from an append-only event log. Port of JpFold.cs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from .graduation import apply_correct_test_event, apply_finalize_enroll
from .srs import apply as srs_apply
from .state import LearningState


@dataclass(frozen=True)
class EventRecord:
    event_id: str
    kind: str  # seed|review|test|finalize
    payload_json: str
    occurred_at: datetime


def replay(events: Iterable[EventRecord]) -> LearningState:
    """Fold events (any order) into LearningState. Sorts by occurred_at, then event_id."""
    ordered = sorted(events, key=lambda e: (_as_aware(e.occurred_at), e.event_id))

    state = LearningState.new()
    base_occurred_at = datetime.min.replace(tzinfo=timezone.utc)

    latest_seed: Optional[EventRecord] = None
    for e in ordered:
        if e.kind == "seed" and (
            latest_seed is None or _as_aware(e.occurred_at) >= _as_aware(latest_seed.occurred_at)
        ):
            latest_seed = e

    if latest_seed is not None:
        payload = _deserialize(latest_seed.payload_json)
        if payload is not None:
            state = LearningState(
                mastery=payload.get("mastery") or payload.get("Mastery") or "new",
                srs_interval_days=float(
                    payload.get("srs_interval_days", payload.get("srsIntervalDays", 0)) or 0
                ),
                srs_ease=float(payload.get("srs_ease", payload.get("srsEase", 2.5)) or 2.5),
                srs_due_at=_parse_dt(payload.get("srs_due_at") or payload.get("srsDueAt")),
                srs_reps=int(payload.get("srs_reps", payload.get("srsReps", 0)) or 0),
                srs_lapses=int(payload.get("srs_lapses", payload.get("srsLapses", 0)) or 0),
                graduation_state=payload.get("graduation_state")
                or payload.get("graduationState")
                or "none",
                graduation_stage1_at=_parse_dt(
                    payload.get("graduation_stage1_at") or payload.get("graduationStage1At")
                ),
                graduation_stage2_at=_parse_dt(
                    payload.get("graduation_stage2_at") or payload.get("graduationStage2At")
                ),
            )
            base_occurred_at = _as_aware(latest_seed.occurred_at)

    for e in ordered:
        if e.kind == "seed" or _as_aware(e.occurred_at) < base_occurred_at:
            continue

        if e.kind == "review":
            payload = _deserialize(e.payload_json)
            if payload is None:
                continue
            rating = int(payload.get("rating", payload.get("Rating", 0)) or 0)
            reaction_ms = int(payload.get("reaction_ms", payload.get("reactionMs", 0)) or 0)
            state = srs_apply(state, rating, reaction_ms, _to_naive(e.occurred_at))

        elif e.kind == "finalize":
            payload = _deserialize(e.payload_json) or {}
            ok = payload.get("ok", payload.get("Ok", False))
            if ok:
                state = state.with_updates(
                    graduation_state=apply_finalize_enroll(state.graduation_state)
                )

        elif e.kind == "test":
            payload = _deserialize(e.payload_json)
            if payload is None:
                continue
            is_correct = payload.get("is_correct", payload.get("IsCorrect", False))
            if not is_correct:
                continue
            test_type = payload.get("test_type") or payload.get("TestType") or ""
            new_state, stage1_at, stage2_at = apply_correct_test_event(
                state.graduation_stage1_at,
                state.graduation_stage2_at,
                test_type,
                _to_naive(e.occurred_at),
                state.graduation_state,
            )
            state = state.with_updates(
                graduation_state=new_state,
                graduation_stage1_at=stage1_at,
                graduation_stage2_at=stage2_at,
                mastery="mastered" if new_state == "learned" else state.mastery,
                srs_due_at=None if new_state == "learned" else state.srs_due_at,
            )

    return state


def _deserialize(raw: str) -> Optional[dict[str, Any]]:
    if not raw or not str(raw).strip():
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return _to_naive(value)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    text = str(value).replace("Z", "+00:00")
    try:
        return _to_naive(datetime.fromisoformat(text))
    except ValueError:
        return None


def _as_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _to_naive(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)
