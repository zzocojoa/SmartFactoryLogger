import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_TEST_ROOT = Path(__file__).resolve().parents[2]
_TEST_APPDATA_ROOT = _TEST_ROOT / ".tmp_test_appdata"
_TEST_CONFIG_PATH = _TEST_APPDATA_ROOT / "config.ini"

os.environ.setdefault("APPDATA", str(_TEST_APPDATA_ROOT))
os.environ.setdefault("SFL_CONFIG_PATH", str(_TEST_CONFIG_PATH))


class ConfigurationServiceTests(unittest.TestCase):
    def test_update_config_refreshes_derived_spot_actuator_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.ini"
            config_path.write_text(
                "\n".join(
                    [
                        "[SPOT]",
                        "ip = 10.1.10.50",
                        "actuatorip = 10.1.10.60",
                        "actuatorurl = http://10.1.10.60/scan.cgi",
                        "",
                    ]
                ),
                encoding="utf-8-sig",
            )

            from backend.Configuration import service
            from backend.Configuration.Configuration_Structure import ConfigUpdate

            original_config_path = service.config.CONFIG_PATH
            original_allow_local_config = service.os.environ.get("SFL_ALLOW_LOCAL_CONFIG")
            service.config.CONFIG_PATH = config_path
            service.os.environ["SFL_ALLOW_LOCAL_CONFIG"] = "1"
            try:
                with mock.patch.object(service.config_meta, "record_local_update", return_value={}):
                    with mock.patch.object(service.config_manager, "reload", return_value={}):
                        with mock.patch.object(service.config_manager, "apply_changes", return_value={}):
                            service.update_config(ConfigUpdate(spot={"actuator_ip": "10.1.10.70"}), source="local")
                service.clear_snapshot_cache()
                snapshot = service.get_config_snapshot()
            finally:
                service.clear_snapshot_cache()
                service.config.CONFIG_PATH = original_config_path
                if original_allow_local_config is None:
                    service.os.environ.pop("SFL_ALLOW_LOCAL_CONFIG", None)
                else:
                    service.os.environ["SFL_ALLOW_LOCAL_CONFIG"] = original_allow_local_config

            spot = snapshot["values"]["spot"]
            self.assertEqual(spot["actuator_ip"], "10.1.10.70")
            self.assertEqual(spot["actuator_url"], "http://10.1.10.70/scan.cgi")

    def test_config_snapshot_includes_spot_actuator_step(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.ini"
            config_path.write_text(
                "\n".join(
                    [
                        "[SYSTEM]",
                        "intervalsec = 0.2",
                        "",
                        "[EXTRUDER]",
                        "ip = 192.168.10.10",
                        "port = 12289",
                        "",
                        "[SPOT]",
                        "ip = 10.1.10.50",
                        "refreshinterval = 1.0",
                        "imageurl = http://10.1.10.50/image.jpg",
                        "focusurl = http://10.1.10.50/control?p=focus",
                        "focusstep = 200",
                        "actuatorip = 10.1.10.60",
                        "actuatorstep = 5",
                        "",
                        "[LS_PLC]",
                        "ip = 192.168.10.220",
                        "port = 2004",
                        "",
                        "[SETTINGS]",
                        "password = 8860",
                        "",
                        "[LOGGING]",
                        "rotationmode = DAILY",
                        "",
                        "[THRESHOLDS_VALUE]",
                        "",
                        "[THRESHOLDS_ENABLE]",
                        "",
                    ]
                ),
                encoding="utf-8-sig",
            )

            from backend.Configuration import service

            original_config_path = service.config.CONFIG_PATH
            service.config.CONFIG_PATH = config_path
            try:
                service.clear_snapshot_cache()
                snapshot = service.get_config_snapshot()
            finally:
                service.clear_snapshot_cache()
                service.config.CONFIG_PATH = original_config_path

            spot = snapshot["values"]["spot"]
            self.assertEqual(spot["actuator_step"], 5)
            self.assertEqual(spot["actuator_ip"], "10.1.10.60")
            self.assertEqual(spot["focus_step"], 200)

    def test_legacy_cycle_threshold_migrates_to_status_jam_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.ini"
            config_path.write_text(
                "\n".join(
                    [
                        "[LOGGING]",
                        "rotationmode = BILLET",
                        "cycleidletime = 30",
                        "cyclethresholdpress = 55.5",
                        "",
                    ]
                ),
                encoding="utf-8-sig",
            )

            from backend.Configuration import service
            from backend.Configuration.Configuration_Structure import ConfigUpdate

            original_config_path = service.config.CONFIG_PATH
            original_allow_local_config = service.os.environ.get("SFL_ALLOW_LOCAL_CONFIG")
            service.config.CONFIG_PATH = config_path
            service.os.environ["SFL_ALLOW_LOCAL_CONFIG"] = "1"
            try:
                service.clear_snapshot_cache()
                snapshot = service.get_config_snapshot()
                self.assertEqual(snapshot["values"]["status"]["jam_press_threshold"], 55.5)

                with mock.patch.object(service.config_meta, "record_local_update", return_value={}):
                    with mock.patch.object(service.config_manager, "reload", return_value={}):
                        with mock.patch.object(service.config_manager, "apply_changes", return_value={}):
                            service.update_config(ConfigUpdate(settings={"autosave": True}), source="local")
            finally:
                service.clear_snapshot_cache()
                service.config.CONFIG_PATH = original_config_path
                if original_allow_local_config is None:
                    service.os.environ.pop("SFL_ALLOW_LOCAL_CONFIG", None)
                else:
                    service.os.environ["SFL_ALLOW_LOCAL_CONFIG"] = original_allow_local_config

            migrated_text = config_path.read_text(encoding="utf-8-sig")
            self.assertIn("[STATUS]", migrated_text)
            self.assertIn("jampressthreshold = 55.5", migrated_text)
            self.assertNotIn("cyclethresholdpress", migrated_text)
            self.assertNotIn("rotationmode", migrated_text)

    def test_update_config_writes_status_jam_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.ini"
            config_path.write_text(
                "\n".join(
                    [
                        "[STATUS]",
                        "jampressthreshold = 20.0",
                        "",
                    ]
                ),
                encoding="utf-8-sig",
            )

            from backend.Configuration import service
            from backend.Configuration.Configuration_Structure import ConfigUpdate

            original_config_path = service.config.CONFIG_PATH
            original_allow_local_config = service.os.environ.get("SFL_ALLOW_LOCAL_CONFIG")
            service.config.CONFIG_PATH = config_path
            service.os.environ["SFL_ALLOW_LOCAL_CONFIG"] = "1"
            try:
                with mock.patch.object(service.config_meta, "record_local_update", return_value={}):
                    with mock.patch.object(service.config_manager, "reload", return_value={}):
                        with mock.patch.object(service.config_manager, "apply_changes", return_value={}):
                            service.update_config(
                                ConfigUpdate(status={"jam_press_threshold": 42.5}),
                                source="local",
                            )
                service.clear_snapshot_cache()
                snapshot = service.get_config_snapshot()
            finally:
                service.clear_snapshot_cache()
                service.config.CONFIG_PATH = original_config_path
                if original_allow_local_config is None:
                    service.os.environ.pop("SFL_ALLOW_LOCAL_CONFIG", None)
                else:
                    service.os.environ["SFL_ALLOW_LOCAL_CONFIG"] = original_allow_local_config

            self.assertEqual(snapshot["values"]["status"]["jam_press_threshold"], 42.5)
            self.assertIn("jampressthreshold = 42.5", config_path.read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
