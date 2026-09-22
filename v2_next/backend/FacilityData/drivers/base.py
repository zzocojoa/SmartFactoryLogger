from abc import ABC, abstractmethod
from typing import Any
from backend.FacilityData.schemas import FactoryData

class BasePLCDriver(ABC):
    """
    Abstract Base Class for PLC Drivers.
    Enforces interface for both Real (Melsec/Modbus) and Mock drivers.
    """
    
    def __init__(self):
        self.connected = False
        
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to PLC/Device."""
        pass
        
    @abstractmethod
    def read_data(self) -> FactoryData:
        """
        Read all required registers and return a structured FactoryData object.
        Should handle exceptions internally and return safe defaults or current state.
        """
        pass
        
    @abstractmethod
    def close(self) -> bool:
        """Close owned resources; True only when all owned work has stopped.

        Synchronous drivers with no background workers return True after cleanup.
        A timeout or cleanup failure returns False and preserves remaining ownership.
        """
        pass

    def get_comm_metrics(self) -> dict:
        return {}
