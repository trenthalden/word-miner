"""SQLite event log + derived card state. Event log is the source of truth."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .answer import matches, prompt_gloss
from .deck import DeckCandidate, build_study_session, count_active_rotation, count_review_due
from .fold import EventRecord, replay
from .graduation import apply_correct_test_event, apply_finalize_enroll, needs_gate
from .lemma import canonical as canonical_lemma
from .srs import TYPED_RECALL_REACTION_MS, apply as srs_apply
from .state import LearningState

DEFAULT_DAILY_NEW_CAP = 20
PLUGIN_NAME = "word-miner"


@dataclass
class CardRecord:
    id: str
    deck: str
    lemma: str
    reading: str
    meaning: str
    pos: str
    example: str
    source: str
    created_at: datetime
    updated_at: datetime
    state: LearningState
    last_rating: Optional[int] = None


class WordMinerStore:
    """Owns the SQLite file under the plugin data directory."""

    def __init__(self, db_path: Path, daily_new_cap: int = DEFAULT_DAILY_NEW_CAP):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.daily_new_cap = daily_new_cap
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS decks (
                name TEXT PRIMARY KEY,
                source_lang TEXT NOT NULL DEFAULT '',
                target_lang TEXT NOT NULL DEFAULT '',
                daily_new_cap INTEGER NOT NULL DEFAULT 20,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cards (
                id TEXT PRIMARY KEY,
                deck TEXT NOT NULL REFERENCES decks(name),
                lemma TEXT NOT NULL,
                lemma_key TEXT NOT NULL,
                reading TEXT NOT NULL DEFAULT '',
                meaning TEXT NOT NULL DEFAULT '',
                pos TEXT NOT NULL DEFAULT '',
                example TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                mastery TEXT NOT NULL DEFAULT 'new',
                srs_interval_days REAL NOT NULL DEFAULT 0,
                srs_ease REAL NOT NULL DEFAULT 2.5,
                srs_due_at TEXT,
                srs_reps INTEGER NOT NULL DEFAULT 0,
                srs_lapses INTEGER NOT NULL DEFAULT 0,
                graduation_state TEXT NOT NULL DEFAULT 'none',
                graduation_stage1_at TEXT,
                graduation_stage2_at TEXT,
                recent_outcomes_json TEXT NOT NULL DEFAULT '[]',
                last_rating INTEGER,
                UNIQUE(deck, lemma_key)
            );
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                card_id TEXT NOT NULL REFERENCES cards(id),
                kind TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                occurred_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS daily_new (
                deck TEXT NOT NULL,
                day TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (deck, day)
            );
            CREATE TABLE IF NOT EXISTS study_days (
                day TEXT PRIMARY KEY
            );
            CREATE INDEX IF NOT EXISTS idx_events_card_time ON events(card_id, occurred_at);
            CREATE INDEX IF NOT EXISTS idx_cards_deck ON cards(deck);
            """
        )
        self._conn.commit()

    # ── decks ──────────────────────────────────────────────────────────

    def ensure_deck(
        self,
        name: str,
        source_lang: str = "",
        target_lang: str = "",
        daily_new_cap: Optional[int] = None,
    ) -> Dict[str, Any]:
        name = (name or "").strip()
        if not name:
            raise ValueError("deck name is required")
        now = _iso(datetime.now(timezone.utc).replace(tzinfo=None))
        cap = daily_new_cap if daily_new_cap is not None else self.daily_new_cap
        row = self._conn.execute("SELECT * FROM decks WHERE name = ?", (name,)).fetchone()
        if row is None:
            # Parse language pair from name like ja-en if not given.
            src, tgt = source_lang, target_lang
            if not src and not tgt and "-" in name:
                parts = name.split("-", 1)
                src, tgt = parts[0], parts[1]
            self._conn.execute(
                "INSERT INTO decks(name, source_lang, target_lang, daily_new_cap, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (name, src or "", tgt or "", cap, now),
            )
            self._conn.commit()
            row = self._conn.execute("SELECT * FROM decks WHERE name = ?", (name,)).fetchone()
        return dict(row)

    def list_decks(self) -> List[Dict[str, Any]]:
        return [dict(r) for r in self._conn.execute("SELECT * FROM decks ORDER BY name")]

    # ── add words ──────────────────────────────────────────────────────

    def add_words(self, deck: str, items: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        deck_info = self.ensure_deck(deck)
        cap = int(deck_info["daily_new_cap"])
        today = date.today().isoformat()
        used = self._daily_new_count(deck, today)

        added = merged = skipped = 0
        details: List[Dict[str, Any]] = []

        for raw in items:
            lemma = (raw.get("lemma") or "").strip()
            meaning = (raw.get("meaning") or "").strip()
            if not lemma or not meaning:
                skipped += 1
                details.append({"lemma": lemma, "status": "skipped", "reason": "missing lemma/meaning"})
                continue

            lemma_key = canonical_lemma(lemma).lower()
            existing = self._conn.execute(
                "SELECT * FROM cards WHERE deck = ? AND lemma_key = ?",
                (deck, lemma_key),
            ).fetchone()

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if existing is not None:
                self._merge_card(existing["id"], raw, now)
                merged += 1
                details.append({"lemma": lemma, "status": "merged", "card_id": existing["id"]})
                continue

            if used >= cap:
                skipped += 1
                details.append({"lemma": lemma, "status": "skipped", "reason": "daily_new_cap"})
                continue

            card_id = str(uuid.uuid4())
            self._insert_card(card_id, deck, lemma, lemma_key, raw, now)
            used += 1
            added += 1
            details.append({"lemma": lemma, "status": "added", "card_id": card_id})

        self._set_daily_new_count(deck, today, used)
        self._conn.commit()
        return {
            "deck": deck,
            "added": added,
            "merged": merged,
            "skipped": skipped,
            "daily_new_used": used,
            "daily_new_cap": cap,
            "details": details,
        }

    def _insert_card(
        self,
        card_id: str,
        deck: str,
        lemma: str,
        lemma_key: str,
        raw: Dict[str, Any],
        now: datetime,
    ) -> None:
        iso = _iso(now)
        self._conn.execute(
            """
            INSERT INTO cards(
                id, deck, lemma, lemma_key, reading, meaning, pos, example, source,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                card_id,
                deck,
                lemma,
                lemma_key,
                (raw.get("reading") or "").strip(),
                (raw.get("meaning") or "").strip(),
                (raw.get("pos") or "").strip(),
                (raw.get("example") or "").strip(),
                (raw.get("source") or "").strip(),
                iso,
                iso,
            ),
        )
        # Seed event captures initial empty learning state.
        seed_payload = {
            "mastery": "new",
            "srs_interval_days": 0,
            "srs_ease": 2.5,
            "srs_due_at": None,
            "srs_reps": 0,
            "srs_lapses": 0,
            "graduation_state": "none",
            "graduation_stage1_at": None,
            "graduation_stage2_at": None,
        }
        self._append_event(card_id, "seed", seed_payload, now)

    def _merge_card(self, card_id: str, raw: Dict[str, Any], now: datetime) -> None:
        row = self._conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        reading = (raw.get("reading") or "").strip() or row["reading"]
        meaning = (raw.get("meaning") or "").strip() or row["meaning"]
        pos = (raw.get("pos") or "").strip() or row["pos"]
        example = (raw.get("example") or "").strip() or row["example"]
        source = (raw.get("source") or "").strip() or row["source"]
        self._conn.execute(
            """
            UPDATE cards SET reading=?, meaning=?, pos=?, example=?, source=?, updated_at=?
            WHERE id=?
            """,
            (reading, meaning, pos, example, source, _iso(now), card_id),
        )

    # ── session ────────────────────────────────────────────────────────

    def build_session(self, deck: str, now: Optional[datetime] = None, seed: Optional[int] = None) -> Dict[str, Any]:
        self.ensure_deck(deck)
        now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        cards = self._load_cards(deck)
        candidates = [self._to_candidate(c) for c in cards]
        import random

        rng = random.Random(seed) if seed is not None else random.Random()
        ids = build_study_session(candidates, now, rng=rng)
        by_id = {c.id: c for c in cards}
        session_cards = []
        for cid in ids:
            c = by_id[cid]
            prompt_side, prompt, hint, expected = self._prompt_for(c)
            session_cards.append(
                {
                    "card_id": c.id,
                    "lemma": c.lemma,
                    "reading": c.reading,
                    "meaning": c.meaning,
                    "pos": c.pos,
                    "example": c.example,
                    "mastery": c.state.mastery,
                    "graduation_state": c.state.graduation_state,
                    "prompt_side": prompt_side,
                    "prompt": prompt,
                    "hint": hint,
                    "expected": expected,
                }
            )
        return {
            "deck": deck,
            "count": len(session_cards),
            "active_rotation": count_active_rotation(candidates),
            "review_due": count_review_due(candidates, now),
            "cards": session_cards,
        }

    def _prompt_for(self, card: CardRecord) -> tuple:
        # After Easy, next card is meaning → type lemma (production).
        if card.last_rating == 4 or card.state.graduation_state == "test_ready":
            gloss = prompt_gloss(card.lemma, card.meaning)
            return (
                "produce",
                gloss,
                card.reading or card.pos or "",
                card.lemma,
            )
        if card.state.graduation_state == "stage1_passed":
            return (
                "recognise",
                card.lemma + (f" ({card.reading})" if card.reading else ""),
                card.example or card.pos or "",
                card.meaning,
            )
        # Default recognition: show lemma, recall meaning.
        return (
            "recognise",
            card.lemma + (f" ({card.reading})" if card.reading else ""),
            card.example or card.pos or "",
            card.meaning,
        )

    # ── grade ──────────────────────────────────────────────────────────

    def grade(
        self,
        card_id: str,
        *,
        answer: Optional[str] = None,
        rating: Optional[int] = None,
        response_ms: Optional[int] = None,
        test_type: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        card = self.get_card(card_id)
        if card is None:
            return {"ok": False, "error": f"unknown card_id: {card_id}"}

        reaction = response_ms if response_ms is not None else TYPED_RECALL_REACTION_MS
        prompt_side, _prompt, _hint, expected = self._prompt_for(card)

        # Graduation test path.
        if card.state.graduation_state in ("test_ready", "stage1_passed") or test_type:
            return self._grade_test(card, answer, expected, reaction, test_type, now)

        correct: Optional[bool] = None
        if answer is not None:
            correct = matches(answer, expected)
            if rating is None:
                rating = 4 if correct else 1
            # Typed recall miss must not emit a review event (mastery unchanged).
            if prompt_side == "produce" and not correct:
                return {
                    "ok": True,
                    "correct": False,
                    "rating": None,
                    "mastery": card.state.mastery,
                    "next_due": _iso(card.state.srs_due_at) if card.state.srs_due_at else None,
                    "graduation_state": card.state.graduation_state,
                    "message": "typed answer incorrect; retry same card (no review logged)",
                }

        if rating is None:
            return {"ok": False, "error": "provide answer or rating (1-4)"}
        rating = int(rating)
        if rating < 1 or rating > 4:
            return {"ok": False, "error": "rating must be 1-4"}

        new_state = srs_apply(card.state, rating, int(reaction), now)
        payload = {"rating": rating, "reaction_ms": int(reaction)}
        self._append_event(card_id, "review", payload, now)
        self._write_derived(card_id, new_state, last_rating=rating, updated_at=now)

        # Auto-enroll for graduation after three Easy ratings.
        ratings = self._last_ratings(card_id, 3)
        if needs_gate(ratings, new_state.graduation_state):
            enrolled = apply_finalize_enroll(new_state.graduation_state)
            self._append_event(card_id, "finalize", {"ok": True}, now)
            new_state = new_state.with_updates(graduation_state=enrolled)
            self._write_derived(card_id, new_state, last_rating=rating, updated_at=now)

        self._mark_study_day(now.date())
        self._conn.commit()

        return {
            "ok": True,
            "correct": correct if correct is not None else rating >= 3,
            "rating": rating,
            "mastery": new_state.mastery,
            "srs_reps": new_state.srs_reps,
            "srs_interval_days": new_state.srs_interval_days,
            "next_due": _iso(new_state.srs_due_at) if new_state.srs_due_at else None,
            "graduation_state": new_state.graduation_state,
            "card_id": card_id,
        }

    def _grade_test(
        self,
        card: CardRecord,
        answer: Optional[str],
        expected: str,
        reaction: int,
        test_type: Optional[str],
        now: datetime,
    ) -> Dict[str, Any]:
        if test_type is None:
            if card.state.graduation_state == "stage1_passed":
                test_type = "recognition"
            else:
                test_type = "write_lemma"

        if answer is not None:
            correct = matches(answer, expected)
        else:
            return {"ok": False, "error": "graduation test requires a typed answer"}

        payload = {
            "test_type": test_type,
            "is_correct": correct,
            "reaction_ms": int(reaction),
        }
        self._append_event(card.id, "test", payload, now)

        state = card.state
        if correct:
            new_grad, stage1, stage2 = apply_correct_test_event(
                state.graduation_stage1_at,
                state.graduation_stage2_at,
                test_type,
                now,
                state.graduation_state,
            )
            state = state.with_updates(
                graduation_state=new_grad,
                graduation_stage1_at=stage1,
                graduation_stage2_at=stage2,
                mastery="mastered" if new_grad == "learned" else state.mastery,
                srs_due_at=None if new_grad == "learned" else state.srs_due_at,
            )

        self._write_derived(card.id, state, updated_at=now)
        self._mark_study_day(now.date())
        self._conn.commit()
        return {
            "ok": True,
            "correct": correct,
            "test_type": test_type,
            "mastery": state.mastery,
            "graduation_state": state.graduation_state,
            "next_due": _iso(state.srs_due_at) if state.srs_due_at else None,
            "card_id": card.id,
        }

    # ── stats ──────────────────────────────────────────────────────────

    def stats(self, deck: Optional[str] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        if deck:
            decks = [deck]
            self.ensure_deck(deck)
        else:
            decks = [d["name"] for d in self.list_decks()]

        levels = {"new": 0, "weak": 0, "medium": 0, "good": 0, "mastered": 0}
        graduation = {"none": 0, "test_ready": 0, "stage1_passed": 0, "learned": 0}
        due_today = 0
        total = 0
        per_deck: List[Dict[str, Any]] = []

        for d in decks:
            cards = self._load_cards(d)
            candidates = [self._to_candidate(c) for c in cards]
            d_levels = {"new": 0, "weak": 0, "medium": 0, "good": 0, "mastered": 0}
            d_grad = {"none": 0, "test_ready": 0, "stage1_passed": 0, "learned": 0}
            for c in cards:
                d_levels[c.state.mastery] = d_levels.get(c.state.mastery, 0) + 1
                levels[c.state.mastery] = levels.get(c.state.mastery, 0) + 1
                d_grad[c.state.graduation_state] = d_grad.get(c.state.graduation_state, 0) + 1
                graduation[c.state.graduation_state] = graduation.get(c.state.graduation_state, 0) + 1
            d_due = count_review_due(candidates, now)
            due_today += d_due
            total += len(cards)
            per_deck.append(
                {
                    "deck": d,
                    "total": len(cards),
                    "levels": d_levels,
                    "graduation": d_grad,
                    "due_today": d_due,
                    "active_rotation": count_active_rotation(candidates),
                    "daily_new_used": self._daily_new_count(d, date.today().isoformat()),
                }
            )

        return {
            "deck": deck,
            "total": total,
            "levels": levels,
            "graduation": graduation,
            "due_today": due_today,
            "streak_days": self._study_streak(date.today()),
            "decks": per_deck,
        }

    def rebuild_card_from_events(self, card_id: str) -> LearningState:
        events = self._load_events(card_id)
        return replay(events)

    # ── card helpers ───────────────────────────────────────────────────

    def get_card(self, card_id: str) -> Optional[CardRecord]:
        row = self._conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
        return self._row_to_card(row) if row else None

    def _load_cards(self, deck: str) -> List[CardRecord]:
        rows = self._conn.execute(
            "SELECT * FROM cards WHERE deck = ? ORDER BY created_at, id", (deck,)
        ).fetchall()
        return [self._row_to_card(r) for r in rows]

    def _row_to_card(self, row: sqlite3.Row) -> CardRecord:
        outcomes = json.loads(row["recent_outcomes_json"] or "[]")
        from .state import ReviewOutcome

        recent = tuple(
            ReviewOutcome(bool(o["was_correct"]), int(o["reaction_ms"])) for o in outcomes
        )
        state = LearningState(
            mastery=row["mastery"],
            srs_interval_days=row["srs_interval_days"],
            srs_ease=row["srs_ease"],
            srs_due_at=_parse_iso(row["srs_due_at"]),
            srs_reps=row["srs_reps"],
            srs_lapses=row["srs_lapses"],
            graduation_state=row["graduation_state"],
            graduation_stage1_at=_parse_iso(row["graduation_stage1_at"]),
            graduation_stage2_at=_parse_iso(row["graduation_stage2_at"]),
            recent_outcomes=recent,
        )
        return CardRecord(
            id=row["id"],
            deck=row["deck"],
            lemma=row["lemma"],
            reading=row["reading"],
            meaning=row["meaning"],
            pos=row["pos"],
            example=row["example"],
            source=row["source"],
            created_at=_parse_iso(row["created_at"]) or datetime.now(timezone.utc).replace(tzinfo=None),
            updated_at=_parse_iso(row["updated_at"]) or datetime.now(timezone.utc).replace(tzinfo=None),
            state=state,
            last_rating=row["last_rating"],
        )

    def _to_candidate(self, card: CardRecord) -> DeckCandidate:
        return DeckCandidate(
            sync_id=card.id,
            mastery=card.state.mastery,
            graduation_state=card.state.graduation_state,
            srs_due_at=card.state.srs_due_at,
            updated_at=card.updated_at,
            srs_reps=card.state.srs_reps,
            created_at=card.created_at,
            has_image=True,
        )

    def _append_event(
        self, card_id: str, kind: str, payload: Dict[str, Any], occurred_at: datetime
    ) -> str:
        event_id = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO events(event_id, card_id, kind, payload_json, occurred_at) VALUES (?, ?, ?, ?, ?)",
            (event_id, card_id, kind, json.dumps(payload), _iso(occurred_at)),
        )
        return event_id

    def _write_derived(
        self,
        card_id: str,
        state: LearningState,
        *,
        last_rating: Optional[int] = None,
        updated_at: Optional[datetime] = None,
    ) -> None:
        outcomes = [
            {"was_correct": o.was_correct, "reaction_ms": o.reaction_ms}
            for o in state.recent_outcomes
        ]
        fields = [
            state.mastery,
            state.srs_interval_days,
            state.srs_ease,
            _iso(state.srs_due_at) if state.srs_due_at else None,
            state.srs_reps,
            state.srs_lapses,
            state.graduation_state,
            _iso(state.graduation_stage1_at) if state.graduation_stage1_at else None,
            _iso(state.graduation_stage2_at) if state.graduation_stage2_at else None,
            json.dumps(outcomes),
            _iso(updated_at or datetime.now(timezone.utc).replace(tzinfo=None)),
        ]
        if last_rating is not None:
            self._conn.execute(
                """
                UPDATE cards SET mastery=?, srs_interval_days=?, srs_ease=?, srs_due_at=?,
                    srs_reps=?, srs_lapses=?, graduation_state=?, graduation_stage1_at=?,
                    graduation_stage2_at=?, recent_outcomes_json=?, updated_at=?, last_rating=?
                WHERE id=?
                """,
                (*fields, last_rating, card_id),
            )
        else:
            self._conn.execute(
                """
                UPDATE cards SET mastery=?, srs_interval_days=?, srs_ease=?, srs_due_at=?,
                    srs_reps=?, srs_lapses=?, graduation_state=?, graduation_stage1_at=?,
                    graduation_stage2_at=?, recent_outcomes_json=?, updated_at=?
                WHERE id=?
                """,
                (*fields, card_id),
            )

    def _load_events(self, card_id: str) -> List[EventRecord]:
        rows = self._conn.execute(
            "SELECT * FROM events WHERE card_id = ? ORDER BY occurred_at, event_id",
            (card_id,),
        ).fetchall()
        return [
            EventRecord(
                event_id=r["event_id"],
                kind=r["kind"],
                payload_json=r["payload_json"],
                occurred_at=_parse_iso(r["occurred_at"]) or datetime.now(timezone.utc).replace(tzinfo=None),
            )
            for r in rows
        ]

    def _last_ratings(self, card_id: str, n: int) -> List[int]:
        rows = self._conn.execute(
            "SELECT payload_json FROM events WHERE card_id = ? AND kind = 'review' "
            "ORDER BY occurred_at DESC, event_id DESC LIMIT ?",
            (card_id, n),
        ).fetchall()
        ratings = []
        for r in reversed(rows):
            payload = json.loads(r["payload_json"])
            ratings.append(int(payload.get("rating", 0)))
        return ratings

    def _daily_new_count(self, deck: str, day: str) -> int:
        row = self._conn.execute(
            "SELECT count FROM daily_new WHERE deck = ? AND day = ?", (deck, day)
        ).fetchone()
        return int(row["count"]) if row else 0

    def _set_daily_new_count(self, deck: str, day: str, count: int) -> None:
        self._conn.execute(
            "INSERT INTO daily_new(deck, day, count) VALUES (?, ?, ?) "
            "ON CONFLICT(deck, day) DO UPDATE SET count = excluded.count",
            (deck, day, count),
        )

    def _mark_study_day(self, day: date) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO study_days(day) VALUES (?)", (day.isoformat(),)
        )

    def _study_streak(self, today: date) -> int:
        days = {
            r["day"]
            for r in self._conn.execute("SELECT day FROM study_days").fetchall()
        }
        if not days:
            return 0
        streak = 0
        cursor = today
        # Allow today or yesterday as the streak tip.
        if today.isoformat() not in days:
            from datetime import timedelta

            cursor = today - timedelta(days=1)
            if cursor.isoformat() not in days:
                return 0
        from datetime import timedelta

        while cursor.isoformat() in days:
            streak += 1
            cursor = cursor - timedelta(days=1)
        return streak


def open_store(
    data_dir: Optional[Path] = None,
    daily_new_cap: int = DEFAULT_DAILY_NEW_CAP,
) -> WordMinerStore:
    """Open the plugin store. Uses Hermes plugin_data_dir when available."""
    if data_dir is None:
        try:
            from plugins.plugin_storage import plugin_data_dir

            data_dir = plugin_data_dir(PLUGIN_NAME)
        except Exception:
            data_dir = Path.home() / ".hermes" / "plugin-data" / PLUGIN_NAME
    return WordMinerStore(Path(data_dir) / "data.db", daily_new_cap=daily_new_cap)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat(timespec="seconds")


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt
