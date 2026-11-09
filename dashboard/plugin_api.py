"""Backend routes for the word-miner Desktop flashcard page.

Mounted at /api/plugins/word-miner/ when the agent half is enabled.

Hermes loads this file via ``importlib.util.spec_from_file_location`` under a
synthetic module name and mounts ``mod.router`` (see
``hermes_cli.web_server_dashboard._mount_one_plugin_api``). A module-level
``router = APIRouter()`` is required — a ``register(router)`` helper alone is
never called by the host.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Body

# Hermes imports this file as a lone module (not as part of the plugin package),
# and a bare ``import tools`` resolves to Hermes core's ``tools`` package. Put
# the plugin root on sys.path and open the store through ``core.store``.
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from core.store import WordMinerStore, open_store  # noqa: E402

router = APIRouter()

_DATA_DIR: Optional[Path] = None
_STORE: Optional[WordMinerStore] = None


def configure_store(data_dir: Optional[Path] = None) -> None:
    """Point the dashboard store at a data dir (tests) or reset to Hermes default."""
    global _DATA_DIR, _STORE
    if _STORE is not None:
        try:
            _STORE.close()
        except Exception:
            pass
    _STORE = None
    _DATA_DIR = Path(data_dir) if data_dir is not None else None


def _store() -> WordMinerStore:
    global _STORE
    if _STORE is None:
        _STORE = open_store(_DATA_DIR)
    return _STORE


@router.get("/health")
def health() -> dict:
    return {"ok": True, "plugin": "word-miner"}


@router.get("/stats")
def stats(deck: str = "") -> dict:
    result = _store().stats(deck=deck or None)
    result["ok"] = True
    return result


@router.get("/session")
def session(deck: str) -> dict:
    result = _store().build_session(deck)
    result["ok"] = True
    return result


@router.post("/grade")
def grade(body: dict[str, Any] = Body(default_factory=dict)) -> dict:
    return _store().grade(
        card_id=body.get("card_id", ""),
        answer=body.get("answer"),
        rating=body.get("rating"),
        response_ms=body.get("response_ms"),
        test_type=body.get("test_type"),
    )


@router.get("/decks")
def decks() -> dict:
    return {"ok": True, "decks": _store().list_decks()}
