# Demo shot list (< 90 s)

Target: show mining → session → stats without leaving Hermes.

## Setup (off-camera)

- Isolated `HERMES_HOME` with word-miner installed and enabled.
- Empty deck `ja-en` (or delete `plugin-data/word-miner` first).

## Shots

| # | Seconds | What to show | Exact prompt / command | Expected screen |
|---|---------|--------------|------------------------|-----------------|
| 1 | 0–15 | Paste a short verse | User: “Mine vocabulary from this into deck `ja-en` using skill word-miner:word-miner-extract:” + 4–6 lyric lines (synthetic, no personal data) | Agent loads skill, asks/confirms deck if needed |
| 2 | 15–35 | Tool call | Agent calls `deck_add_words` with ~12 items (lemma, reading, short meaning, example) | Tool result: `added: 12`, `merged: 0`, `skipped: 0` |
| 3 | 35–55 | Session | User types `/deck ja-en` | Card 1/10 with prompt; then `/deck reveal` shows answer; `/deck grade 4` (or typed lemma) updates mastery |
| 4 | 55–70 | Timer path | Mention response timing: grade with a quick Easy vs a slow Again on next card | Chat shows mastery / next_due |
| 5 | 70–85 | Stats | `/deck stats ja-en` | Levels (new/weak/…), due today, streak ≥1, graduation counts |
| 6 | 85–90 | Close | Optional: Desktop “deck” pane if enabled — flashcard + stats panel | Same numbers as `/deck stats` |

## Notes for the narrator

- Emphasize: **local only**, no Anki, no network.
- Contrast: catalog `anki` plugin needs Anki + AnkiConnect; word-miner does not.
- If Desktop pane is not live, end on `/deck stats` (pane documented as OPEN).
