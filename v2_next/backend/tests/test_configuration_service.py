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

    def test_update_config_writes_operator_metadata_downtime_reset_hours(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.ini"
            config_path.write_text(
                "\n".join(
                    [
                        "[SETTINGS]",
                        "operator_metadata_downtime_reset_hours = 8",
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
                                ConfigUpdate(settings={"operator_metadata_downtime_reset_hours": 200}),
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

            self.assertEqual(snapshot["values"]["settings"]["operator_metadata_downtime_reset_hours"], 72)
            self.assertIn("operator_metadata_downtime_reset_hours = 72", config_path.read_text(encoding="utf-8-sig"))

    def test_config_snapshot_defaults_spot_image_capture_to_off(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.ini"
            config_path.write_text("[SPOT]\nip = 10.1.10.50\n", encoding="utf-8-sig")

            from backend.Configuration import service

            original_config_path = service.config.CONFIG_PATH
            service.config.CONFIG_PATH = config_path
            try:
                service.clear_snapshot_cache()
                snapshot = service.get_config_snapshot()
            finally:
                service.clear_snapshot_cache()
                service.config.CONFIG_PATH = original_config_path

            image_capture = snapshot["values"]["spot"]["image_capture"]
            self.assertFalse(image_capture["enabled"])
            self.assertEqual(image_capture["mode"], "off")
            self.assertEqual(image_capture["path"], "spot_images")
            self.assertEqual(image_capture["min_interval_sec"], 1.0)
            self.assertEqual(image_capture["max_bytes"], 2_000_000)
            self.assertEqual(image_capture["retention_days"], 7)
            self.assertTrue(image_capture["link_to_observation"])

    def test_update_config_writes_spot_image_capture_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.ini"
            config_path.write_text(
                "\n".join(
                    [
                        "[SPOT]",
                        "ip = 10.1.10.50",
                        "imagecaptureenabled = false",
                        "imagecapturemode = off",
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
                                ConfigUpdate(
                                    spot={
                                        "image_capture": {
                                            "enabled": True,
                                            "mode": "interval",
                                            "path": "spot_images\\ui_policy",
                                            "min_interval_sec": 2.5,
                                            "max_bytes": 1_500_000,
                                            "retention_days": 3,
                                            "link_to_observation": False,
                                        }
                                    }
                                ),
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

            image_capture = snapshot["values"]["spot"]["image_capture"]
            self.assertTrue(image_capture["enabled"])
            self.assertEqual(image_capture["mode"], "interval")
            self.assertEqual(image_capture["path"], "spot_images\\ui_policy")
            self.assertEqual(image_capture["min_interval_sec"], 2.5)
            self.assertEqual(image_capture["max_bytes"], 1_500_000)
            self.assertEqual(image_capture["retention_days"], 3)
            self.assertFalse(image_capture["link_to_observation"])
            text = config_path.read_text(encoding="utf-8-sig")
            self.assertIn("imagecaptureenabled = true", text)
            self.assertIn("imagecapturemode = interval", text)
            self.assertIn("imagecapturepath = spot_images\\ui_policy", text)
            self.assertIn("imagecaptureminintervalsec = 2.5", text)
            self.assertIn("imagecapturemaxbytes = 1500000", text)
            self.assertIn("imagecaptureretentiondays = 3", text)
            self.assertIn("imagecapturelinktoobservation = false", text)

    def test_update_config_rejects_unsafe_spot_image_capture_paths(self) -> None:
        unsafe_paths = [
            "C:\\tmp\\outside_logs",
            "/tmp/outside_logs",
            "\\tmp\\outside_logs",
            "..\\outside_logs",
            "spot_images\\..\\outside_logs",
            "spot_images/../outside_logs",
        ]

        for unsafe_path in unsafe_paths:
            with self.subTest(unsafe_path=unsafe_path):
                with tempfile.TemporaryDirectory() as temp_dir:
                    config_path = Path(temp_dir) / "config.ini"
                    config_path.write_text(
                        "\n".join(
                            [
                                "[SPOT]",
                                "ip = 10.1.10.50",
                                "imagecapturepath = spot_images",
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
                        with self.assertRaises(ValueError):
                            service.update_config(
                                ConfigUpdate(
                                    spot={
                                        "image_capture": {
                                            "enabled": True,
                                            "mode": "event",
                                            "path": unsafe_path,
                                        }
                                    }
                                ),
                                source="local",
                            )
                    finally:
                        service.clear_snapshot_cache()
                        service.config.CONFIG_PATH = original_config_path
                        if original_allow_local_config is None:
                            service.os.environ.pop("SFL_ALLOW_LOCAL_CONFIG", None)
                        else:
                            service.os.environ["SFL_ALLOW_LOCAL_CONFIG"] = original_allow_local_config

                    self.assertIn("imagecapturepath = spot_images", config_path.read_text(encoding="utf-8-sig"))

    def test_config_api_rejects_unsafe_spot_image_capture_path_with_400(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.ini"
            config_path.write_text(
                "\n".join(
                    [
                        "[SPOT]",
                        "ip = 10.1.10.50",
                        "imagecapturepath = spot_images",
                        "",
                    ]
                ),
                encoding="utf-8-sig",
            )

            from fastapi.testclient import TestClient

            from backend import app as backend_app
            from backend.Configuration import service

            original_config_path = service.config.CONFIG_PATH
            original_allow_local_config = service.os.environ.get("SFL_ALLOW_LOCAL_CONFIG")
            service.config.CONFIG_PATH = config_path
            service.os.environ["SFL_ALLOW_LOCAL_CONFIG"] = "1"
            client = TestClient(backend_app.app, raise_server_exceptions=False)
            response = None
            try:
                with mock.patch.object(service.config_meta, "record_local_update", return_value={}):
                    with mock.patch.object(service.config_manager, "reload", return_value={}):
                        with mock.patch.object(service.config_manager, "apply_changes", return_value={}):
                            response = client.post(
                                "/api/config",
                                json={
                                    "spot": {
                                        "image_capture": {
                                            "enabled": True,
                                            "mode": "event",
                                            "path": "spot_images/../outside_logs",
                                        }
                                    }
                                },
                            )
            finally:
                client.close()
                service.clear_snapshot_cache()
                service.config.CONFIG_PATH = original_config_path
                if original_allow_local_config is None:
                    service.os.environ.pop("SFL_ALLOW_LOCAL_CONFIG", None)
                else:
                    service.os.environ["SFL_ALLOW_LOCAL_CONFIG"] = original_allow_local_config

            self.assertIsNotNone(response)
            assert response is not None
            self.assertEqual(response.status_code, 400)
            self.assertIn("parent path", response.json()["detail"])
            self.assertIn("imagecapturepath = spot_images", config_path.read_text(encoding="utf-8-sig"))

    def test_update_config_hot_reloads_spot_image_capture_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.ini"
            config_path.write_text(
                "\n".join(
                    [
                        "[SPOT]",
                        "ip = 10.1.10.50",
                        "imagecaptureenabled = false",
                        "imagecapturemode = off",
                        "",
                    ]
                ),
                encoding="utf-8-sig",
            )

            from backend.Configuration import service
            from backend.Configuration.Configuration_Structure import ConfigUpdate

            original_config_path = service.config.CONFIG_PATH
            original_allow_local_config = service.os.environ.get("SFL_ALLOW_LOCAL_CONFIG")
            capture_env_keys = [
                "SPOT_IMAGE_CAPTURE_ENABLED",
                "SPOT_IMAGE_CAPTURE_MODE",
                "SPOT_IMAGE_CAPTURE_PATH",
                "SPOT_IMAGE_CAPTURE_MIN_INTERVAL_SEC",
                "SPOT_IMAGE_CAPTURE_MAX_BYTES",
                "SPOT_IMAGE_CAPTURE_RETENTION_DAYS",
                "SPOT_IMAGE_CAPTURE_LINK_TO_OBSERVATION",
            ]
            original_env = {key: service.os.environ.get(key) for key in capture_env_keys}
            original_capture_values = {
                "enabled": service.config.SPOT_IMAGE_CAPTURE_ENABLED,
                "mode": service.config.SPOT_IMAGE_CAPTURE_MODE,
                "path": service.config.SPOT_IMAGE_CAPTURE_PATH,
                "min_interval_sec": service.config.SPOT_IMAGE_CAPTURE_MIN_INTERVAL_SEC,
                "max_bytes": service.config.SPOT_IMAGE_CAPTURE_MAX_BYTES,
                "retention_days": service.config.SPOT_IMAGE_CAPTURE_RETENTION_DAYS,
                "link_to_observation": service.config.SPOT_IMAGE_CAPTURE_LINK_TO_OBSERVATION,
            }
            result = None
            observed_capture_values = {}
            service.config.CONFIG_PATH = config_path
            service.os.environ["SFL_ALLOW_LOCAL_CONFIG"] = "1"
            for key in capture_env_keys:
                service.os.environ.pop(key, None)
            try:
                with mock.patch.object(service.config_meta, "record_local_update", return_value={}):
                    result = service.update_config(
                        ConfigUpdate(
                            spot={
                                "image_capture": {
                                    "enabled": True,
                                    "mode": "event",
                                    "path": "spot_images\\hot_reload",
                                    "min_interval_sec": 4.0,
                                    "max_bytes": 900_000,
                                    "retention_days": 2,
                                    "link_to_observation": True,
                                }
                            }
                        ),
                        source="local",
                    )
                observed_capture_values = {
                    "enabled": service.config.SPOT_IMAGE_CAPTURE_ENABLED,
                    "mode": service.config.SPOT_IMAGE_CAPTURE_MODE,
                    "path": service.config.SPOT_IMAGE_CAPTURE_PATH,
                    "min_interval_sec": service.config.SPOT_IMAGE_CAPTURE_MIN_INTERVAL_SEC,
                    "max_bytes": service.config.SPOT_IMAGE_CAPTURE_MAX_BYTES,
                    "retention_days": service.config.SPOT_IMAGE_CAPTURE_RETENTION_DAYS,
                    "link_to_observation": service.config.SPOT_IMAGE_CAPTURE_LINK_TO_OBSERVATION,
                }
            finally:
                service.clear_snapshot_cache()
                service.config.CONFIG_PATH = original_config_path
                service.config.SPOT_IMAGE_CAPTURE_ENABLED = original_capture_values["enabled"]
                service.config.SPOT_IMAGE_CAPTURE_MODE = original_capture_values["mode"]
                service.config.SPOT_IMAGE_CAPTURE_PATH = original_capture_values["path"]
                service.config.SPOT_IMAGE_CAPTURE_MIN_INTERVAL_SEC = original_capture_values["min_interval_sec"]
                service.config.SPOT_IMAGE_CAPTURE_MAX_BYTES = original_capture_values["max_bytes"]
                service.config.SPOT_IMAGE_CAPTURE_RETENTION_DAYS = original_capture_values["retention_days"]
                service.config.SPOT_IMAGE_CAPTURE_LINK_TO_OBSERVATION = original_capture_values["link_to_observation"]
                for key, value in original_env.items():
                    if value is None:
                        service.os.environ.pop(key, None)
                    else:
                        service.os.environ[key] = value
                if original_allow_local_config is None:
                    service.os.environ.pop("SFL_ALLOW_LOCAL_CONFIG", None)
                else:
                    service.os.environ["SFL_ALLOW_LOCAL_CONFIG"] = original_allow_local_config

            self.assertIsNotNone(result)
            self.assertIn("spot.image_capture.enabled", result["apply"]["applied"])
            self.assertIn("spot.image_capture.mode", result["apply"]["applied"])
            self.assertTrue(observed_capture_values["enabled"])
            self.assertEqual(observed_capture_values["mode"], "event")
            self.assertEqual(observed_capture_values["path"], "spot_images\\hot_reload")
            self.assertEqual(observed_capture_values["min_interval_sec"], 4.0)
            self.assertEqual(observed_capture_values["max_bytes"], 900_000)
            self.assertEqual(observed_capture_values["retention_days"], 2)
            self.assertTrue(observed_capture_values["link_to_observation"])


if __name__ == "__main__":
    unittest.main()
