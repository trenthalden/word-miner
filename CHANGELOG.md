# Changelog

## 0.1.1 — 2026-11-09

- Fix dashboard backend mount: expose module-level `router = APIRouter()` so Hermes
  (`mod.router`) actually mounts `/api/plugins/word-miner/*`.
- Open the SQLite store from `dashboard/plugin_api.py` via `core.store.open_store`
  (plugin root on `sys.path`), avoiding the broken `word_miner` / bare `tools`
  import fallback that resolved to Hermes core's `tools`.

## 0.1.0 — 2026-11-06

- Initial release: local SM-2-like SRS with response-time adjustment, multi-deck vocabulary mining, 3+3+3+1 study sessions, two-stage graduation, append-only event fold, typed-answer normalisation, TSV/CSV import helpers.
- Tools: `deck_add_words`, `deck_session`, `deck_grade`, `deck_stats`.
- Slash command `/deck` for chat-side sessions.
- Bundled skill `word-miner-extract`.
- Optional Desktop flashcard pane + dashboard backend routes.
