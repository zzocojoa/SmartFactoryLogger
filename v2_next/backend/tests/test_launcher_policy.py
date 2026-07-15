import os
import unittest
from unittest.mock import patch

from backend.launcher_policy import is_embedded_electron, should_show_backend_splash


class LauncherPolicyTests(unittest.TestCase):
    def test_embedded_electron_disables_backend_splash(self) -> None:
        environ = {"SFL_EMBEDDED_ELECTRON": "1"}

        self.assertTrue(is_embedded_electron(environ))
        self.assertFalse(should_show_backend_splash(environ))

    def test_standalone_backend_preserves_legacy_splash(self) -> None:
        self.assertFalse(is_embedded_electron({}))
        self.assertTrue(should_show_backend_splash({}))

    def test_only_exact_enabled_value_selects_embedded_mode(self) -> None:
        for value in ("", "0", "true", "TRUE", " 1"):
            with self.subTest(value=value):
                self.assertFalse(is_embedded_electron({"SFL_EMBEDDED_ELECTRON": value}))

    def test_default_reads_process_environment(self) -> None:
        with patch.dict(os.environ, {"SFL_EMBEDDED_ELECTRON": "1"}, clear=False):
            self.assertTrue(is_embedded_electron())
            self.assertFalse(should_show_backend_splash())


if __name__ == "__main__":
    unittest.main()
