import json
import shutil
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse


class _OperationalObservabilityHandler(BaseHTTPRequestHandler):
    fact_path = r"C:\Users\operator\AppData\Roaming\SmartFactoryLogger\logs\test_data\spot_image_fact.csv"
    capture_root = (
        r"C:\Users\operator\AppData\Roaming\SmartFactoryLogger\logs\test_data"
        r"\spot_images\server_smoke_20260701-100445"
    )

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        payload = self._payload_for(path)
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return

    @classmethod
    def _payload_for(cls, path: str) -> dict:
        if path == "/stats":
            return {
                "total_http_5xx_count": 0,
                "total_http_4xx_count": 0,
                "error_count": 0,
                "window": {"seconds": 60},
                "polling": {"paths": {}},
            }
        if path == "/api/observability/errors":
            return {"summary": {"queue_size": 0}, "items": []}
        if path == "/api/spot/config":
            return {
                "image_capture": {
                    "enabled": True,
                    "mode": "all",
                    "queue_size": 0,
                    "queue_capacity": 128,
                    "enqueued_count": 3,
                    "written_count": 3,
                    "dropped_count": 0,
                    "failure_count": 0,
                    "last_write_at": 1782867948.0793145,
                },
                "spot_image_fact_manifest": {
                    "enabled": True,
                    "mode": "all",
                    "fact_path": cls.fact_path,
                    "capture_root": cls.capture_root,
                    "row_count": 19883,
                    "sha256": "bcb96397fbb97df8d6595fa8e71d03d0e60f4c2a6e7daaef0a54797d802f15d5",
                    "written": 3,
                    "dropped": 0,
                    "failure": 0,
                    "last_write_at": 1782867948.0793145,
                },
            }
        return {"status": "ok"}


class OperationalObservabilityExportTests(unittest.TestCase):
    def test_sanitized_summary_scrubs_spot_image_fact_manifest_paths(self) -> None:
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if powershell is None:
            self.skipTest("PowerShell is required for collect_operational_observability.ps1")

        repo_root = Path(__file__).resolve().parents[2]
        script = repo_root / "scripts" / "collect_operational_observability.ps1"

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "evidence"
            server = HTTPServer(("127.0.0.1", 0), _OperationalObservabilityHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                result = subprocess.run(
                    [
                        powershell,
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(script),
                        "-ApiBase",
                        f"http://127.0.0.1:{server.server_port}",
                        "-Samples",
                        "1",
                        "-IntervalSec",
                        "0",
                        "-OutputRoot",
                        str(output_root),
                    ],
                    cwd=repo_root,
                    text=True,
                    capture_output=True,
                    timeout=30,
                )
            finally:
                server.shutdown()
                server.server_close()

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            raw_files = list(output_root.glob("*/raw/sample_001_spot_config.json"))
            self.assertEqual(len(raw_files), 1)
            raw_text = raw_files[0].read_text(encoding="utf-8-sig")
            raw_envelope = json.loads(raw_text)
            raw_body = json.loads(raw_envelope["body"])
            raw_manifest = raw_body["spot_image_fact_manifest"]
            self.assertEqual(raw_manifest["fact_path"], _OperationalObservabilityHandler.fact_path)
            self.assertEqual(raw_manifest["capture_root"], _OperationalObservabilityHandler.capture_root)

            summaries = list(output_root.glob("*/sanitized/operational_observability_summary.json"))
            self.assertEqual(len(summaries), 1)
            summary_text = summaries[0].read_text(encoding="utf-8-sig")
            self.assertNotIn(_OperationalObservabilityHandler.fact_path, summary_text)
            self.assertNotIn(_OperationalObservabilityHandler.capture_root, summary_text)

            summary = json.loads(summary_text)
            manifest = summary["spot_config_samples"][0]["spot_image_fact_manifest"]
            self.assertEqual(manifest["fact_basename"], "spot_image_fact.csv")
            self.assertEqual(manifest["capture_root_basename"], "server_smoke_20260701-100445")
            self.assertRegex(manifest["fact_path_sha256"], r"^[a-f0-9]{64}$")
            self.assertRegex(manifest["capture_root_sha256"], r"^[a-f0-9]{64}$")
            self.assertNotIn("fact_path", manifest)
            self.assertNotIn("capture_root", manifest)
            self.assertTrue(manifest["path_values_redacted"])


if __name__ == "__main__":
    unittest.main()
