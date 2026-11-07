"""Answer normalisation golden cases."""

from __future__ import annotations

import unittest

from tests._path import ROOT  # noqa: F401
from core.answer import contains_wave_dash, matches, prompt_gloss, type_recall_required
from core.lemma import canonical, has_technical_suffix


class TestAnswer(unittest.TestCase):
    def test_type_recall_only_after_easy(self):
        self.assertFalse(type_recall_required(None))
        self.assertFalse(type_recall_required(3))
        self.assertTrue(type_recall_required(4))

    def test_punctuation_and_case(self):
        self.assertTrue(matches("あの...", "あの…"))
        self.assertTrue(matches(" お茶 ", "お茶"))
        self.assertTrue(matches("~半", "〜半"))
        self.assertTrue(matches("～半", "〜半"))
        self.assertTrue(contains_wave_dash("〜半"))
        self.assertFalse(contains_wave_dash("お茶"))
        self.assertTrue(matches("APA", "apa"))

    def test_romanian_diacritics(self):
        self.assertTrue(matches("peste", "peşte"))
        self.assertTrue(matches("peste", "pește"))
        self.assertTrue(matches("Țară", "țară"))
        self.assertTrue(matches("mâine", "MÂINE"))
        self.assertFalse(matches("apa", "peste"))

    def test_prompt_gloss_strips_lemma(self):
        self.assertEqual(prompt_gloss("おじさん", "おじさん дядя"), "дядя")
        self.assertEqual(prompt_gloss("canapea", "диван"), "диван")
        self.assertEqual(prompt_gloss("apa", "apa"), "apa")

    def test_lemma_canonical(self):
        self.assertEqual(canonical("mare (2)"), "mare")
        self.assertEqual(canonical("箱 (2)"), "箱")
        self.assertTrue(has_technical_suffix("mare (2)"))
        self.assertFalse(has_technical_suffix("mare"))
        self.assertTrue(matches("mare", "mare (2)"))
        self.assertTrue(matches("a dormi", "a dormi (3)"))


if __name__ == "__main__":
    unittest.main()
