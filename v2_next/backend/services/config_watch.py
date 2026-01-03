from __future__ import annotations

import logging
from pathlib import Path
import threading
import time
from typing import Optional, Tuple

from .. import config
from .config_manager import config_manager


class ConfigWatchService:
    def __init__(self, interval_sec: float = 1.0) -> None:
        self.interval_sec = max(0.5, float(interval_sec))
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self.logger = logging.getLogger("SmartFactoryLoggerV2")
        self._last_state: Optional[Tuple[int, int]] = None
        self._stable_checks = 3
        self._stable_delay_sec = 0.2

    def _config_path(self) -> Path:
        if config.CONFIG_PATH:
            return config.CONFIG_PATH
        return Path(config.APP_DATA_DIR) / "config.ini"

    def _get_state(self, path: Path) -> Optional[Tuple[int, int]]:
        try:
            stat = path.stat()
        except FileNotFoundError:
            return None
        except Exception:
            return None
        return (stat.st_mtime_ns, stat.st_size)

    def _wait_for_stable_state(self, path: Path, initial: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        last_state = initial
        for _ in range(self._stable_checks):
            time.sleep(self._stable_delay_sec)
            state = self._get_state(path)
            if state is None:
                return None
            if state == last_state and state[1] > 0:
                return state
            last_state = state
        if last_state[1] > 0:
            return last_state
        return None

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, name="ConfigWatch", daemon=True)
        self.thread.start()
        self.logger.info("Config watch started.")

    def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        self.thread = None
        self.logger.info("Config watch stopped.")

    def _loop(self) -> None:
        path = self._config_path()
        self._last_state = self._get_state(path)
        while self.running:
            time.sleep(self.interval_sec)
            path = self._config_path()
            state = self._get_state(path)
            if state == self._last_state:
                continue
            if state is None:
                self._last_state = state
                self.logger.warning("Config watch: config.ini not found.")
                continue
            stable_state = self._wait_for_stable_state(path, state)
            if stable_state is None:
                self.logger.warning("Config watch: config.ini unstable or empty, skipping reload.")
                continue
            self._last_state = stable_state
            try:
                changes = config_manager.reload()
                if not changes:
                    self.logger.info("Config watch: file changed but no config value differences.")
                    continue
                apply_result = config_manager.apply_changes(changes)
                self.logger.info(
                    "Config watch: applied=%s pending=%s",
                    len(apply_result.get("applied", [])),
                    len(apply_result.get("pending", [])),
                )
            except Exception as exc:
                self.logger.error("Config watch failed: %s", exc)


config_watch_service = ConfigWatchService()
