---
name: word-miner-extract
description: >
  Mine vocabulary from lyrics, subtitles, articles, or chat into a word-miner
  deck. Prefer lemmas, skip names and already-known words, include readings for
  CJK, keep meanings short, ask which deck.
---

# Mine words into word-miner

Use this skill when the user pastes or points at text they want to learn from
(song lyrics, subtitle blocks, an article paragraph, a chat excerpt).

## Steps

1. **Ask which deck** if unclear. Deck names are language pairs such as `ja-en`,
   `es-ru`, `fr-en`. Confirm source → target once, then reuse.
2. **Extract lemmas**, not inflected surface forms. Prefer the dictionary form
   the learner would look up.
3. **Skip**:
   - proper names / place names unless the user asks for them
   - words the user says they already know
   - function words that carry no useful meaning for their level
4. **For CJK (and other writing systems that need it)**: always include a
   `reading` / transcription field (hiragana, pinyin, …).
5. **Meanings**: one short gloss in the target language. Do not paste a
   dictionary essay. If the source line already embeds the lemma in the gloss,
   keep the gloss short — the tool stores lemma separately.
6. **Example**: copy the shortest source line that contains the word.
7. **Call the tool** `deck_add_words` with structured items:

```json
{
  "deck": "ja-en",
  "items": [
    {
      "lemma": "雨",
      "reading": "あめ",
      "meaning": "rain",
      "pos": "noun",
      "example": "雨が降っている",
      "source": "lyrics: example-song"
    }
  ]
}
```

8. Report the tool's `added` / `merged` / `skipped` counts. Mention when the
   daily new-word cap skipped items so the user can continue tomorrow.
9. Offer a study session: tell the user to run `/deck <name>` or call
   `deck_session`.

## Do not

- Do not invent tokenizer / MeCab / fugashi calls — you are the linguistics layer.
- Do not call external dictionary APIs; use your own knowledge of the languages.
- Do not dump dozens of filler words; quality over quantity (aim ~8–15 per paste).
