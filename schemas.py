"""JSON schemas for word-miner tools."""

DECK_ADD_WORDS = {
    "name": "deck_add_words",
    "description": (
        "Add vocabulary items to a personal spaced-repetition deck. "
        "Duplicates in the same deck are merged by lemma. Honours the per-day new-word cap "
        "(default 20). The model should extract lemma/reading/meaning/pos/example from text "
        "before calling this tool — no tokenizer is used."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "deck": {
                "type": "string",
                "description": "Deck name, typically a language pair like ja-en or es-ru.",
            },
            "items": {
                "type": "array",
                "description": "Structured vocabulary items mined from the user's text.",
                "items": {
                    "type": "object",
                    "properties": {
                        "lemma": {"type": "string", "description": "Dictionary form / headword."},
                        "reading": {
                            "type": "string",
                            "description": "Reading/transcription (required for CJK).",
                        },
                        "meaning": {"type": "string", "description": "Short gloss in the target language."},
                        "pos": {"type": "string", "description": "Part of speech."},
                        "example": {
                            "type": "string",
                            "description": "Example line from the source text.",
                        },
                        "source": {
                            "type": "string",
                            "description": "Optional provenance (song title, article URL, etc.).",
                        },
                    },
                    "required": ["lemma", "meaning"],
                },
            },
            "source_lang": {
                "type": "string",
                "description": "ISO language code of the lemmas (optional if encoded in deck name).",
            },
            "target_lang": {
                "type": "string",
                "description": "ISO language code of the meanings.",
            },
        },
        "required": ["deck", "items"],
    },
}

DECK_SESSION = {
    "name": "deck_session",
    "description": (
        "Build the next study session for a deck (up to 10 cards, composed 3 new + 3 weak + "
        "3 medium + 1 good when available; new cards only while active rotation < 20; "
        "tops up with nearest-due words so a day is never empty)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "deck": {"type": "string", "description": "Deck name."},
        },
        "required": ["deck"],
    },
}

DECK_GRADE = {
    "name": "deck_grade",
    "description": (
        "Grade a card after the user answers. Pass a typed `answer` (normalised for "
        "diacritics/case/punctuation) and/or a self-grade `rating` 1-4 (Again/Hard/Good/Easy). "
        "Optional `response_ms` adjusts ease (fast <500ms / slow >2000ms)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "card_id": {"type": "string", "description": "Card id from deck_session."},
            "answer": {"type": "string", "description": "Typed answer to check."},
            "rating": {
                "type": "integer",
                "description": "Self-grade 1=Again, 2=Hard, 3=Good, 4=Easy.",
                "minimum": 1,
                "maximum": 4,
            },
            "response_ms": {
                "type": "integer",
                "description": "Reaction time from prompt show to reveal/answer, in milliseconds.",
            },
            "test_type": {
                "type": "string",
                "description": "Graduation test stage: write_lemma or recognition.",
                "enum": ["write_lemma", "write_kanji", "recognition"],
            },
        },
        "required": ["card_id"],
    },
}

DECK_STATS = {
    "name": "deck_stats",
    "description": (
        "Vocabulary stats: counts per mastery level, due today, study-day streak, "
        "and graduation progress. Omit deck to summarise all decks."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "deck": {
                "type": "string",
                "description": "Optional deck name; omit for all decks.",
            },
        },
        "required": [],
    },
}
