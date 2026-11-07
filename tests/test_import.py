"""TSV/CSV import golden cases."""

from __future__ import annotations

import unittest

from tests._path import ROOT  # noqa: F401
from core.import_words import parse_import


class TestImport(unittest.TestCase):
    def test_tsv_csv_header_comment_reading(self):
        rows = parse_import("word\tmeaning\napa\tвода\n# comment\nmâine,завтра,наречие,A1\n")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].lemma, "apa")
        self.assertEqual(rows[0].meaning, "вода")
        self.assertEqual(rows[1].lemma, "mâine")
        self.assertEqual(rows[1].notes, "наречие")
        self.assertEqual(rows[1].level, "A1")

        with_reading = parse_import("lemma\tmeaning\tnotes\tlevel\treading\n水\tвода\t\tN5\tみず\n")
        self.assertEqual(len(with_reading), 1)
        self.assertEqual(with_reading[0].reading, "みず")
        self.assertEqual(parse_import(""), [])


if __name__ == "__main__":
    unittest.main()
