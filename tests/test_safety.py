import unittest

from app.safety import assessment_signal, checkin_signal, report_signal


class SafetyRuleTests(unittest.TestCase):
    def test_urgent_report_is_mandatory(self):
        signal = report_signal({'urgent': True})
        self.assertEqual(signal['level'], 'mandatory')
        self.assertEqual(signal['reason_code'], 'urgent_patient_request')

    def test_self_harm_response_is_mandatory(self):
        signal = assessment_signal('phq9', {'total': 1, 'alert_codes': ['self_harm_response']})
        self.assertEqual(signal['level'], 'mandatory')

    def test_high_screening_score_is_recommended(self):
        signal = assessment_signal('gad7', {'total': 15, 'alert_codes': []})
        self.assertEqual(signal['level'], 'recommended')
        self.assertEqual(signal['reason_code'], 'high_screening_score')

    def test_severe_adverse_event_is_mandatory(self):
        signal = checkin_signal({'taken': True, 'side_effect_severity': 'severe'})
        self.assertEqual(signal['level'], 'mandatory')

    def test_missed_therapy_is_recommended(self):
        signal = checkin_signal({'taken': False, 'side_effect_severity': 'none'})
        self.assertEqual(signal['level'], 'recommended')

    def test_normal_checkin_has_no_signal(self):
        self.assertIsNone(checkin_signal({'taken': True, 'side_effect_severity': 'none'}))


if __name__ == '__main__':
    unittest.main()
