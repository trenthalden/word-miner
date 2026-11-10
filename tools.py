"""Tool handlers for word-miner. Return JSON strings for the agent.

Hermes dispatches tools as ``handler(args, **kwargs)`` where ``args`` is the
parameter dict (see ``tools/registry.py`` and the plugin developer guide).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

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


def _error(message: str) -> str:
    return _json({"ok": False, "error": message})


def _coerce_args(args: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Normalize Hermes tool args (dict or JSON string) into a dict."""
    if args is None:
        return {}, None
    if isinstance(args, str):
        text = args.strip()
        if not text:
            return {}, None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            return None, f"args must be a JSON object: {exc}"
        args = parsed
    if not isinstance(args, dict):
        return None, f"args must be an object, got {type(args).__name__}"
    return args, None


def _as_str(value: Any, field: str) -> Tuple[Optional[str], Optional[str]]:
    if value is None:
        return "", None
    if isinstance(value, bool) or isinstance(value, (dict, list)):
        return None, f"{field} must be a string"
    return str(value).strip(), None


def _as_optional_str(value: Any, field: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (None, None) when absent/blank; otherwise a stripped string."""
    if value is None or value == "":
        return None, None
    if isinstance(value, bool) or isinstance(value, (dict, list)):
        return None, f"{field} must be a string"
    text = str(value).strip()
    return (text if text else None), None


def _as_optional_int(value: Any, field: str) -> Tuple[Optional[int], Optional[str]]:
    if value is None or value == "":
        return None, None
    if isinstance(value, bool):
        return None, f"{field} must be an integer"
    if isinstance(value, int):
        return value, None
    if isinstance(value, float) and value.is_integer():
        return int(value), None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None, None
        try:
            return int(text), None
        except ValueError:
            return None, f"{field} must be an integer"
    return None, f"{field} must be an integer"


def _as_items(value: Any) -> Tuple[Optional[list], Optional[str]]:
    if value is None:
        return None, "items must be a non-empty array"
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None, "items must be a non-empty array"
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            return None, f"items must be a JSON array: {exc}"
    if not isinstance(value, list):
        return None, "items must be a non-empty array"
    if not value:
        return None, "items must be a non-empty array"
    return value, None


def deck_add_words(args: Any = None, **_: Any) -> str:
    try:
        params, err = _coerce_args(args)
        if err:
            return _error(err)
        assert params is not None

        deck, err = _as_str(params.get("deck"), "deck")
        if err:
            return _error(err)
        if not deck:
            return _error("deck is required")

        items, err = _as_items(params.get("items"))
        if err:
            return _error(err)
        assert items is not None

        source_lang, err = _as_str(params.get("source_lang", ""), "source_lang")
        if err:
            return _error(err)
        target_lang, err = _as_str(params.get("target_lang", ""), "target_lang")
        if err:
            return _error(err)

        store = get_store()
        store.ensure_deck(deck, source_lang=source_lang or "", target_lang=target_lang or "")
        result = store.add_words(deck, items)
        result["ok"] = True
        return _json(result)
    except Exception as exc:
        logger.exception("deck_add_words failed")
        return _error(str(exc))


def deck_session(args: Any = None, **_: Any) -> str:
    try:
        params, err = _coerce_args(args)
        if err:
            return _error(err)
        assert params is not None

        deck, err = _as_str(params.get("deck"), "deck")
        if err:
            return _error(err)
        if not deck:
            return _error("deck is required")

        result = get_store().build_session(deck)
        result["ok"] = True
        return _json(result)
    except Exception as exc:
        logger.exception("deck_session failed")
        return _error(str(exc))


def deck_grade(args: Any = None, **_: Any) -> str:
    try:
        params, err = _coerce_args(args)
        if err:
            return _error(err)
        assert params is not None

        card_id, err = _as_str(params.get("card_id"), "card_id")
        if err:
            return _error(err)
        if not card_id:
            return _error("card_id is required")

        answer, err = _as_optional_str(params.get("answer"), "answer")
        if err:
            return _error(err)

        rating, err = _as_optional_int(params.get("rating"), "rating")
        if err:
            return _error(err)

        response_ms, err = _as_optional_int(params.get("response_ms"), "response_ms")
        if err:
            return _error(err)

        test_type, err = _as_optional_str(params.get("test_type"), "test_type")
        if err:
            return _error(err)

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
        return _error(str(exc))


def deck_stats(args: Any = None, **_: Any) -> str:
    try:
        params, err = _coerce_args(args)
        if err:
            return _error(err)
        assert params is not None

        deck, err = _as_optional_str(params.get("deck"), "deck")
        if err:
            return _error(err)

        result = get_store().stats(deck=deck)
        result["ok"] = True
        return _json(result)
    except Exception as exc:
        logger.exception("deck_stats failed")
        return _error(str(exc))
