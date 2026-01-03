import json
import os
from pathlib import Path
from typing import Optional

from .. import config


class LogicProcessor:
    def __init__(self) -> None:
        self.state_path = Path(config.APP_DATA_DIR) / "state.json"
        self.die_id: Optional[str] = None
        self.die_seq = 0
        self.billet_cycle_id = 0
        self.last_counter = -1
        self.last_update_time = 0.0
        self.cycle_state = 0
        self._load_state()

    def _load_state(self) -> None:
        if not self.state_path.exists():
            return
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return
        self.die_id = data.get("die_id")
        self.die_seq = int(data.get("die_seq", 0))
        self.billet_cycle_id = int(data.get("billet_cycle_id", 0))
        self.last_counter = int(data.get("last_counter", -1))
        self.last_update_time = float(data.get("last_update_time", 0.0))
        self.cycle_state = int(data.get("cycle_state", 0))

    def _save_state(self) -> None:
        payload = {
            "die_id": self.die_id,
            "die_seq": self.die_seq,
            "billet_cycle_id": self.billet_cycle_id,
            "last_counter": self.last_counter,
            "last_update_time": self.last_update_time,
            "cycle_state": self.cycle_state,
        }
        tmp_path = self.state_path.with_suffix(".tmp")
        try:
            tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp_path.replace(self.state_path)
        except Exception:
            pass

    def _generate_die_id(self, timestamp) -> str:
        date_str = timestamp.strftime("%Y%m%d")
        return f"{date_str}_{self.die_seq:02d}"

    def update(self, count, pressure, speed, timestamp):
        if count is None:
            return "", ""
        try:
            current_count = int(count)
        except Exception:
            return "", ""

        try:
            current_speed = float(speed) if speed is not None else 0.0
        except Exception:
            current_speed = 0.0

        self.last_update_time = timestamp.timestamp()

        if self.last_counter == -1:
            self.last_counter = current_count
            if not self.die_id:
                self.die_seq = 1
                self.die_id = self._generate_die_id(timestamp)
                self.billet_cycle_id = current_count - 1
                self._save_state()

        is_die_changed = current_count < self.last_counter
        if is_die_changed:
            current_date_str = timestamp.strftime("%Y%m%d")
            last_date_str = self.die_id.split("_")[0] if self.die_id else ""
            if current_date_str != last_date_str:
                self.die_seq = 0
            self.die_seq += 1
            self.die_id = self._generate_die_id(timestamp)
            self.billet_cycle_id = -1
            self._save_state()

        self.last_counter = current_count

        cycle_id_output = ""
        if current_speed > 0.1:
            if self.billet_cycle_id != current_count:
                self.billet_cycle_id = current_count
                self._save_state()
            cycle_id_output = str(self.billet_cycle_id)

        return self.die_id or "", cycle_id_output
