import csv
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import app as backend_app
from backend.FacilityData.drivers.real_plc import MelsecResponseError, RealPLCDriver, _parse_melsec_values
from backend.FacilityData.repository import CSVLoggerService, V1_CSV_COLUMNS, V2_CSV_COLUMNS
from backend.FacilityData.schemas import FactoryData, OperatorMetadata, OperatorMetadataUpdate
from scripts.validate_csv_v2_shadow import validate as validate_csv_v2_shadow
from scripts.validate_csv_v2_shadow import validate_many as validate_csv_v2_shadow_many


class MelsecParseTests(unittest.TestCase):
    def test_parse_melsec_values_returns_hex_words(self) -> None:
        values = _parse_melsec_values("D0020", 2, b"01OK000A0014\r\n", "01OK000A0014")

        self.assertEqual(values, [10, 20])

    def test_parse_melsec_values_raises_with_context_for_invalid_hex(self) -> None:
        raw = b"01OK000G0014\r\n"

        with self.assertRaises(MelsecResponseError) as context:
            _parse_melsec_values("D0020", 2, raw, "01OK000G0014")

        message = str(context.exception)
        self.assertIn("addr=D0020", message)
        self.assertIn("count=2", message)
        self.assertIn("raw=b'01OK000G0014\\r\\n'", message)
        self.assertIn("chunk='000G'", message)
        self.assertIn("offset=0", message)

    def test_parse_melsec_values_raises_with_context_for_short_chunk(self) -> None:
        raw = b"01OK000A1\r\n"

        with self.assertRaises(MelsecResponseError) as context:
            _parse_melsec_values("D0020", 2, raw, "01OK000A1")

        message = str(context.exception)
        self.assertIn("addr=D0020", message)
        self.assertIn("count=2", message)
        self.assertIn("raw=b'01OK000A1\\r\\n'", message)
        self.assertIn("chunk='1'", message)
        self.assertIn("offset=4", message)


class SpotSnapshotTests(unittest.TestCase):
    def test_zero_cached_spot_temperature_replaces_previous_positive_snapshot(self) -> None:
        driver = RealPLCDriver()
        driver.last_spot = 45.5
        driver._update_spot_snapshot(45.5, 100.0)

        _, _, previous_spot = driver._read_cached_snapshot()
        self.assertEqual(previous_spot, 45.5)

        with patch("backend.FacilityData.drivers.real_plc.get_cached_spot_temp", return_value=0.0):
            spot_value = driver._read_spot()

        _, _, cached_spot = driver._read_cached_snapshot()

        self.assertEqual(spot_value, 0.0)
        self.assertEqual(driver.last_spot, 0.0)
        self.assertEqual(cached_spot, 0.0)


class RealPLCPositionReadFlagTests(unittest.TestCase):
    def _merged_read_fixture(self, calls: list[str]):
        def fake_read(addr: str, count: int, deadline: float) -> list[int]:
            calls.append(addr)
            if addr == "D0020":
                values = [0] * 16
                values[3] = 300
                values[11] = 410
                values[12] = 420
                return values
            if addr == "D0420":
                values = [0] * 6
                values[1] = 10150
                return values
            if addr == "D1500":
                values = [0] * 16
                values[10] = 7
                return values
            if addr == "D1900":
                values = [0] * 16
                values[11] = 650
                return values
            if addr == "B1502":
                return [45]
            if addr == "D0010":
                return [4970, 0, 116]
            return []

        return fake_read

    def test_position_read_disabled_does_not_read_d0010(self) -> None:
        driver = RealPLCDriver()
        calls: list[str] = []

        with patch("backend.FacilityData.drivers.real_plc.config.POSITION_READ_ENABLED", False):
            with patch.object(driver, "_melsec_read", side_effect=self._merged_read_fixture(calls)):
                data = driver._read_extruder_merged(9999999999.0)

        self.assertIsNotNone(data)
        assert data is not None
        self.assertNotIn("D0010", calls)
        self.assertNotIn("MainRamPosition_D0010", data)
        self.assertNotIn("ContainerPosition_D0012", data)

    def test_position_read_enabled_reads_d0010_and_maps_positions(self) -> None:
        driver = RealPLCDriver()
        calls: list[str] = []

        with patch("backend.FacilityData.drivers.real_plc.config.POSITION_READ_ENABLED", True):
            with patch.object(driver, "_melsec_read", side_effect=self._merged_read_fixture(calls)):
                data = driver._read_extruder_merged(9999999999.0)

        self.assertIsNotNone(data)
        assert data is not None
        self.assertIn("D0010", calls)
        self.assertEqual(data["MainRamPosition_D0010"], 497.0)
        self.assertEqual(data["ContainerPosition_D0012"], 11.6)


