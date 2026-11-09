"""Load dashboard/plugin_api.py the way Hermes does and exercise each route.

Hermes (``hermes_cli.web_server_dashboard._mount_one_plugin_api``) imports the
file by path under a synthetic non-package name and mounts ``mod.router``.
This test mirrors that load shape, plants a conflicting top-level ``tools``
module on ``sys.path`` (as in the live Hermes process), and hits every route
against a temporary store.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_PATH = Path(os.environ.get("WORD_MINER_PLUGIN_API", str(ROOT / "dashboard" / "plugin_api.py")))


def _fastapi_available() -> bool:
    try:
        import fastapi  # noqa: F401
        from fastapi.testclient import TestClient  # noqa: F401

        return True
    except Exception:
        return False


def _install_fastapi_stub() -> None:
    """Minimal APIRouter stand-in so the module can load without FastAPI installed."""
    if "fastapi" in sys.modules:
        return

    class _APIRouter:
        def __init__(self) -> None:
            self.routes = []

        def get(self, path: str, **_kwargs):
            def deco(fn):
                self.routes.append(("GET", path, fn))
                return fn

            return deco

        def post(self, path: str, **_kwargs):
            def deco(fn):
                self.routes.append(("POST", path, fn))
                return fn

            return deco

    def _Body(default=None, default_factory=None, **_kwargs):
        if default_factory is not None:
            return default_factory()
        return default

    stub = types.ModuleType("fastapi")
    stub.APIRouter = _APIRouter  # type: ignore[attr-defined]
    stub.Body = _Body  # type: ignore[attr-defined]
    sys.modules["fastapi"] = stub


def _plant_conflicting_tools(tmpdir: Path) -> Path:
    """Put a Hermes-like top-level ``tools`` package ahead on sys.path.

    It must NOT expose word-miner handlers, so a bare ``import tools`` cannot
    silently reach the plugin's tools.py.
    """
    pkg = tmpdir / "tools"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        '"""Fake Hermes core tools package (no deck_* handlers)."""\nCORE = True\n'
    )
    sys.path.insert(0, str(tmpdir))
    sys.modules.pop("tools", None)
    return pkg


def _load_plugin_api(api_path: Path, module_name: str = "hermes_dashboard_plugin_word-miner"):
    """Import ``plugin_api.py`` exactly as Hermes mounts it (file path, synthetic name)."""
    if not _fastapi_available():
        _install_fastapi_stub()

    # Drop a prior load so each test gets a fresh module (router + store state).
    for key in list(sys.modules):
        if key == module_name or key.startswith(module_name + "."):
            sys.modules.pop(key, None)

    spec = importlib.util.spec_from_file_location(module_name, api_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestPluginApiHermesMount(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.conflict_root = self.tmp_path / "conflict"
        self.conflict_root.mkdir()
        _plant_conflicting_tools(self.conflict_root)
        # Ensure a bare import tools hits the conflict, not the plugin.
        import tools as planted  # noqa: F401

        self.assertTrue(getattr(planted, "CORE", False))
        self.assertFalse(hasattr(planted, "deck_stats"))

        self.data_dir = self.tmp_path / "plugin-data"
        self.data_dir.mkdir()
        self.mod = _load_plugin_api(API_PATH)

    def tearDown(self):
        if hasattr(self, "mod") and hasattr(self.mod, "configure_store"):
            try:
                self.mod.configure_store(None)
            except Exception:
                pass
        self.tmp.cleanup()

    def _seed_store(self):
        self.mod.configure_store(self.data_dir)
        store = self.mod._store()
        store.ensure_deck("ja-en", source_lang="ja", target_lang="en")
        store.add_words(
            "ja-en",
            [
                {
                    "lemma": "mizu",
                    "meaning": "water",
                    "reading": "みず",
                    "pos": "noun",
                    "example": "mizu o nomu",
                    "source": "fixture",
                },
                {
                    "lemma": "hi",
                    "meaning": "fire",
                    "reading": "ひ",
                    "pos": "noun",
                    "example": "hi ga tsuyoi",
                    "source": "fixture",
                },
            ],
        )
        return store

    def _call_routes(self):
        """Hit every route via TestClient when FastAPI works, else call functions directly."""
        use_client = False
        if _fastapi_available():
            try:
                from fastapi import APIRouter as RealAPIRouter
                from fastapi import FastAPI
                from fastapi.testclient import TestClient

                use_client = isinstance(self.mod.router, RealAPIRouter)
            except Exception:
                use_client = False

        if use_client:
            app = FastAPI()
            app.include_router(self.mod.router, prefix="/api/plugins/word-miner")
            client = TestClient(app)
            health = client.get("/api/plugins/word-miner/health").json()
            stats = client.get("/api/plugins/word-miner/stats", params={"deck": "ja-en"}).json()
            decks = client.get("/api/plugins/word-miner/decks").json()
            session = client.get(
                "/api/plugins/word-miner/session", params={"deck": "ja-en"}
            ).json()
            card = (session.get("cards") or [None])[0]
            grade = {"ok": False}
            if card:
                grade = client.post(
                    "/api/plugins/word-miner/grade",
                    json={
                        "card_id": card["card_id"],
                        "rating": 3,
                        "response_ms": 400,
                    },
                ).json()
            return health, stats, decks, session, grade

        health = self.mod.health()
        stats = self.mod.stats(deck="ja-en")
        decks = self.mod.decks()
        session = self.mod.session(deck="ja-en")
        card = (session.get("cards") or [None])[0]
        grade = {"ok": False}
        if card:
            grade = self.mod.grade(
                body={
                    "card_id": card["card_id"],
                    "rating": 3,
                    "response_ms": 400,
                }
            )
        return health, stats, decks, session, grade

    def test_router_mounted_and_routes_work(self):
        router = getattr(self.mod, "router", None)
        self.assertIsNotNone(
            router,
            "Hermes mounts only mod.router; register(router) alone never attaches routes",
        )
        self._seed_store()
        health, stats, decks, session, grade = self._call_routes()

        self.assertTrue(health.get("ok"), health)
        self.assertEqual(health.get("plugin"), "word-miner")

        self.assertTrue(stats.get("ok"), stats)
        self.assertGreaterEqual(stats.get("total", 0), 2)

        self.assertTrue(decks.get("ok"), decks)
        names = {d.get("name") if isinstance(d, dict) else d for d in decks.get("decks", [])}
        self.assertIn("ja-en", names)

        self.assertTrue(session.get("ok"), session)
        self.assertGreaterEqual(session.get("count", 0), 1)
        self.assertTrue(grade.get("ok"), grade)


if __name__ == "__main__":
    unittest.main()
