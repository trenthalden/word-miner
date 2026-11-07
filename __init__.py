"""word-miner — local spaced-repetition vocabulary decks inside Hermes."""

from __future__ import annotations

import logging
from pathlib import Path

from . import schemas, tools
from .command import handle_deck

logger = logging.getLogger(__name__)

PLUGIN_NAME = "word-miner"


def register(ctx) -> None:
    """Wire tools, slash command, and bundled extract skill."""
    # Settings: daily new-word cap (default 20).
    daily_cap = 20
    try:
        raw = ctx.get_config("daily_new_cap", default=20)
        daily_cap = int(raw) if raw is not None else 20
    except Exception:
        daily_cap = 20

    # Prefer Hermes plugin data dir; fall back inside tools.open_store.
    data_dir = None
    try:
        from plugins.plugin_storage import plugin_data_dir

        data_dir = plugin_data_dir(PLUGIN_NAME)
    except Exception as exc:
        logger.debug("word-miner: plugin_data_dir unavailable (%s); tools will resolve later", exc)

    tools.configure(data_dir=data_dir, daily_new_cap=daily_cap)

    toolset = PLUGIN_NAME
    ctx.register_tool(
        name="deck_add_words",
        toolset=toolset,
        schema=schemas.DECK_ADD_WORDS,
        handler=tools.deck_add_words,
    )
    ctx.register_tool(
        name="deck_session",
        toolset=toolset,
        schema=schemas.DECK_SESSION,
        handler=tools.deck_session,
    )
    ctx.register_tool(
        name="deck_grade",
        toolset=toolset,
        schema=schemas.DECK_GRADE,
        handler=tools.deck_grade,
    )
    ctx.register_tool(
        name="deck_stats",
        toolset=toolset,
        schema=schemas.DECK_STATS,
        handler=tools.deck_stats,
    )

    ctx.register_command(
        "deck",
        handler=handle_deck,
        description="Study a vocabulary deck (session / grade / stats)",
        args_hint="[<name>|stats|list|reveal|grade|next]",
    )

    skills_dir = Path(__file__).resolve().parent / "skills"
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            skill_md = child / "SKILL.md"
            if child.is_dir() and skill_md.exists():
                ctx.register_skill(child.name, skill_md)

    logger.info(
        "word-miner registered (daily_new_cap=%s, data=%s)",
        daily_cap,
        data_dir or "(default)",
    )
