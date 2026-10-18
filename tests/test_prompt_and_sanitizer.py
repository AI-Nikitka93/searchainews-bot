import os
import unittest
from pathlib import Path

from ai_analyzer import (
    strip_citation_brackets,
    clean_action_item,
    format_impact_rationale,
    validate_payload,
    get_prompt_path,
)
from ai_config import MAX_COMPLETION_TOKENS


class TestPromptAndSanitizer(unittest.TestCase):
    def test_strip_citation_brackets(self):
        sample = "Проверить cited-источники [1][2][3] для валидации приведённых метрик [4]."
        cleaned = strip_citation_brackets(sample)
        self.assertIn(cleaned, [
            "Проверить cited-источники для валидации приведённых метрик.",
            "Проверить cited-источники для валидации приведённых метрик .",
        ])

        sample2 = "Модель превосходит baseline [1] на 5% [2, 3] и [^4]."
        cleaned2 = strip_citation_brackets(sample2)
        self.assertNotIn("[1]", cleaned2)
        self.assertNotIn("[2, 3]", cleaned2)
        self.assertNotIn("[^4]", cleaned2)

    def test_action_item_never_cuts_mid_word(self):
        long_action = "Проверить корректность работы алгоритма на больших объемах данных и Пересечение топовых ссылок"
        # Truncating at 90 chars would hit in the middle of 'ссылок' ('ссыло')
        cleaned = clean_action_item(long_action, max_len=90)
        self.assertIsNotNone(cleaned)
        self.assertNotIn("ссыло", cleaned)
        self.assertTrue(cleaned.endswith("топовых"))

    def test_clean_action_item_rejects_citation_checks(self):
        # Action item copied from footnotes must be rejected
        bad_action = "Проверить cited-источники [1][2][3] для валидации приведённых метрик"
        self.assertIsNone(clean_action_item(bad_action))

        bad_action_2 = "Проверить источники для оценки надежности"
        self.assertIsNone(clean_action_item(bad_action_2))

        bad_action_3 = "Check cited sources for confirmation"
        self.assertIsNone(clean_action_item(bad_action_3))

        # Real technical actions must be retained and cleaned
        good_action = "Запустить бенчмарк инференса на vLLM с квантованием FP8 [1]"
        cleaned = clean_action_item(good_action)
        self.assertIsNotNone(cleaned)
        self.assertEqual(cleaned, "Запустить бенчмарк инференса на vLLM с квантованием FP8")

    def test_format_impact_rationale_sentence_completion(self):
        # When text has trailing incomplete sentence, it must be cleanly discarded
        text = (
            "Команда представила новую архитектуру с квантованием FP8. "
            "Инференс ускоряется в 2 раза на GPU RTX 4090. "
            "Инженерам рекомендуется протестировать лока"  # cut off mid-word
        )
        formatted = format_impact_rationale(text, max_chars=320, max_sentences=3)
        self.assertTrue(formatted.endswith("."))
        self.assertNotIn("протестировать лока", formatted)
        self.assertIn("Инференс ускоряется в 2 раза на GPU RTX 4090.", formatted)

    def test_format_impact_rationale_strips_citations(self):
        text = "Релиз открытых весов [1][2] меняет стек разработки [3]. Доступны чекпоинты 7B и 14B."
        formatted = format_impact_rationale(text, max_chars=320, max_sentences=3)
        self.assertNotIn("[1]", formatted)
        self.assertNotIn("[2]", formatted)
        self.assertNotIn("[3]", formatted)
        self.assertTrue(formatted.endswith("."))

    def test_validate_payload_terminal_punctuation(self):
        import logging
        logger = logging.getLogger("test")

        valid_payload = {
            "impact_score": 4,
            "target_role": "ai_developer",
            "impact_rationale": "Релиз весов открывает новые возможности локального инференса. Модель оптимизирована под vLLM.",
            "action_items": ["Запустить бенчмарк на GPU", "Проверить квантование"],
            "confidence": 0.9,
        }
        self.assertTrue(validate_payload(valid_payload, logger, "https://example.com"))

        invalid_payload = {
            "impact_score": 4,
            "target_role": "ai_developer",
            "impact_rationale": "Релиз весов открывает новые возможности локального инференса без точки в конце",
            "action_items": ["Запустить бенчмарк на GPU", "Проверить квантование"],
            "confidence": 0.9,
        }
        self.assertFalse(validate_payload(invalid_payload, logger, "https://example.com"))

    def test_prompt_template_contains_strict_rules(self):
        prompt_path = get_prompt_path()
        content = prompt_path.read_text(encoding="utf-8")

        # Must strictly forbid citation brackets
        self.assertIn("[1], [2], [3]", content)
        self.assertIn("ЖЁСТКИЙ ЗАПРЕТ СНОСОК", content)
        # Must enforce sentence completion and punctuation
        self.assertIn("ЗАВЕРШЁННОСТЬ ПРЕДЛОЖЕНИЙ", content)
        self.assertIn("ОБЯЗАТЕЛЬНО должно заканчиваться точкой", content)
        # Must specify Habr style
        self.assertIn("Habr-style", content)

    def test_token_budget_config(self):
        self.assertGreaterEqual(MAX_COMPLETION_TOKENS, 1000)


if __name__ == "__main__":
    unittest.main()
