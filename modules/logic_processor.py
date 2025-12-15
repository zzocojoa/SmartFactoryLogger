import os
import json
import time
import datetime
from pathlib import Path
from config import APP_DATA_DIR

class LogicProcessor:
    def __init__(self):
        self.state_path = os.path.join(APP_DATA_DIR, "state.json")
        
        # State Variables
        self.die_id = None
        self.die_seq = 0
        self.billet_cycle_id = 0
        self.last_counter = -1
        self.last_update_time = 0.0
        
        # Cycle Detection Logic
        self.cycle_state = 0 # 0: IDLE, 1: PRE_CYCLE, 2: IN_CYCLE
        self.cycle_start_time = 0.0
        self.cycle_max_pressure = 0.0
        
        # Load persisted state
        self._load_state()

    def _load_state(self):
        """ Load state from JSON file for persistence """
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.die_id = data.get('die_id')
                    self.die_seq = data.get('die_seq', 0)
                    self.billet_cycle_id = data.get('billet_cycle_id', 0)
                    self.last_counter = data.get('last_counter', -1)
                    self.last_update_time = data.get('last_update_time', 0.0)
                    # Restore cycle state if available, or default to IDLE
                    self.cycle_state = data.get('cycle_state', 0)
            except Exception as e:
                print(f"[LogicProcessor] Failed to load state: {e}")
                # Fallback to defaults if file is corrupt
                
    def _save_state(self):
        """ Atomic write to save state """
        try:
            data = {
                'die_id': self.die_id,
                'die_seq': self.die_seq,
                'billet_cycle_id': self.billet_cycle_id,
                'last_counter': self.last_counter,
                'last_update_time': self.last_update_time,
                'cycle_state': self.cycle_state
            }
            
            temp_path = self.state_path + ".tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
                
            # Atomic replacement
            if os.path.exists(self.state_path):
                os.replace(temp_path, self.state_path)
            else:
                os.rename(temp_path, self.state_path)
                
        except Exception as e:
            print(f"[LogicProcessor] Failed to save state: {e}")

    def _generate_die_id(self, timestamp):
        """ Generate DIE_ID based on Date and Sequence """
        date_str = timestamp.strftime("%Y%m%d")
        return f"{date_str}_{self.die_seq:02d}"

    def update(self, count, pressure, speed, timestamp):
        """
        Update logic state and return current (die_id, billet_cycle_id)
        
        Args:
            count (float/int): Production counter from PLC
            pressure (float): Main pressure
            speed (float): Extrusion speed
            timestamp (datetime): Current data timestamp
        
        Returns:
            tuple: (die_id, billet_cycle_id) - Strings or Empty String on invalid
        """
        # Null Handling
        if count is None:
            return "", ""
        
        try:
            current_count = int(count)
        except:
            return "", "" # Invalid count data

        try:
            current_press = float(pressure) if pressure is not None else 0.0
        except:
            current_press = 0.0

        # State Sync Timestamp
        self.last_update_time = timestamp.timestamp()

        # -----------------------------------------------------------
        # 1. Run (Die) Detection Logic
        # -----------------------------------------------------------
        is_die_changed = False
        
        # Initialize if first run
        if self.last_counter == -1:
            self.last_counter = current_count
            # If no ID exists yet, generate one
            if not self.die_id:
                self.die_seq = 1
                self.die_id = self._generate_die_id(timestamp)
                # [Fix] Sync internal cycle ID with PLC counter on startup
                # To align with 0-based indexing (Logic match PLC at Start):
                # If PLC is 5, next trigger makes Logic 5. So init at 4.
                self.billet_cycle_id = current_count - 1
                self._save_state()
        
        # Trigger: Counter Reset (Inversion) -> New Die Run
        # Explicit Inversion: Current < Last (and not just jitter)
        if current_count < self.last_counter:
            is_die_changed = True
            
        if is_die_changed:
            # [Logic] Check for Date Change to Reset Sequence
            # Extract date from current ID (e.g. "20251215_01" -> "20251215")
            current_date_str = timestamp.strftime("%Y%m%d")
            last_date_str = self.die_id.split('_')[0] if self.die_id else ""
            
            if current_date_str != last_date_str:
                self.die_seq = 0 # Reset sequence if date changed

            self.die_seq += 1
            self.die_id = self._generate_die_id(timestamp)
            self.billet_cycle_id = -1 # Reset to -1 so next start becomes 0 (0-based execution)
            self._save_state()
            
        self.last_counter = current_count # Update tracker

        # -----------------------------------------------------------
        # 2. Billet Cycle Logic (Simplified: Speed Trigger -> Reflect Logic)
        # -----------------------------------------------------------
        # -----------------------------------------------------------
        # 2. Billet Cycle Logic (Simplified: Speed Trigger -> Reflect Logic)
        # -----------------------------------------------------------
        SPEED_THRESHOLD = 0.2  # [User Request] Lower threshold
        
        try:
            current_speed = float(speed) if speed is not None else 0.0
        except:
            current_speed = 0.0
        
        # [User Request] Just reflect billet count when Speed rises
        # This aligns Logic Count with PLC Count at the start of the cycle.
        cycle_id_output = "" # Default to empty string (null) if stopped
        
        if current_speed > SPEED_THRESHOLD:
            # Only update if different to avoid frequent writes (optional but good practice)
            if self.billet_cycle_id != current_count:
                self.billet_cycle_id = current_count
                self._save_state()
            
            # When moving, return the active ID
            cycle_id_output = str(self.billet_cycle_id)
        
        # Note: When speed is low, we return "", but self.billet_cycle_id holds the LAST count.

        # Return current valid IDs (DIE_ID always valid, Cycle ID only when running)
        return self.die_id, cycle_id_output

    def set_manual_die_id(self, manual_id):
        """ Future extension for MES integration """
        self.die_id = str(manual_id)
        self.billet_cycle_id = 0
        self._save_state()
