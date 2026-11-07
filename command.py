"""Slash command /deck — start or continue a one-card-at-a-time session in chat."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from .tools import deck_grade, deck_session, deck_stats, get_store

# Process-local session cursor keyed by a simple default (single-user local plugin).
_SESSION: Dict[str, Any] = {}


def reset_session() -> None:
    _SESSION.clear()


def handle_deck(raw_args: str = "") -> str:
    args = (raw_args or "").strip()
    if not args or args in ("help", "?"):
        return _help()

    parts = args.split(None, 1)
    head = parts[0].lower()
    rest = parts[1].strip() if len(parts) > 1 else ""

    if head == "stats":
        payload = json.loads(deck_stats(deck=rest or None))
        return _format_stats(payload)

    if head == "grade":
        return _handle_grade(rest)

    if head == "reveal":
        return _handle_reveal()

    if head == "list":
        decks = get_store().list_decks()
        if not decks:
            return "No decks yet. Mine words first (skill `word-miner:word-miner-extract`)."
        lines = ["Decks:"]
        for d in decks:
            lines.append(f"  · {d['name']} ({d['source_lang'] or '?'}→{d['target_lang'] or '?'})")
        return "\n".join(lines)

    # `/deck <name>` or `/deck` with a remembered deck → start/continue session.
    deck_name = args if head not in ("next", "continue") else (_SESSION.get("deck") or rest)
    if head in ("next", "continue"):
        deck_name = _SESSION.get("deck") or rest
    if not deck_name:
        return "Name a deck: `/deck ja-en` (or `/deck list`)."

    return _start_or_continue(deck_name)


def _start_or_continue(deck: str) -> str:
    if _SESSION.get("deck") != deck or not _SESSION.get("cards"):
        payload = json.loads(deck_session(deck=deck))
        if not payload.get("ok"):
            return f"Could not build session: {payload.get('error')}"
        cards = payload.get("cards") or []
        if not cards:
            return f"Deck `{deck}` has no cards yet. Mine some words first."
        _SESSION.clear()
        _SESSION.update(
            {
                "deck": deck,
                "cards": cards,
                "index": 0,
                "revealed": False,
                "active_rotation": payload.get("active_rotation"),
                "review_due": payload.get("review_due"),
            }
        )
        return _render_card(intro=True)

    # Advance if previous card was graded.
    if _SESSION.get("awaiting_advance"):
        _SESSION["index"] = int(_SESSION.get("index", 0)) + 1
        _SESSION["revealed"] = False
        _SESSION["awaiting_advance"] = False
        _SESSION.pop("shown_at_ms", None)

    idx = int(_SESSION.get("index", 0))
    cards = _SESSION.get("cards") or []
    if idx >= len(cards):
        stats = json.loads(deck_stats(deck=deck))
        _SESSION.clear()
        return "Session complete.\n" + _format_stats(stats)
    return _render_card(intro=False)


def _render_card(*, intro: bool) -> str:
    import time

    cards = _SESSION["cards"]
    idx = int(_SESSION["index"])
    card = cards[idx]
    _SESSION["shown_at_ms"] = int(time.time() * 1000)
    _SESSION["revealed"] = False
    total = len(cards)
    lines = []
    if intro:
        lines.append(
            f"Session `{_SESSION['deck']}` — {total} cards "
            f"(active rotation {_SESSION.get('active_rotation')}, due {_SESSION.get('review_due')})."
        )
        lines.append("Reply `/deck reveal` then `/deck grade <answer|1-4>`. `/deck next` after grading.")
        lines.append("")
    lines.append(f"Card {idx + 1}/{total} · {card.get('mastery')} · {card.get('prompt_side')}")
    lines.append(f"Q: {card.get('prompt')}")
    if card.get("hint"):
        lines.append(f"hint: {card.get('hint')}")
    lines.append(f"(card_id: {card.get('card_id')})")
    return "\n".join(lines)


def _handle_reveal() -> str:
    cards = _SESSION.get("cards") or []
    idx = int(_SESSION.get("index", 0))
    if not cards or idx >= len(cards):
        return "No active card. Start with `/deck <name>`."
    card = cards[idx]
    _SESSION["revealed"] = True
    return (
        f"Answer: {card.get('expected')}\n"
        f"lemma={card.get('lemma')} reading={card.get('reading') or '—'}\n"
        f"Grade: `/deck grade 3` (Good) / `4` (Easy) / `1` (Again), or type the answer."
    )


def _handle_grade(rest: str) -> str:
    import time

    cards = _SESSION.get("cards") or []
    idx = int(_SESSION.get("index", 0))
    if not cards or idx >= len(cards):
        return "No active card. Start with `/deck <name>`."
    card = cards[idx]
    if not rest:
        return "Usage: `/deck grade <typed answer>` or `/deck grade <1-4>`"

    shown = _SESSION.get("shown_at_ms")
    response_ms = int(time.time() * 1000) - int(shown) if shown else None

    rating: Optional[int] = None
    answer: Optional[str] = None
    if rest.strip() in ("1", "2", "3", "4"):
        rating = int(rest.strip())
    else:
        answer = rest

    payload = json.loads(
        deck_grade(
            card_id=card["card_id"],
            answer=answer,
            rating=rating,
            response_ms=response_ms,
        )
    )
    if not payload.get("ok"):
        return f"Grade failed: {payload.get('error')}"

    if payload.get("message"):
        return payload["message"] + "\nTry again: `/deck grade <answer>`"

    _SESSION["awaiting_advance"] = True
    correct = payload.get("correct")
    lines = [
        f"{'✓' if correct else '✗'} mastery={payload.get('mastery')} "
        f"next_due={payload.get('next_due') or '—'} "
        f"graduation={payload.get('graduation_state')}",
        "Continue: `/deck next`",
    ]
    return "\n".join(lines)


def _format_stats(payload: Dict[str, Any]) -> str:
    if not payload.get("ok", True) and payload.get("error"):
        return f"Stats error: {payload['error']}"
    levels = payload.get("levels") or {}
    grad = payload.get("graduation") or {}
    lines = [
        f"Total {payload.get('total', 0)} · due today {payload.get('due_today', 0)} · "
        f"streak {payload.get('streak_days', 0)} day(s)",
        "Levels: "
        + ", ".join(f"{k}={levels.get(k, 0)}" for k in ("new", "weak", "medium", "good", "mastered")),
        "Graduation: "
        + ", ".join(
            f"{k}={grad.get(k, 0)}" for k in ("none", "test_ready", "stage1_passed", "learned")
        ),
    ]
    for d in payload.get("decks") or []:
        lines.append(
            f"  · {d['deck']}: {d['total']} cards, due {d['due_today']}, "
            f"active {d['active_rotation']}, new today {d['daily_new_used']}"
        )
    return "\n".join(lines)


def _help() -> str:
    return (
        "word-miner `/deck` commands:\n"
        "  /deck <name>     start/continue a 10-card session\n"
        "  /deck reveal     show the answer\n"
        "  /deck grade …    typed answer or 1–4 self-grade\n"
        "  /deck next       next card\n"
        "  /deck stats [name]\n"
        "  /deck list\n"
        "Mine words with skill `word-miner:word-miner-extract`, then `deck_add_words`."
    )
