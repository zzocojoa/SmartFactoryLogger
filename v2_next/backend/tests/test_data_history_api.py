import time
import unittest
from typing import Any

from fastapi.testclient import TestClient

from backend import app as backend_app
from backend.FacilityData.schemas import FactoryData


class DataHistoryApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clear_history()

    def tearDown(self) -> None:
        self.clear_history()

    def clear_history(self) -> None:
        backend_app.plc_service.clear_data_history()

    def build_sample(self, time_value: str, spot_value: float, count_value: int) -> FactoryData:
        return FactoryData(
            Time=time_value,
            Status="Running",
            Speed=1.0,
            Press=2.0,
            Count=count_value,
            EndPos=3.0,
            Billet_Length=4.0,
            Spot=spot_value,
            Temp_F=5.0,
            Temp_B=6.0,
            Billet_Temp=7.0,
            Mold1=8.0,
            Mold2=9.0,
            Mold3=10.0,
            Mold4=11.0,
            Mold5=12.0,
            Mold6=13.0,
            At_Temp=14.0,
            At_Pre=15.0,
        )

    def get_history(self, client: TestClient, since_ms: int, limit: int) -> dict[str, Any]:
        response = client.get(f"/api/data/history?since_ms={since_ms}&limit={limit}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsInstance(payload, dict)
        self.assertIsInstance(payload["samples"], list)
        return payload

    def test_history_returns_samples_since_last_visible_timestamp(self) -> None:
        base_sec = time.time() - 10.0
        timestamp_ms = [int((base_sec + offset_sec) * 1000) for offset_sec in [1.0, 2.0, 3.0]]
        samples = [
            self.build_sample("2026-05-21T00:00:01.000Z", 10.0, 1),
            self.build_sample("2026-05-21T00:00:02.000Z", 20.0, 2),
            self.build_sample("2026-05-21T00:00:03.000Z", 30.0, 3),
        ]

        backend_app.plc_service._record_history_sample(samples[0], base_sec + 1.0)
        backend_app.plc_service._record_history_sample(samples[1], base_sec + 2.0)
        backend_app.plc_service._record_history_sample(samples[2], base_sec + 3.0)

        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            response_payload = self.get_history(client, int((base_sec + 1.5) * 1000), 10)
        finally:
            client.close()

        history = response_payload["samples"]
        self.assertEqual([item["timestamp_ms"] for item in history], timestamp_ms[1:])
        self.assertEqual([item["data"]["Spot"] for item in history], [20.0, 30.0])
        self.assertEqual([item["data"]["Count"] for item in history], [2, 3])
        self.assertEqual([item["data"]["timestamp_ms"] for item in history], timestamp_ms[1:])
        self.assertEqual(response_payload["oldest_timestamp_ms"], timestamp_ms[0])
        self.assertEqual(response_payload["newest_timestamp_ms"], timestamp_ms[2])
        self.assertFalse(response_payload["truncated"])

    def test_history_read_is_idempotent_and_respects_limit(self) -> None:
        base_sec = time.time() - 10.0
        timestamp_ms = [int((base_sec + offset_sec) * 1000) for offset_sec in [1.0, 2.0, 3.0]]
        samples = [
            self.build_sample("2026-05-21T00:00:01.000Z", 10.0, 1),
            self.build_sample("2026-05-21T00:00:02.000Z", 20.0, 2),
            self.build_sample("2026-05-21T00:00:03.000Z", 30.0, 3),
        ]

        backend_app.plc_service._record_history_sample(samples[0], base_sec + 1.0)
        backend_app.plc_service._record_history_sample(samples[1], base_sec + 2.0)
        backend_app.plc_service._record_history_sample(samples[2], base_sec + 3.0)

        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            first_payload = self.get_history(client, 0, 2)
            second_payload = self.get_history(client, 0, 2)
        finally:
            client.close()

        first_history = first_payload["samples"]
        second_history = second_payload["samples"]
        self.assertEqual([item["timestamp_ms"] for item in first_history], timestamp_ms[1:])
        self.assertEqual(second_history, first_history)

    def test_history_marks_truncated_when_since_is_before_retention(self) -> None:
        base_sec = time.time() - 10.0
        timestamp_ms = [int((base_sec + offset_sec) * 1000) for offset_sec in [2.0, 3.0]]
        samples = [
            self.build_sample("2026-05-21T00:00:02.000Z", 20.0, 2),
            self.build_sample("2026-05-21T00:00:03.000Z", 30.0, 3),
        ]

        backend_app.plc_service._record_history_sample(samples[0], base_sec + 2.0)
        backend_app.plc_service._record_history_sample(samples[1], base_sec + 3.0)

        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            response_payload = self.get_history(client, int((base_sec + 1.0) * 1000), 10)
        finally:
            client.close()

        self.assertTrue(response_payload["truncated"])
        self.assertEqual(response_payload["oldest_timestamp_ms"], timestamp_ms[0])
        self.assertEqual([item["timestamp_ms"] for item in response_payload["samples"]], timestamp_ms)


if __name__ == "__main__":
    unittest.main()
