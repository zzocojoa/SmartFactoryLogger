import random
import time
from datetime import datetime
from .base import BasePLCDriver
from backend.FacilityData.schemas import FactoryData
from ..processor import LogicProcessor

class MockPLCDriver(BasePLCDriver):
    def __init__(self):
        super().__init__()
        self.logic = LogicProcessor()

    def connect(self) -> bool:
        print("[MockDriver] Connected to Virtual Factory.")
        self.connected = True
        return True

    def apply_connection_config(self) -> None:
        # Mock driver has no remote connection; keep connected flag.
        self.connected = True
        
    def read_data(self) -> FactoryData:
        # Simulate realistic factory data
        now = datetime.now()
        
        # Base values with noise
        speed = round(random.uniform(2.0, 2.8), 2)
        press = round(random.uniform(140.0, 150.0), 1)
        spot = round(520.0 + random.uniform(-5, 5), 1)
        
        # Cycle Count (increment every 10s logic handled by caller or here?)
        # Let's keep it simple here, return snapshot
        
        die_id, billet_cycle_id = self.logic.update(
            1000 + int(now.timestamp() / 10) % 100,
            press,
            speed,
            now,
        )

        return FactoryData(
            Time=now.isoformat(),
            Status="Running",
            Speed=speed,
            Press=press,
            Count=1000 + int(now.timestamp() / 10) % 100, # Mock increment
            EndPos=15.0,
            Billet_Length=600.0,
            Die_ID=die_id,
            Billet_Cycle_ID=billet_cycle_id,
            Spot=spot,
            Temp_F=450.0,
            Temp_B=440.0,
            Billet_Temp=480.0,
            Mold1=random.randint(60, 80),
            Mold2=random.randint(60, 80),
            Mold3=random.randint(60, 80),
            Mold4=random.randint(60, 80),
            Mold5=random.randint(60, 80),
            Mold6=random.randint(60, 80),
            At_Temp=24.0,
            At_Pre=45.0
        )
        
    def close(self):
        print("[MockDriver] Connection Closed.")
        self.connected = False
