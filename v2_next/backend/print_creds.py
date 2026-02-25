
import sys
from pathlib import Path
# Ensure project root (parent of backend/) is on sys.path.
sys.path.append(str(Path(__file__).resolve().parent.parent))
from backend.MESSync.MESSync_Config import get_credentials

u, p = get_credentials()
print(f"ID:{u}")
print(f"PW:{p}")
