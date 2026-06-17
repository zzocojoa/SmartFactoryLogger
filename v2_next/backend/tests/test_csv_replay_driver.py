import csv
import os
import tempfile
import unittest
from pathlib import Path

from backend.FacilityData.drivers.csv_replay import CsvReplayDriver
from backend.FacilityData.repository import V1_CSV_COLUMNS, V2_CSV_COLUMNS


class CsvReplayDriverTests(unittest.TestCase):
    def _write_v1_csv(self, path: Path, count: int, speed: float = 1.0) -> None:
        row = [
            "2026-03-09",
            "07:20:25.123",
            "450.0",
            "120.0",
            "650.0",
            "30.0",
            "31.0",
            str(count),
            str(speed),
            "10.0",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "500.0",
            "1.0",
            "20.0",
            "DIE-1",
            "CYCLE-1",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(V1_CSV_COLUMNS)
            writer.writerow(row)

    def _write_v2_csv(self, path: Path, count: int) -> None:
        v1_row = [
            "2026-03-09",
            "07:20:25.123",
            "450.0",
            "120.0",
            "650.0",
            "30.0",
            "31.0",
            str(count),
            "1.0",
            "10.0",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "500.0",
            "1.0",
            "20.0",
            "DIE-1",
            "CYCLE-1",
        ]
        v2_row = [
            "2.2.0",
            str(count),
            "2026-03-09T07:20:25.123+09:00",
            "2026-03-08T22:20:25.123Z",
            "2026-03-09T07:20:25.123+09:00",
            "",
            "",
            "",
            "12345",
            "123",
            "true",
            "",
            "2026-03-09T07:20:20Z",
            *v1_row,
            "",
            "",
            "ok",
            "not_missing",
            "bar",
            "ok",
            "not_missing",
            "degC",
            "ok",
            "not_missing",
            "mm/s",
            "ok",
            "not_missing",
            "mm",
            "true",
            "true",
            "cycle-heuristic-v1",
            "0.0",
            "unknown",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(V2_CSV_COLUMNS)
            writer.writerow(v2_row)

    def test_replay_loads_directory_daily_v1_files_in_timestamp_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            first = log_dir / "Factory_Integrated_Log_20260309_235959.csv"
            second = log_dir / "Factory_Integrated_Log_20260310_000000.csv"
            self._write_v1_csv(second, 2)
            self._write_v1_csv(first, 1)

            cwd = Path.cwd()
            os.chdir(log_dir)
            try:
                driver = CsvReplayDriver(str(log_dir))
            finally:
                os.chdir(cwd)

            self.assertTrue(driver.connect())
            self.assertEqual(driver.read_data().Count, 1)
            self.assertEqual(driver.read_data().Count, 2)

    def test_replay_rejects_mixed_v1_and_v2_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            v1_path = log_dir / "Factory_Integrated_Log_20260309_235959.csv"
            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_235959.csv"
            self._write_v1_csv(v1_path, 1)
            self._write_v2_csv(v2_path, 1)

            driver = CsvReplayDriver(f"{v1_path}{os.pathsep}{v2_path}")

            self.assertEqual(driver.rows, [])
            self.assertFalse(driver.connect())

    def test_replay_maps_v2_operator_metadata_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            v2_path = log_dir / "Factory_Integrated_Log_v2_20260309_235959.csv"
            self._write_v2_csv(v2_path, 1)

            cwd = Path.cwd()
            os.chdir(log_dir)
            try:
                driver = CsvReplayDriver(str(v2_path))
            finally:
                os.chdir(cwd)

            self.assertTrue(driver.connect())
            data = driver.read_data()
            self.assertEqual(data.Product_No_operator, "12345")
            self.assertEqual(data.Mold_No_operator, "123")
            self.assertTrue(data.operator_metadata_valid)
            self.assertEqual(data.operator_metadata_missing_fields, [])
            self.assertEqual(data.operator_metadata_updated_at, "2026-03-09T07:20:20Z")


if __name__ == "__main__":
    unittest.main()
