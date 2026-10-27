import os

os.environ.setdefault("CLINICAL_COMPASS_DEMO_HEADERS", "1")

import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.rag.retrieval import doctor_index

DOCTOR = {"X-Demo-Role": "doctor"}
PATIENT = {"X-Demo-Role": "patient"}


class RAGRetrievalTests(unittest.TestCase):
    def test_specific_medication_query_returns_expected_fact_first(self):
        result = doctor_index().search("пароксетин доза при ГТР", 3)
        self.assertEqual(result["results"][0]["entity_ids"], ["ru_cr_gad_adult_457_3__M001"])
        self.assertEqual(result["audience"], "doctor")

    def test_safety_query_returns_rule_with_source_citation(self):
        result = doctor_index().search("длительность курса бензодиазепинов", 3)
        first = result["results"][0]
        self.assertEqual(first["entity_ids"], ["safety:S001"])
        self.assertTrue(first["source"]["title"])
        self.assertTrue(first["source"]["url"])
        self.assertIn("page", first["evidence"])

    def test_clinical_aliases_retrieve_matching_guideline_and_scale(self):
        gad = doctor_index().search("Авиандр при ГТР: линия терапии и доза", 6)
        gad_entities = {entity for row in gad["results"] for entity in row["entity_ids"]}
        self.assertIn("ru_cr_gad_adult_457_3__M016", gad_entities)

        depression = doctor_index().search("динамика HDRS и MADRS при депрессивном эпизоде", 6)
        depression_entities = {entity for row in depression["results"] for entity in row["entity_ids"]}
        self.assertIn("scale:hdrs17_ru", depression_entities)
        self.assertIn("scale:madrs_ru", depression_entities)

    def test_endpoint_is_doctor_only_and_honors_limit(self):
        with TestClient(app) as client:
            doctor = client.post("/api/rag/search", headers=DOCTOR, json={
                "query": "суицидальный риск",
                "limit": 2,
            })
            self.assertEqual(doctor.status_code, 200)
            self.assertEqual(len(doctor.json()["results"]), 2)
            self.assertEqual(client.post("/api/rag/search", headers=PATIENT, json={
                "query": "суицидальный риск",
            }).status_code, 403)

    def test_endpoint_validates_query_and_limit(self):
        with TestClient(app) as client:
            self.assertEqual(client.post("/api/rag/search", headers=DOCTOR, json={"query": "x"}).status_code, 422)
            self.assertEqual(client.post("/api/rag/search", headers=DOCTOR, json={
                "query": "тревога",
                "limit": 50,
            }).status_code, 422)


if __name__ == "__main__":
    unittest.main()