class OperatorMetadataApiTests(unittest.TestCase):
    TRUSTED_WRITE_HEADERS = {"origin": "http://localhost:3000", "host": "localhost:8000"}

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_path = backend_app.operator_metadata_store._path
        self.original_metadata = backend_app.operator_metadata_store.get()
        with backend_app.operator_metadata_store._lock:
            backend_app.operator_metadata_store._path = Path(self.temp_dir.name) / "operator_metadata.json"
            backend_app.operator_metadata_store._metadata = OperatorMetadata()

    def tearDown(self) -> None:
        with backend_app.operator_metadata_store._lock:
            backend_app.operator_metadata_store._path = self.original_path
            backend_app.operator_metadata_store._metadata = self.original_metadata
        self.temp_dir.cleanup()

    def test_get_returns_default_invalid_state(self) -> None:
        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            response = client.get("/api/facility/operator-metadata")
        finally:
            client.close()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["valid"])
        self.assertEqual(payload["missing_fields"], ["product_no", "operator_mold_no"])

    def test_put_persists_valid_operator_metadata(self) -> None:
        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            response = client.put(
                "/api/facility/operator-metadata",
                json={"product_no": "DW-50306", "operator_mold_no": "MOLD-01"},
                headers=self.TRUSTED_WRITE_HEADERS,
            )
        finally:
            client.close()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["product_no"], "DW-50306")
        self.assertEqual(payload["operator_mold_no"], "MOLD-01")
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["missing_fields"], [])
        self.assertTrue(backend_app.operator_metadata_store._path.exists())

    def test_put_rejects_untrusted_origin(self) -> None:
        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            response = client.put(
                "/api/facility/operator-metadata",
                json={"product_no": "DW-50306", "operator_mold_no": "MOLD-01"},
                headers={"origin": "https://example.invalid", "host": "localhost:8000"},
            )
        finally:
            client.close()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(backend_app.operator_metadata_store.get().product_no, "")

    def test_put_rejects_csv_formula_prefix(self) -> None:
        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            response = client.put(
                "/api/facility/operator-metadata",
                json={"product_no": "DW-50306", "operator_mold_no": "=cmd"},
            )
        finally:
            client.close()

        self.assertEqual(response.status_code, 422)
        self.assertEqual(backend_app.operator_metadata_store.get().operator_mold_no, "")

    def test_put_rejects_missing_required_fields(self) -> None:
        client = TestClient(backend_app.app, raise_server_exceptions=False)
        try:
            response = client.put(
                "/api/facility/operator-metadata",
                json={"product_no": "DW-50306", "operator_mold_no": ""},
            )
        finally:
            client.close()

        self.assertEqual(response.status_code, 422)
        self.assertFalse(backend_app.operator_metadata_store.get().valid)

    def test_store_keeps_existing_memory_state_when_persist_fails(self) -> None:
        existing_metadata = OperatorMetadata(
            product_no="DW-OLD",
            operator_mold_no="MOLD-OLD",
            updated_at="2026-03-09T07:20:20Z",
        )
        with backend_app.operator_metadata_store._lock:
            backend_app.operator_metadata_store._metadata = existing_metadata

        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                backend_app.operator_metadata_store.update(
                    OperatorMetadataUpdate(product_no="DW-NEW", operator_mold_no="MOLD-NEW")
                )

        current_metadata = backend_app.operator_metadata_store.get()
        self.assertEqual(current_metadata.product_no, "DW-OLD")
        self.assertEqual(current_metadata.operator_mold_no, "MOLD-OLD")

    def test_compose_data_attaches_current_operator_metadata(self) -> None:
        backend_app.operator_metadata_store.update(
            OperatorMetadataUpdate(product_no="DW-50306", operator_mold_no="MOLD-01")
        )
        raw_data = FactoryData(
            Time="2026-03-09T07:20:25.123",
            Status="Running",
            Speed=1.0,
            Press=2.0,
            Count=3,
            EndPos=4.0,
            Billet_Length=5.0,
            Spot=6.0,
            Temp_F=7.0,
            Temp_B=8.0,
            Billet_Temp=9.0,
            Mold1=10.0,
            Mold2=11.0,
            Mold3=12.0,
            Mold4=13.0,
            Mold5=14.0,
            Mold6=15.0,
            At_Temp=16.0,
            At_Pre=17.0,
        )

        composed = backend_app.plc_service._compose_data(raw_data)

        self.assertEqual(composed.Product_No_operator, "DW-50306")
        self.assertEqual(composed.Mold_No_operator, "MOLD-01")
        self.assertTrue(composed.operator_metadata_valid)
        self.assertEqual(composed.operator_metadata_missing_fields, [])
        self.assertIsNotNone(composed.operator_metadata_updated_at)


