import unittest
from app.therapy import evaluate

class TherapyRuleTests(unittest.TestCase):
    def test_pregnancy_blocks_aviandr(self):
        result=evaluate('aviandr', {'pregnancy': True})
        self.assertEqual(result['status'], 'not_suitable')
        self.assertEqual(result['findings'][0]['level'], 'blocked')

    def test_interaction_requires_review(self):
        result=evaluate('aviandr', {'serotonergic_drugs': True})
        self.assertEqual(result['status'], 'review_required')

    def test_clear_checklist_does_not_prescribe(self):
        result=evaluate('aviandr', {})
        self.assertEqual(result['status'], 'no_flags')
        self.assertIn('не является назначением', result['disclaimer'])

    def test_unknown_medication_is_rejected(self):
        with self.assertRaises(ValueError):
            evaluate('unknown', {})

if __name__ == '__main__':
    unittest.main()
