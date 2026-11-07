"""Backend routes for the word-miner Desktop flashcard page.

Mounted at /api/plugins/word-miner/ when the agent half is enabled.
"""

from __future__ import annotations

import json
from typing import Any

# Import the shared store through the installed plugin package when available;
# fall back to sibling import for linked checkouts under plugins/.
try:
    from word_miner import tools as wm_tools  # type: ignore
except Exception:
    try:
        import tools as wm_tools  # type: ignore
    except Exception:
        wm_tools = None  # type: ignore


def register(router) -> None:
    """Register FastAPI-style routes on the plugin router."""

    @router.get("/health")
    def health() -> dict:
        return {"ok": True, "plugin": "word-miner"}

    @router.get("/stats")
    def stats(deck: str = "") -> dict:
        if wm_tools is None:
            return {"ok": False, "error": "word-miner tools unavailable in this process"}
        raw = wm_tools.deck_stats(deck=deck or None)
        return json.loads(raw)

    @router.get("/session")
    def session(deck: str) -> dict:
        if wm_tools is None:
            return {"ok": False, "error": "word-miner tools unavailable in this process"}
        raw = wm_tools.deck_session(deck=deck)
        return json.loads(raw)

    @router.post("/grade")
    def grade(body: dict[str, Any]) -> dict:
        if wm_tools is None:
            return {"ok": False, "error": "word-miner tools unavailable in this process"}
        raw = wm_tools.deck_grade(
            card_id=body.get("card_id", ""),
            answer=body.get("answer"),
            rating=body.get("rating"),
            response_ms=body.get("response_ms"),
            test_type=body.get("test_type"),
        )
        return json.loads(raw)

    @router.get("/decks")
    def decks() -> dict:
        if wm_tools is None:
            return {"ok": False, "error": "word-miner tools unavailable in this process"}
        store = wm_tools.get_store()
        return {"ok": True, "decks": store.list_decks()}
