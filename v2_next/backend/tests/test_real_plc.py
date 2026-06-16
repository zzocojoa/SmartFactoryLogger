import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.FacilityData.drivers.real_plc import MelsecResponseError, RealPLCDriver, _parse_melsec_values
from backend.FacilityData.repository import CSVLoggerService, V1_CSV_COLUMNS, V2_CSV_COLUMNS
from backend.FacilityData.schemas import FactoryData
from scripts.validate_csv_v2_shadow import validate as validate_csv_v2_shadow


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
            captured_at_extruder=1773040825.0,
            captured_at_ls=1773040825.0,
            captured_at_spot=1773040825.0,
        )

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

    def test_csv_injection_escapes_string_fields(self) -> None:
        service = CSVLoggerService()
        data = self.create_data().model_copy(update={"Die_ID": "=cmd", "Billet_Cycle_ID": "+cycle"})

        row = service._build_row(data, service._parse_timestamp(data))

        self.assertEqual(row[19], "'=cmd")
        self.assertEqual(row[20], "'+cycle")

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

            self.assertIn(
                "hmi_confirmed_actual_position",
                metadata["quality_rule_metadata"]["mapping_status_values"],
            )
            self.assertIn(
                "hmi_confirmed_separate_field",
                metadata["quality_rule_metadata"]["mapping_status_values"],
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


if __name__ == "__main__":
    unittest.main()
