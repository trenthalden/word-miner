"""TSV/CSV import for vocabulary rows. Port of LearningWordImport.cs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class ImportRow:
    lemma: str
    meaning: str
    notes: str = ""
    level: str = ""
    reading: str = ""


def parse_import(text: str) -> List[ImportRow]:
    """Header optional. Columns: lemma, meaning [, notes] [, level] [, reading]. Tab or comma."""
    rows: List[ImportRow] = []
    if not text or not text.strip():
        return rows

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    started = False
    for raw in lines:
        line = raw.strip()
        if not line or line[0] == "#":
            continue

        sep = "\t" if "\t" in line else ","
        cols = _split(line, sep)
        if len(cols) < 2:
            continue

        lemma = cols[0].strip()
        meaning = cols[1].strip()
        if not started:
            started = True
            if _looks_like_header(lemma, meaning):
                continue

        if not lemma or not meaning:
            continue
        notes = cols[2].strip() if len(cols) > 2 else ""
        level = cols[3].strip() if len(cols) > 3 else ""
        reading = cols[4].strip() if len(cols) > 4 else ""
        rows.append(ImportRow(lemma, meaning, notes, level, reading))

    return rows


def _looks_like_header(a: str, b: str) -> bool:
    a = a.lower()
    b = b.lower()
    return a in ("word", "lemma", "japanese", "cuvânt", "cuvant", "слово") and b in (
        "meaning",
        "translation",
        "перевод",
        "sense",
    )


def _split(line: str, sep: str) -> List[str]:
    cols: List[str] = []
    cur: List[str] = []
    in_quotes = False
    i = 0
    while i < len(line):
        c = line[i]
        if c == '"':
            if in_quotes and i + 1 < len(line) and line[i + 1] == '"':
                cur.append('"')
                i += 1
            else:
                in_quotes = not in_quotes
            i += 1
            continue
        if c == sep and not in_quotes:
            cols.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    cols.append("".join(cur))
    return cols
