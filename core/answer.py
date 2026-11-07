"""Typed-answer normalisation (diacritics, case, punctuation)."""

from __future__ import annotations

import unicodedata

from .lemma import canonical as canonical_lemma


def type_recall_required(last_rating: int | None) -> bool:
    return last_rating == 4


def contains_wave_dash(japanese: str | None) -> bool:
    return bool(japanese) and any(_is_wave_dash_like(c) for c in japanese)


def matches(typed: str, expected: str) -> bool:
    return normalize(typed) == normalize(expected)


def prompt_gloss(lemma: str, meaning: str) -> str:
    """Gloss shown as the write-test prompt; strip lemma prefix if stuffed into meaning."""
    gloss = (meaning or "").strip()
    if not gloss:
        return gloss
    heads = []
    for head in ((lemma or "").strip(), canonical_lemma(lemma)):
        if head and head not in heads:
            heads.append(head)
    for head in heads:
        if gloss.startswith(head):
            rest = gloss[len(head) :].lstrip(" ·•\u002d—:　")
            return rest if rest else gloss
    return gloss


def normalize(value: str) -> str:
    # Strip sync-bug " (N)" so typed "mare" still matches leftover "mare (2)".
    normalized = unicodedata.normalize("NFKC", canonical_lemma(value))
    chars = []
    for c in normalized:
        if c.isspace() or _is_ignored_punctuation(c) or c in "()":
            continue
        chars.append(_canonical_romanian_letter(_canonical_wave_dash(c)))
    return "".join(chars).lower()


def _canonical_wave_dash(c: str) -> str:
    return "〜" if _is_wave_dash_like(c) else c


def _canonical_romanian_letter(c: str) -> str:
    # Fold ă/â/î/ș/ț (comma-below and cedilla) to ASCII so typing without diacritics still matches.
    mapping = {
        "ă": "a",
        "Ă": "a",
        "â": "a",
        "Â": "a",
        "î": "i",
        "Î": "i",
        "\u015e": "s",
        "\u0218": "s",
        "\u015f": "s",
        "\u0219": "s",
        "\u0162": "t",
        "\u021a": "t",
        "\u0163": "t",
        "\u021b": "t",
    }
    return mapping.get(c, c)


def _is_wave_dash_like(c: str) -> bool:
    return c in "~～〜〰"


def _is_ignored_punctuation(c: str) -> bool:
    return c in ".…⋯。、"
