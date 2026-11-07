"""Tool handlers for word-miner. Return JSON strings for the agent."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from .core.store import DEFAULT_DAILY_NEW_CAP, WordMinerStore, open_store

logger = logging.getLogger(__name__)

_STORE: Optional[WordMinerStore] = None
_DATA_DIR: Optional[Path] = None
_DAILY_CAP = DEFAULT_DAILY_NEW_CAP


def configure(data_dir: Optional[Path] = None, daily_new_cap: int = DEFAULT_DAILY_NEW_CAP) -> None:
    """Reset the process-local store (used by tests and register())."""
    global _STORE, _DATA_DIR, _DAILY_CAP
    if _STORE is not None:
        try:
            _STORE.close()
        except Exception:
            pass
    _STORE = None
    _DATA_DIR = Path(data_dir) if data_dir else None
    _DAILY_CAP = daily_new_cap


def get_store() -> WordMinerStore:
    global _STORE
    if _STORE is None:
        _STORE = open_store(_DATA_DIR, daily_new_cap=_DAILY_CAP)
    return _STORE


def _json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def deck_add_words(
    deck: str = "",
    items: Any = None,
    source_lang: str = "",
    target_lang: str = "",
    **_: Any,
) -> str:
    try:
        if not deck:
            return _json({"ok": False, "error": "deck is required"})
        if not isinstance(items, list) or not items:
            return _json({"ok": False, "error": "items must be a non-empty array"})
        store = get_store()
        store.ensure_deck(deck, source_lang=source_lang or "", target_lang=target_lang or "")
        result = store.add_words(deck, items)
        result["ok"] = True
        return _json(result)
    except Exception as exc:
        logger.exception("deck_add_words failed")
        return _json({"ok": False, "error": str(exc)})


def deck_session(deck: str = "", **_: Any) -> str:
    try:
        if not deck:
            return _json({"ok": False, "error": "deck is required"})
        result = get_store().build_session(deck)
        result["ok"] = True
        return _json(result)
    except Exception as exc:
        logger.exception("deck_session failed")
        return _json({"ok": False, "error": str(exc)})


def deck_grade(
    card_id: str = "",
    answer: Optional[str] = None,
    rating: Optional[int] = None,
    response_ms: Optional[int] = None,
    test_type: Optional[str] = None,
    **_: Any,
) -> str:
    try:
        if not card_id:
            return _json({"ok": False, "error": "card_id is required"})
        result = get_store().grade(
            card_id,
            answer=answer,
            rating=rating,
            response_ms=response_ms,
            test_type=test_type,
        )
        return _json(result)
    except Exception as exc:
        logger.exception("deck_grade failed")
        return _json({"ok": False, "error": str(exc)})


def deck_stats(deck: Optional[str] = None, **_: Any) -> str:
    try:
        result = get_store().stats(deck=deck or None)
        result["ok"] = True
        return _json(result)
    except Exception as exc:
        logger.exception("deck_stats failed")
        return _json({"ok": False, "error": str(exc)})