class CSVLoggerV2ContractTests(unittest.TestCase):
    def create_data(self, press_value: float | None = 30.0) -> FactoryData:
        return FactoryData(
            Time="2026-03-09T07:20:25.123",
            Status="Running",
            Press=press_value,
            Spot=100.0,
            Billet_Length=1.0,
            Temp_F=2.0,
            Temp_B=3.0,
            Count=1,
            Speed=4.0,
            EndPos=5.0,
            MainRamPosition_D0010=15.0,
            ContainerPosition_D0012=16.0,
            Mold1=6.0,
            Mold2=7.0,
            Mold3=8.0,
            Mold4=9.0,
            Mold5=10.0,
            Mold6=11.0,
            Billet_Temp=12.0,
            At_Pre=13.0,
            At_Temp=14.0,
            Die_ID="D1",
            Billet_Cycle_ID="C1",
            Product_No_operator="DW-50306",
            Mold_No_operator="MOLD-01",
            operator_metadata_valid=True,
            operator_metadata_missing_fields=[],
            operator_metadata_updated_at="2026-03-09T07:20:20Z",
            captured_at_extruder=1773040825.0,
            captured_at_ls=1773040825.0,
            captured_at_spot=1773040825.0,
        )

    def _read_csv_rows(self, path: Path) -> list[list[str]]:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.reader(handle))

    def _list_v1_files(self, log_dir: Path) -> list[Path]:
        return sorted(
            path for path in log_dir.glob("Factory_Integrated_Log_*.csv") if "_v2_" not in path.name
        )

    def _list_v2_files(self, log_dir: Path) -> list[Path]:
        return sorted(log_dir.glob("Factory_Integrated_Log_v2_*.csv"))

    def _run_logger_once(
        self,
        log_dir: Path,
        *,
        csv_v1_enabled: bool,
        csv_v2_enabled: bool,
    ) -> CSVLoggerService:
        service = CSVLoggerService()
        service.fallback_log_dir = log_dir
        service.apply_config(
            log_path=log_dir,
            auto_save=True,
            csv_v1_enabled=csv_v1_enabled,
            csv_v2_enabled=csv_v2_enabled,
        )
        service.start()
        try:
            service.enqueue(self.create_data())
            service.stop()
        finally:
            if service.running:
                service.stop()
        return service

    def test_v1_golden_row_contract_is_stable(self) -> None:
        service = CSVLoggerService()
        data = self.create_data()

        row = service._build_row(data, service._parse_timestamp(data))

        self.assertEqual(
            row,
            [
                "2026-03-09",
                "07:20:25.123",
                "100.0",
                "30.0",
                "1.0",
                "2.0",
                "3.0",
                "1",
                "4.0",
                "5.0",
                "6.0",
                "7.0",
                "8.0",
                "9.0",
                "10.0",
                "11.0",
                "12.0",
                "13.0",
                "14.0",
                "D1",
                "C1",
            ],
        )

    def test_header_mismatch_falls_back_to_v1_contract(self) -> None:
        service = CSVLoggerService()

        with self.assertLogs("SmartFactoryLoggerV2", level="WARNING") as logs:
            service.apply_config(csv_header="Date,Time,Temperature")

        self.assertEqual(service.csv_header, V1_CSV_COLUMNS)
        self.assertTrue(any("CSV header ignored" in message for message in logs.output))

    def test_header_position_mismatch_falls_back_to_v1_contract(self) -> None:
        service = CSVLoggerService()
        swapped_header = ",".join(
            [
                "Date",
                "Time",
                "Temperature",
                "MainPress",
                "BilletLength",
                "Temp_F",
                "Temp_B",
                "Count",
                "EndPos",
                "Speed",
                "Mold1",
                "Mold2",
                "Mold3",
                "Mold4",
                "Mold5",
                "Mold6",
                "Billet_Temp",
                "At_Pre",
                "At_Temp",
                "DIE_ID",
                "Billet_CycleID",
            ]
        )

        with self.assertLogs("SmartFactoryLoggerV2", level="WARNING") as logs:
            service.apply_config(csv_header=swapped_header)

        self.assertEqual(service.csv_header, V1_CSV_COLUMNS)
        self.assertTrue(any("label does not match v1 position contract" in message for message in logs.output))

    def test_known_legacy_header_aliases_are_accepted_by_position(self) -> None:
        service = CSVLoggerService()
        legacy_header = ",".join(
            [
                "Date",
                "Time",
                "Temperature",
                "메인압력",
                "빌렛길이",
                "콘테이너온도 앞쪽",
                "콘테이너온도 뒷쪽",
                "생산카운터",
                "현재속도",
                "압출종료 위치",
                "Mold1",
                "Mold2",
                "Mold3",
                "Mold4",
                "Mold5",
                "Mold6",
                "Billet_Temp",
                "At_Pre",
                "At_Temp",
                "DIE_ID",
                "Billet_CycleID",
            ]
        )

        service.apply_config(csv_header=legacy_header)

        self.assertEqual(service.csv_header, legacy_header.split(","))

    def test_v2_row_marks_mainpress_missing_without_changing_v1_zero(self) -> None:
        service = CSVLoggerService()
        data = self.create_data(press_value=None)
        timestamp = service._parse_timestamp(data)
        v1_row = service._build_row(data, timestamp)

        v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

        self.assertEqual(v1_row[3], "0.0")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("MainPress_quality")], "missing")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("MainPress_missing_reason")], "source_missing")

    def test_v2_row_marks_billet_length_zero_as_idle_not_missing(self) -> None:
        service = CSVLoggerService()
        data = self.create_data().model_copy(update={"Billet_Length": 0.0})
        timestamp = service._parse_timestamp(data)
        v1_row = service._build_row(data, timestamp)

        v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

        self.assertEqual(v1_row[V1_CSV_COLUMNS.index("BilletLength")], "0.0")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("BilletLength_quality")], "idle")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("BilletLength_missing_reason")], "not_missing")

    def test_v2_row_marks_positive_billet_length_as_ok(self) -> None:
        service = CSVLoggerService()
        data = self.create_data().model_copy(update={"Billet_Length": 650.0})
        timestamp = service._parse_timestamp(data)
        v1_row = service._build_row(data, timestamp)

        v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

        self.assertEqual(v1_row[V1_CSV_COLUMNS.index("BilletLength")], "650.0")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("BilletLength_quality")], "ok")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("BilletLength_missing_reason")], "not_missing")

    def test_v2_row_includes_actual_position_fields_without_changing_v1(self) -> None:
        service = CSVLoggerService()
        data = self.create_data()
        timestamp = service._parse_timestamp(data)
        v1_row = service._build_row(data, timestamp)

        v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

        self.assertNotIn("MainRamPosition_D0010", V1_CSV_COLUMNS)
        self.assertNotIn("ContainerPosition_D0012", V1_CSV_COLUMNS)
        self.assertEqual(len(v1_row), 21)
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("MainRamPosition_D0010")], "15.0")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("ContainerPosition_D0012")], "16.0")

    def test_v2_row_includes_operator_metadata_without_changing_v1(self) -> None:
        service = CSVLoggerService()
        data = self.create_data()
        timestamp = service._parse_timestamp(data)
        v1_row = service._build_row(data, timestamp)

        v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

        self.assertNotIn("Product_No_operator", V1_CSV_COLUMNS)
        self.assertNotIn("Mold_No_operator", V1_CSV_COLUMNS)
        self.assertEqual(len(v1_row), 21)
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("Product_No_operator")], "DW-50306")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("Mold_No_operator")], "MOLD-01")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("operator_metadata_valid")], "true")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("operator_metadata_missing_fields")], "")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("operator_metadata_updated_at")], "2026-03-09T07:20:20Z")

    def test_v2_row_records_missing_operator_metadata_as_invalid(self) -> None:
        service = CSVLoggerService()
        data = self.create_data().model_copy(update={
            "Product_No_operator": "",
            "Mold_No_operator": "",
            "operator_metadata_valid": False,
            "operator_metadata_missing_fields": ["product_no", "operator_mold_no"],
            "operator_metadata_updated_at": None,
        })
        timestamp = service._parse_timestamp(data)
        v1_row = service._build_row(data, timestamp)

        v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("operator_metadata_valid")], "false")
        self.assertEqual(
            v2_row[V2_CSV_COLUMNS.index("operator_metadata_missing_fields")],
            "product_no,operator_mold_no",
        )

    def test_csv_injection_escapes_string_fields(self) -> None:
        service = CSVLoggerService()
        data = self.create_data().model_copy(update={
            "Die_ID": "=cmd",
            "Billet_Cycle_ID": "+cycle",
            "Product_No_operator": "@product",
            "Mold_No_operator": "-mold",
        })
        timestamp = service._parse_timestamp(data)

        row = service._build_row(data, timestamp)
        v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, row)

        self.assertEqual(row[19], "'=cmd")
        self.assertEqual(row[20], "'+cycle")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("Product_No_operator")], "'@product")
        self.assertEqual(v2_row[V2_CSV_COLUMNS.index("Mold_No_operator")], "'-mold")

    def test_csv_writer_mode_v1_enabled_v2_disabled_creates_v1_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            self._run_logger_once(log_dir, csv_v1_enabled=True, csv_v2_enabled=False)

            self.assertEqual(len(self._list_v1_files(log_dir)), 1)
            self.assertEqual(self._list_v2_files(log_dir), [])

    def test_csv_writer_mode_v1_enabled_v2_enabled_creates_both_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            self._run_logger_once(log_dir, csv_v1_enabled=True, csv_v2_enabled=True)

            self.assertEqual(len(self._list_v1_files(log_dir)), 1)
            v2_files = self._list_v2_files(log_dir)
            self.assertEqual(len(v2_files), 1)
            metadata = json.loads(v2_files[0].with_suffix(".metadata.json").read_text(encoding="utf-8"))
            self.assertTrue(metadata["schema_metadata"]["v1_csv_enabled"])

    def test_csv_writer_mode_v1_disabled_v2_enabled_creates_v2_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            self._run_logger_once(log_dir, csv_v1_enabled=False, csv_v2_enabled=True)

            self.assertEqual(self._list_v1_files(log_dir), [])
            v2_files = self._list_v2_files(log_dir)
            self.assertEqual(len(v2_files), 1)
            rows = self._read_csv_rows(v2_files[0])
            self.assertEqual(rows[0], V2_CSV_COLUMNS)
            self.assertEqual(len(rows), 2)
            metadata = json.loads(v2_files[0].with_suffix(".metadata.json").read_text(encoding="utf-8"))
            self.assertFalse(metadata["schema_metadata"]["v1_csv_enabled"])

    def test_csv_writer_mode_v1_disabled_v2_disabled_falls_back_to_v1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            with self.assertLogs("SmartFactoryLoggerV2", level="WARNING") as logs:
                service = self._run_logger_once(log_dir, csv_v1_enabled=False, csv_v2_enabled=False)

            self.assertTrue(service.csv_v1_enabled)
            self.assertTrue(any("cannot disable both v1 and v2 writers" in message for message in logs.output))
            self.assertEqual(len(self._list_v1_files(log_dir)), 1)
            self.assertEqual(self._list_v2_files(log_dir), [])

    def test_hot_reload_to_v2_only_flushes_pending_v1_buffer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(
                log_path=log_dir,
                auto_save=True,
                csv_v1_enabled=True,
                csv_v2_enabled=False,
            )
            service.start()
            try:
                service.enqueue(self.create_data())
                deadline = time.time() + 2.0
                while service._buffer_size < 1 and time.time() < deadline:
                    time.sleep(0.01)
                self.assertEqual(service._buffer_size, 1)

                service.apply_config(csv_v1_enabled=False, csv_v2_enabled=True)

                deadline = time.time() + 2.0
                while service._buffer_size != 0 and time.time() < deadline:
                    time.sleep(0.01)
            finally:
                service.stop()

            v1_files = self._list_v1_files(log_dir)
            self.assertEqual(len(v1_files), 1)
            rows = self._read_csv_rows(v1_files[0])
            self.assertEqual(rows[0], V1_CSV_COLUMNS)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[1][V1_CSV_COLUMNS.index("Time")], "07:20:25.123")

    def test_csv_writer_rolls_over_v1_v2_and_sidecar_at_midnight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(
                log_path=log_dir,
                auto_save=True,
                csv_v1_enabled=True,
                csv_v2_enabled=True,
            )
            service.start()
            try:
                service.enqueue(self.create_data().model_copy(update={"Time": "2026-03-09T23:59:59.900"}))
                service.enqueue(self.create_data().model_copy(update={"Time": "2026-03-10T00:00:00.100"}))
                time.sleep(1.2)
            finally:
                service.stop()

            v1_files = self._list_v1_files(log_dir)
            v2_files = self._list_v2_files(log_dir)
            self.assertEqual(
                [path.name for path in v1_files],
                [
                    "Factory_Integrated_Log_20260309_235959.csv",
                    "Factory_Integrated_Log_20260310_000000.csv",
                ],
            )
            self.assertEqual(
                [path.name for path in v2_files],
                [
                    "Factory_Integrated_Log_v2_20260309_235959.csv",
                    "Factory_Integrated_Log_v2_20260310_000000.csv",
                ],
            )
            self.assertTrue(v2_files[0].with_suffix(".metadata.json").exists())
            self.assertTrue(v2_files[1].with_suffix(".metadata.json").exists())

            first_v2_rows = self._read_csv_rows(v2_files[0])
            second_v2_rows = self._read_csv_rows(v2_files[1])
            sample_seq_index = V2_CSV_COLUMNS.index("sample_seq")
            date_index = V2_CSV_COLUMNS.index("Date")
            self.assertEqual(first_v2_rows[1][sample_seq_index], "1")
            self.assertEqual(second_v2_rows[1][sample_seq_index], "2")
            self.assertEqual(first_v2_rows[1][date_index], "2026-03-09")
            self.assertEqual(second_v2_rows[1][date_index], "2026-03-10")

    def test_csv_rollover_defers_new_day_row_until_previous_day_flush_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(
                log_path=log_dir,
                auto_save=True,
                csv_v1_enabled=True,
                csv_v2_enabled=True,
            )
            original_flush = service._flush_buffer
            injected_failure = {"remaining": 1}

            def fail_previous_day_flush_once(writer, handle, buffer):
                rows = list(buffer)
                if injected_failure["remaining"] and rows and rows[0][1].date().isoformat() == "2026-03-09":
                    injected_failure["remaining"] = 0
                    return False
                return original_flush(writer, handle, rows)

            with patch.object(service, "_flush_buffer", side_effect=fail_previous_day_flush_once):
                service.start()
                try:
                    service.enqueue(self.create_data().model_copy(update={"Time": "2026-03-09T23:59:59.900"}))
                    deadline = time.time() + 2.0
                    while service._buffer_size < 1 and time.time() < deadline:
                        time.sleep(0.01)

                    service.enqueue(self.create_data().model_copy(update={"Time": "2026-03-10T00:00:00.100"}))
                    deadline = time.time() + 3.0
                    while len(self._list_v1_files(log_dir)) < 2 and time.time() < deadline:
                        time.sleep(0.01)
                finally:
                    service.stop()

            self.assertEqual(injected_failure["remaining"], 0)
            v1_files = self._list_v1_files(log_dir)
            v2_files = self._list_v2_files(log_dir)
            self.assertEqual(
                [path.name for path in v1_files],
                [
                    "Factory_Integrated_Log_20260309_235959.csv",
                    "Factory_Integrated_Log_20260310_000000.csv",
                ],
            )
            self.assertEqual(
                [path.name for path in v2_files],
                [
                    "Factory_Integrated_Log_v2_20260309_235959.csv",
                    "Factory_Integrated_Log_v2_20260310_000000.csv",
                ],
            )
            self.assertEqual([self._read_csv_rows(path)[1][0] for path in v1_files], ["2026-03-09", "2026-03-10"])
            self.assertEqual([self._read_csv_rows(path)[1][V1_CSV_COLUMNS.index("Time")] for path in v1_files], [
                "23:59:59.900",
                "00:00:00.100",
            ])
            self.assertTrue(v2_files[0].with_suffix(".metadata.json").exists())
            self.assertTrue(v2_files[1].with_suffix(".metadata.json").exists())

    def test_csv_rollover_defers_new_day_row_when_previous_day_flush_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(
                log_path=log_dir,
                auto_save=True,
                csv_v1_enabled=True,
                csv_v2_enabled=True,
            )
            original_flush = service._flush_buffer
            injected_failure = {"remaining": 1}

            def raise_previous_day_flush_once(writer, handle, buffer):
                rows = list(buffer)
                if injected_failure["remaining"] and rows and rows[0][1].date().isoformat() == "2026-03-09":
                    injected_failure["remaining"] = 0
                    raise OSError("simulated flush failure")
                return original_flush(writer, handle, rows)

            with patch.object(service, "_flush_buffer", side_effect=raise_previous_day_flush_once):
                service.start()
                try:
                    service.enqueue(self.create_data().model_copy(update={"Time": "2026-03-09T23:59:59.900"}))
                    deadline = time.time() + 2.0
                    while service._buffer_size < 1 and time.time() < deadline:
                        time.sleep(0.01)

                    service.enqueue(self.create_data().model_copy(update={"Time": "2026-03-10T00:00:00.100"}))
                    deadline = time.time() + 4.0
                    while len(self._list_v1_files(log_dir)) < 2 and time.time() < deadline:
                        time.sleep(0.01)
                finally:
                    service.stop()

            self.assertEqual(injected_failure["remaining"], 0)
            v1_files = self._list_v1_files(log_dir)
            v2_files = self._list_v2_files(log_dir)
            self.assertEqual(
                [path.name for path in v1_files],
                [
                    "Factory_Integrated_Log_20260309_235959.csv",
                    "Factory_Integrated_Log_20260310_000000.csv",
                ],
            )
            self.assertEqual(
                [path.name for path in v2_files],
                [
                    "Factory_Integrated_Log_v2_20260309_235959.csv",
                    "Factory_Integrated_Log_v2_20260310_000000.csv",
                ],
            )
            self.assertEqual([self._read_csv_rows(path)[1][0] for path in v1_files], ["2026-03-09", "2026-03-10"])
            self.assertEqual([self._read_csv_rows(path)[1][V1_CSV_COLUMNS.index("Time")] for path in v1_files], [
                "23:59:59.900",
                "00:00:00.100",
            ])
            self.assertTrue(v2_files[0].with_suffix(".metadata.json").exists())
            self.assertTrue(v2_files[1].with_suffix(".metadata.json").exists())

    def test_csv_shutdown_writes_deferred_new_day_row_after_final_flush_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(
                log_path=log_dir,
                auto_save=True,
                csv_v1_enabled=True,
                csv_v2_enabled=True,
            )
            original_flush = service._flush_buffer
            injected_failure = {"remaining": 1}

            def fail_previous_day_flush_and_stop_once(writer, handle, buffer):
                rows = list(buffer)
                if injected_failure["remaining"] and rows and rows[0][1].date().isoformat() == "2026-03-09":
                    injected_failure["remaining"] = 0
                    service.running = False
                    return False
                return original_flush(writer, handle, rows)

            with patch.object(service, "_flush_buffer", side_effect=fail_previous_day_flush_and_stop_once):
                service.start()
                service.enqueue(self.create_data().model_copy(update={"Time": "2026-03-09T23:59:59.900"}))
                deadline = time.time() + 2.0
                while service._buffer_size < 1 and time.time() < deadline:
                    time.sleep(0.01)

                service.enqueue(self.create_data().model_copy(update={"Time": "2026-03-10T00:00:00.100"}))
                if service.thread:
                    service.thread.join(timeout=3.0)
                if service.running:
                    service.stop()

            self.assertEqual(injected_failure["remaining"], 0)
            self.assertFalse(service.thread and service.thread.is_alive())
            v1_files = self._list_v1_files(log_dir)
            v2_files = self._list_v2_files(log_dir)
            self.assertEqual(
                [path.name for path in v1_files],
                [
                    "Factory_Integrated_Log_20260309_235959.csv",
                    "Factory_Integrated_Log_20260310_000000.csv",
                ],
            )
            self.assertEqual(
                [path.name for path in v2_files],
                [
                    "Factory_Integrated_Log_v2_20260309_235959.csv",
                    "Factory_Integrated_Log_v2_20260310_000000.csv",
                ],
            )
            self.assertEqual([self._read_csv_rows(path)[1][0] for path in v1_files], ["2026-03-09", "2026-03-10"])
            self.assertEqual([self._read_csv_rows(path)[1][V1_CSV_COLUMNS.index("Time")] for path in v1_files], [
                "23:59:59.900",
                "00:00:00.100",
            ])
            self.assertTrue(v2_files[0].with_suffix(".metadata.json").exists())
            self.assertTrue(v2_files[1].with_suffix(".metadata.json").exists())

    def test_v2_writer_creates_separate_file_and_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(log_path=log_dir, auto_save=True, csv_v2_enabled=True)
            timestamp = service._parse_timestamp(self.create_data())

            handle, writer = service._open_v2_log_file(timestamp.strftime("%Y%m%d_%H%M%S"), "Factory_Integrated_Log_v2")
            try:
                self.assertIsNotNone(handle)
                self.assertIsNotNone(writer)
            finally:
                service._close_file(handle)

            v2_files = sorted(log_dir.glob("Factory_Integrated_Log_v2_*.csv"))
            self.assertEqual(len(v2_files), 1)
            with v2_files[0].open("r", encoding="utf-8-sig", newline="") as csv_handle:
                rows = list(csv.reader(csv_handle))
            self.assertEqual(rows[0], V2_CSV_COLUMNS)
            self.assertNotIn("ButtLength_HMI_B1880", V2_CSV_COLUMNS)

            metadata = json.loads(v2_files[0].with_suffix(".metadata.json").read_text(encoding="utf-8"))
            self.assertIn("position-specific label", metadata["schema_metadata"]["header_policy"])
            self.assertEqual(metadata["schema_metadata"]["schema_version"], "2.2.0")
            self.assertEqual(metadata["schema_metadata"]["operator_metadata_version"], "1.0.0")
            self.assertEqual(
                metadata["schema_metadata"]["position_read_feature_flag"],
                "EXTRUDER.position_read_enabled or POSITION_READ_ENABLED",
            )
            self.assertIn("메인압력", metadata["schema_metadata"]["v1_header_aliases"]["MainPress"])
            self.assertIn("압출종료 위치", metadata["schema_metadata"]["v1_header_aliases"]["EndPos"])

            billet_meta = [
                item for item in metadata["sensor_metadata"] if item.get("column_name") == "BilletLength"
            ][0]
            self.assertEqual(billet_meta["field_name"], "BilletLength")
            self.assertEqual(billet_meta["source_address"], "D1911")
            self.assertEqual(billet_meta["mapping_status"], "hmi_confirmed")
            self.assertIn("B1880 Float32 LH matches the separate HMI Butt Length", billet_meta["note"])

            butt_meta = [
                item for item in metadata["sensor_metadata"] if item["field_name"] == "ButtLength_HMI_B1880"
            ][0]
            self.assertEqual(butt_meta["physical_meaning"], "HMI 버트 길이")
            self.assertEqual(butt_meta["source_address"], "B1880")
            self.assertEqual(butt_meta["data_type"], "Float32")
            self.assertEqual(butt_meta["word_order"], "LH")
            self.assertEqual(butt_meta["mapping_status"], "hmi_confirmed_separate_field")
            self.assertEqual(butt_meta["semantic_group"], "butt_length")
            self.assertEqual(butt_meta["not_replacement_for"], "BilletLength")
            self.assertEqual(butt_meta["related_v1_field"], "BilletLength")
            self.assertEqual(butt_meta["quality_rule"]["range_10_to_200"], "ok")
            self.assertEqual(butt_meta["quality_rule"]["less_than_or_equal_zero"], "invalid_candidate")
            self.assertIn("must not be treated as v1 BilletLength replacement", butt_meta["notes"])

            endpos_meta = [
                item for item in metadata["sensor_metadata"] if item.get("column_name") == "EndPos"
            ][0]
            self.assertEqual(endpos_meta["mapping_status"], "hmi_confirmed_setting_value")
            self.assertIn("D0010 / 10.0 is the real-time main ram position", endpos_meta["note"])
            self.assertIn("not the moving actual position", endpos_meta["note"])

            main_ram_meta = [
                item for item in metadata["sensor_metadata"] if item.get("column_name") == "MainRamPosition_D0010"
            ][0]
            self.assertEqual(main_ram_meta["source_address"], "D0010")
            self.assertEqual(main_ram_meta["plc_address"], "D0010 / 10.0")
            self.assertEqual(main_ram_meta["unit"], "mm")
            self.assertEqual(main_ram_meta["mapping_status"], "hmi_confirmed_actual_position")
            self.assertEqual(main_ram_meta["semantic_group"], "position")
            self.assertEqual(main_ram_meta["read_feature_flag"], "POSITION_READ_ENABLED")

            container_meta = [
                item for item in metadata["sensor_metadata"] if item.get("column_name") == "ContainerPosition_D0012"
            ][0]
            self.assertEqual(container_meta["source_address"], "D0012")
            self.assertEqual(container_meta["plc_address"], "D0012 / 10.0")
            self.assertEqual(container_meta["unit"], "mm")
            self.assertEqual(container_meta["mapping_status"], "hmi_confirmed_actual_position")
            self.assertEqual(container_meta["semantic_group"], "position")
            self.assertEqual(container_meta["read_feature_flag"], "POSITION_READ_ENABLED")

            product_meta = [
                item for item in metadata["sensor_metadata"] if item.get("column_name") == "Product_No_operator"
            ][0]
            self.assertEqual(product_meta["field_name"], "product_no")
            self.assertEqual(product_meta["source_system"], "Operator input")
            self.assertEqual(product_meta["mapping_status"], "operator_entered_required")
            self.assertEqual(product_meta["not_replacement_for"], "%DW PLC address")

            mold_no_meta = [
                item for item in metadata["sensor_metadata"] if item.get("column_name") == "Mold_No_operator"
            ][0]
            self.assertEqual(mold_no_meta["field_name"], "operator_mold_no")
            self.assertEqual(mold_no_meta["mapping_status"], "operator_entered_required")
            self.assertEqual(mold_no_meta["not_replacement_for"], "DIE_ID")

            self.assertIn(
                "hmi_confirmed_actual_position",
                metadata["quality_rule_metadata"]["mapping_status_values"],
            )
            self.assertIn(
                "hmi_confirmed_separate_field",
                metadata["quality_rule_metadata"]["mapping_status_values"],
            )
            self.assertIn(
                "operator_entered_required",
                metadata["quality_rule_metadata"]["mapping_status_values"],
            )
            self.assertEqual(
                metadata["operator_metadata"]["required_fields"],
                ["product_no", "operator_mold_no"],
            )

    def test_shadow_validation_script_accepts_v1_v2_sidecar_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(log_path=log_dir, auto_save=True, csv_v2_enabled=True)
            data = self.create_data()
            timestamp = service._parse_timestamp(data)
            v1_row = service._build_row(data, timestamp)
            v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

            v1_path = log_dir / "Factory_Integrated_Log_20260309_072025.csv"
            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_072025.csv"

            with v1_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(V1_CSV_COLUMNS)
                writer.writerow(v1_row)
            with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(V2_CSV_COLUMNS)
                writer.writerow(v2_row)
            service._write_v2_sidecar(v2_path)

            result = validate_csv_v2_shadow(v1_path, v2_path, v2_path.with_suffix(".metadata.json"))

        self.assertEqual(result, 0)

    def test_shadow_validation_script_accepts_legacy_2_1_v2_sidecar_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(log_path=log_dir, auto_save=True, csv_v2_enabled=True)
            data = self.create_data()
            timestamp = service._parse_timestamp(data)
            v1_row = service._build_row(data, timestamp)
            v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)
            operator_columns = {
                "Product_No_operator",
                "Mold_No_operator",
                "operator_metadata_valid",
                "operator_metadata_missing_fields",
                "operator_metadata_updated_at",
            }
            legacy_columns = [column for column in V2_CSV_COLUMNS if column not in operator_columns]
            legacy_row = [
                value for column, value in zip(V2_CSV_COLUMNS, v2_row) if column not in operator_columns
            ]
            legacy_row[legacy_columns.index("schema_version")] = "2.1.0"
            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_072025.csv"
            metadata_path = v2_path.with_suffix(".metadata.json")

            with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(legacy_columns)
                writer.writerow(legacy_row)
            metadata_path.write_text(
                json.dumps(
                    {
                        "schema_metadata": {"schema_version": "2.1.0"},
                        "sensor_metadata": [
                            {
                                "field_name": "EndPos",
                                "mapping_status": "hmi_confirmed_setting_value",
                            },
                            {
                                "field_name": "MainRamPosition_D0010",
                                "mapping_status": "hmi_confirmed_actual_position",
                            },
                            {
                                "field_name": "ContainerPosition_D0012",
                                "mapping_status": "hmi_confirmed_actual_position",
                            },
                            {
                                "field_name": "ButtLength_HMI_B1880",
                                "mapping_status": "hmi_confirmed_separate_field",
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = validate_csv_v2_shadow(None, v2_path, metadata_path)

        self.assertEqual(result, 0)

    def test_shadow_validation_script_accepts_v2_only_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(log_path=log_dir, auto_save=True, csv_v1_enabled=False, csv_v2_enabled=True)
            data = self.create_data()
            timestamp = service._parse_timestamp(data)
            v1_row = service._build_row(data, timestamp)
            v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)

            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_072025.csv"

            with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(V2_CSV_COLUMNS)
                writer.writerow(v2_row)
            service._write_v2_sidecar(v2_path)

            result = validate_csv_v2_shadow(None, v2_path, v2_path.with_suffix(".metadata.json"))

        self.assertEqual(result, 0)

    def test_shadow_validation_script_accepts_daily_rollover_file_sets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(log_path=log_dir, auto_save=True, csv_v2_enabled=True)

            file_specs = [
                ("20260309_235959", "2026-03-09T23:59:59.900", 1),
                ("20260310_000000", "2026-03-10T00:00:00.100", 2),
            ]
            v1_paths = []
            v2_paths = []
            metadata_paths = []
            for suffix, timestamp_s, sample_seq in file_specs:
                data = self.create_data().model_copy(update={"Time": timestamp_s})
                timestamp = service._parse_timestamp(data)
                v1_row = service._build_row(data, timestamp)
                v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), sample_seq, v1_row)
                v1_path = log_dir / f"Factory_Integrated_Log_{suffix}.csv"
                v2_path = log_dir / f"Factory_Integrated_Log_v2_{suffix}.csv"

                with v1_path.open("w", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(V1_CSV_COLUMNS)
                    writer.writerow(v1_row)
                with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(V2_CSV_COLUMNS)
                    writer.writerow(v2_row)
                service._write_v2_sidecar(v2_path)
                v1_paths.append(v1_path)
                v2_paths.append(v2_path)
                metadata_paths.append(v2_path.with_suffix(".metadata.json"))

            result = validate_csv_v2_shadow_many(
                list(reversed(v1_paths)),
                list(reversed(v2_paths)),
                list(reversed(metadata_paths)),
            )

        self.assertEqual(result, 0)

    def test_shadow_validation_script_fails_when_required_v1_glob_has_no_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            service = CSVLoggerService()
            service.fallback_log_dir = log_dir
            service.apply_config(log_path=log_dir, auto_save=True, csv_v2_enabled=True)
            data = self.create_data()
            timestamp = service._parse_timestamp(data)
            v1_row = service._build_row(data, timestamp)
            v2_row = service._build_v2_row(data, timestamp, timestamp.astimezone(), 1, v1_row)
            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_072025.csv"

            with v2_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(V2_CSV_COLUMNS)
                writer.writerow(v2_row)
            service._write_v2_sidecar(v2_path)

            result = validate_csv_v2_shadow_many(
                [],
                [v2_path],
                [v2_path.with_suffix(".metadata.json")],
                require_v1=True,
            )

        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
