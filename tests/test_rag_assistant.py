import os

os.environ.setdefault("CLINICAL_COMPASS_DEMO_HEADERS", "1")

import json
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.rag.assistant import (
    OpenRouterClient,
    OpenRouterNotConfigured,
    OpenRouterSettings,
    answer,
    status_payload,
)
from app.rag.retrieval import KnowledgeIndex

DOCTOR = {"X-Demo-Role": "doctor"}
PATIENT = {"X-Demo-Role": "patient"}


class FakeClient:
    def __init__(self, content="Факт подтверждён источником [1]."):
        self.content = content
        self.messages = None

    def complete(self, messages):
        self.messages = messages
        return {
            "content": self.content,
            "model": "test/model",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "request_id": "test-request",
        }


class RAGAssistantTests(unittest.TestCase):
    def test_status_does_not_expose_api_key(self):
        settings = OpenRouterSettings(
            api_key="secret-value",
            model="test/model",
            base_url="https://example.test",
            timeout_seconds=10,
            site_url="",
            app_name="test",
        )
        payload = status_payload(settings)
        self.assertTrue(payload["configured"])
        self.assertNotIn("api_key", payload)
        self.assertNotIn("secret-value", str(payload))

    def test_answer_uses_retrieved_context_and_returns_numbered_citations(self):
        client = FakeClient()
        result = answer(
            "пароксетин доза при ГТР",
            limit=3,
            client=client,
            index=KnowledgeIndex(),
        )
        self.assertTrue(result["grounded"])
        self.assertEqual("test/model", result["model"])
        self.assertEqual(1, result["citations"][0]["number"])
        self.assertIn("[1]", result["answer"])
        self.assertIn("Фрагменты базы знаний", client.messages[1]["content"])
        self.assertNotIn("secret", client.messages[1]["content"])

    def test_unknown_citation_is_reported(self):
        result = answer(
            "пароксетин доза при ГТР",
            limit=2,
            client=FakeClient("Ответ [99]."),
            index=KnowledgeIndex(),
        )
        self.assertFalse(result["grounded"])
        self.assertTrue(result["citation_warnings"])

    def test_missing_key_is_a_clear_configuration_error(self):
        with patch.dict(os.environ, {}, clear=True):
            from app.rag.assistant import OpenRouterClient
            with self.assertRaises(OpenRouterNotConfigured):
                OpenRouterClient().complete([])

    def test_client_retries_once_when_provider_returns_empty_content(self):
        settings = OpenRouterSettings(
            api_key="test-key",
            model="qwen/test",
            base_url="https://example.test",
            timeout_seconds=10,
            site_url="",
            app_name="test",
        )

        class Response:
            def __init__(self, payload):
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return json.dumps(self.payload).encode("utf-8")

        empty = Response({
            "choices": [{"message": {"content": "", "reasoning": "thinking"}, "finish_reason": "length"}],
        })
        complete = Response({
            "id": "retry-ok",
            "model": "qwen/test",
            "choices": [{"message": {"content": "Ответ [1]."}, "finish_reason": "stop"}],
            "usage": {"completion_tokens": 5},
        })
        with patch("app.rag.assistant.urlopen", side_effect=[empty, complete]) as mocked:
            result = OpenRouterClient(settings).complete([{"role": "user", "content": "Вопрос"}])
        self.assertEqual("Ответ [1].", result["content"])
        self.assertTrue(result["retried"])
        self.assertEqual(2, mocked.call_count)
        first_payload = json.loads(mocked.call_args_list[0].args[0].data.decode("utf-8"))
        retry_payload = json.loads(mocked.call_args_list[1].args[0].data.decode("utf-8"))
        self.assertEqual(1800, first_payload["max_tokens"])
        self.assertEqual("low", first_payload["reasoning"]["effort"])
        self.assertFalse(retry_payload["reasoning"]["enabled"])

    def test_endpoints_are_doctor_only_and_errors_are_sanitized(self):
        with TestClient(app) as client:
            self.assertEqual(client.get("/api/rag/status", headers=PATIENT).status_code, 403)
            self.assertEqual(client.post(
                "/api/rag/answer",
                headers=PATIENT,
                json={"query": "тестовый вопрос"},
            ).status_code, 403)
            with patch("app.main.rag_assistant.answer", side_effect=OpenRouterNotConfigured("Настройте ключ")):
                response = client.post(
                    "/api/rag/answer",
                    headers=DOCTOR,
                    json={"query": "тестовый вопрос"},
                )
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["detail"], "Настройте ключ")


if __name__ == "__main__":
    unittest.main()
