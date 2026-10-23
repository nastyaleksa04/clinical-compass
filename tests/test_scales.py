import unittest

from app.scales import score


class ScaleScoringTests(unittest.TestCase):
    def test_gad7_zero_score(self):
        result = score("gad7", [0] * 7)
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["severity"], "Минимальная выраженность")
        self.assertFalse(result["alert"])

    def test_gad7_high_score(self):
        result = score("gad7", [3] * 7)
        self.assertEqual(result["total"], 21)
        self.assertEqual(result["severity"], "Высокая выраженность")

    def test_phq9_self_harm_answer_creates_alert(self):
        result = score("phq9", [0] * 8 + [1])
        self.assertEqual(result["total"], 1)
        self.assertTrue(result["alert"])
        self.assertIn("self_harm_response", result["alert_codes"])

    def test_incomplete_answers_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "все вопросы"):
            score("phq9", [0, 0])


if __name__ == "__main__":
    unittest.main()