"""Handlers must accept Hermes' ``handler(args, **kwargs)`` dispatch.

Live failure on 0.1.1 (e3776ae): Hermes calls ``entry.handler(args, **kwargs)``
(tools/registry.py ~986–988). Keyword-style handlers treated the whole args dict
as ``deck``, so ``deck_add_words`` always reported empty items and ``deck_stats``
hit ``'dict' object has no attribute 'strip'``.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from tests._path import load_plugin_package


class _FakeCtx:
    """Minimal PluginContext stand-in that records register_tool handlers."""

    def __init__(self) -> None:
        self.tools: Dict[str, Callable[..., str]] = {}

    def get_config(self, _key: str, default: Any = None) -> Any:
        return default

    def register_tool(
        self,
        name: str,
        toolset: str = "",
        schema: Optional[dict] = None,
        handler: Optional[Callable[..., str]] = None,
        **_: Any,
    ) -> None:
        assert handler is not None
        self.tools[name] = handler

    def register_command(self, *_a: Any, **_k: Any) -> None:
        return None

    def register_skill(self, *_a: Any, **_k: Any) -> None:
        return None


def _dispatch(handler: Callable[..., str], args: Any, **kwargs: Any) -> dict:
    """Mirror Hermes registry: ``entry.handler(args, **kwargs)``."""
    return json.loads(handler(args, **kwargs))


class TestHandlerSignature(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.pkg = load_plugin_package()
        self.tools = __import__(f"{self.pkg.__name__}.tools", fromlist=["*"])
        self.tools.configure(data_dir=Path(self.tmp.name), daily_new_cap=20)
        self.command = __import__(f"{self.pkg.__name__}.command", fromlist=["*"])
        self.command.reset_session()

        self.ctx = _FakeCtx()
        self.pkg.register(self.ctx)
        # Re-point store after register() which may reconfigure.
        self.tools.configure(data_dir=Path(self.tmp.name), daily_new_cap=20)

    def tearDown(self) -> None:
        self.tools.configure(data_dir=None)
        self.command.reset_session()
        self.tmp.cleanup()

    def test_registered_handlers_accept_positional_args_dict(self) -> None:
        """Reproduce the live reviewer call shape through register(ctx)."""
        add = self.ctx.tools["deck_add_words"]
        session = self.ctx.tools["deck_session"]
        grade = self.ctx.tools["deck_grade"]
        stats = self.ctx.tools["deck_stats"]

        items = [
            {"lemma": "猫", "meaning": "cat", "reading": "ねこ", "pos": "noun"},
            {"lemma": "犬", "meaning": "dog", "reading": "いぬ", "pos": "noun"},
        ]
        # Exact Hermes call: positional dict + injected context kwargs.
        added = _dispatch(
            add,
            {"deck": "ja-en", "items": items, "source_lang": "ja", "target_lang": "en"},
            task_id="t1",
            session_id="s1",
        )
        self.assertTrue(added["ok"], added)
        self.assertEqual(added["added"], 2)

        st = _dispatch(stats, {"deck": "ja-en"}, task_id="t1")
        self.assertTrue(st["ok"], st)
        self.assertEqual(st["total"], 2)

        sess = _dispatch(session, {"deck": "ja-en"})
        self.assertTrue(sess["ok"], sess)
        self.assertGreaterEqual(sess["count"], 1)
        card = sess["cards"][0]

        graded = _dispatch(
            grade,
            {
                "card_id": card["card_id"],
                "answer": card["expected"],
                "response_ms": "420",
            },
        )
        self.assertTrue(graded["ok"], graded)

    def test_args_as_json_string(self) -> None:
        """Deferred tool_call path may pass args as a JSON string."""
        payload = json.dumps(
            {
                "deck": "ja-en",
                "items": [{"lemma": "本", "meaning": "book", "reading": "ほん"}],
                "source_lang": "ja",
                "target_lang": "en",
            },
            ensure_ascii=False,
        )
        added = _dispatch(self.ctx.tools["deck_add_words"], payload)
        self.assertTrue(added["ok"], added)
        self.assertEqual(added["added"], 1)

        st = _dispatch(self.ctx.tools["deck_stats"], '{"deck": "ja-en"}')
        self.assertTrue(st["ok"], st)
        self.assertEqual(st["total"], 1)

    def test_items_as_json_string(self) -> None:
        items_json = json.dumps(
            [{"lemma": "水", "meaning": "water", "reading": "みず"}],
            ensure_ascii=False,
        )
        added = _dispatch(
            self.ctx.tools["deck_add_words"],
            {"deck": "ja-en", "items": items_json},
        )
        self.assertTrue(added["ok"], added)
        self.assertEqual(added["added"], 1)

    def test_numeric_fields_as_strings(self) -> None:
        add = self.ctx.tools["deck_add_words"]
        _dispatch(
            add,
            {
                "deck": "ja-en",
                "items": [{"lemma": "空", "meaning": "sky", "reading": "そら"}],
            },
        )
        sess = _dispatch(self.ctx.tools["deck_session"], {"deck": "ja-en"})
        card = sess["cards"][0]
        graded = _dispatch(
            self.ctx.tools["deck_grade"],
            {
                "card_id": card["card_id"],
                "rating": "3",
                "response_ms": "1500",
            },
        )
        self.assertTrue(graded["ok"], graded)

    def test_bad_types_return_clear_error(self) -> None:
        bad = _dispatch(self.ctx.tools["deck_add_words"], {"deck": "ja-en", "items": "not-json"})
        self.assertFalse(bad["ok"])
        self.assertIn("items", bad["error"])

        bad2 = _dispatch(self.ctx.tools["deck_stats"], [1, 2, 3])
        self.assertFalse(bad2["ok"])
        self.assertIn("object", bad2["error"])

        bad3 = _dispatch(
            self.ctx.tools["deck_grade"],
            {"card_id": "x", "rating": "nope"},
        )
        self.assertFalse(bad3["ok"])
        self.assertIn("rating", bad3["error"])

    def test_slash_command_still_works(self) -> None:
        """/deck adapts to the new signature without duplicating store logic."""
        _dispatch(
            self.ctx.tools["deck_add_words"],
            {
                "deck": "ja-en",
                "items": [
                    {"lemma": "花", "meaning": "flower", "reading": "はな"},
                    {"lemma": "月", "meaning": "moon", "reading": "つき"},
                ],
            },
        )
        out = self.command.handle_deck("ja-en")
        self.assertIn("Card 1/", out)
        self.assertIn("card_id:", out)

        stats_out = self.command.handle_deck("stats ja-en")
        self.assertIn("Total 2", stats_out)


if __name__ == "__main__":
    unittest.main()
