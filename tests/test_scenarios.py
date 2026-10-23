import tempfile
import unittest
from pathlib import Path

from app import db, scenarios


class DemoScenarioTests(unittest.TestCase):
    def setUp(self):
        self.original_path = db.DB_PATH
        self.temp_dir = tempfile.TemporaryDirectory()
        db.DB_PATH = Path(self.temp_dir.name) / "scenarios.db"
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.original_path
        self.temp_dir.cleanup()

    def test_seed_creates_four_complete_scenarios_once(self):
        self.assertEqual(scenarios.seed(), 4)
        self.assertEqual(scenarios.seed(), 0)
        self.assertEqual(len(db.get_patients()), 5)

        stable = db.adherence_summary(2)
        self.assertEqual(stable["percent"], 100)
        self.assertGreaterEqual(len(db.get_assessments(2)), 3)

        pregnancy = scenarios.public_scenario(3)
        self.assertIn("pregnancy", pregnancy["therapy_factors"])
        self.assertEqual(pregnancy["therapy_status"], "blocked")

        recommended = db.get_routing_signals(4, include_unconfirmed=True)
        self.assertEqual(recommended[0]["level"], "recommended")

        mandatory = db.get_routing_signals(5, include_unconfirmed=True)
        self.assertEqual(mandatory[0]["level"], "mandatory")
        alerts = db.refresh_and_get_alerts(10_000)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["patient_id"], 5)

    def test_public_scenarios_do_not_contain_patient_data(self):
        item = scenarios.public_scenario(5)
        self.assertEqual(item["slug"], "self-harm-alert")
        self.assertNotIn("phone", item)
        self.assertNotIn("seed", item)


if __name__ == "__main__":
    unittest.main()
