from pydantic import BaseModel
from typing import Optional

class FactoryData(BaseModel):
    # System
    Time: str
    Status: str = "Running"
    
    # KPIs
    Speed: float
    Press: float
    Count: int
    EndPos: float
    Billet_Length: float
    
    # Temperatures
    Spot: float
    Temp_F: float
    Temp_B: float
    Billet_Temp: float
    
    # Molds
    Mold1: float
    Mold2: float
    Mold3: float
    Mold4: float
    Mold5: float
    Mold6: float
    
    # Environment
    At_Temp: float
    At_Pre: float

class SystemStatus(BaseModel):
    connection: bool
    mode: str  # REAL / MOCK
    message: str
