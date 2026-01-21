
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
from v2_next.backend.mes_bridge.config_manager import get_credentials

u, p = get_credentials()
print(f"ID:{u}")
print(f"PW:{p}")
