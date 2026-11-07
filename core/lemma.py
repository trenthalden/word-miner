"""Lemma canonicalisation — strip technical disambiguators like ' (2)'."""

from __future__ import annotations

import re

_TECHNICAL_SUFFIX = re.compile(r" \(\d+\)$")


def has_technical_suffix(lemma: str | None) -> bool:
    return bool(lemma) and bool(_TECHNICAL_SUFFIX.search(lemma))


def canonical(lemma: str | None) -> str:
    """Strip every trailing ' (N)' so 'an (4)' → 'an'. Idempotent."""
    head = (lemma or "").strip()
    if not head:
        return head
    while True:
        nxt = _TECHNICAL_SUFFIX.sub("", head)
        if nxt == head:
            return head
        head = nxt.rstrip()
