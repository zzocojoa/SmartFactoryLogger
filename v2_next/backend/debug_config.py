import sys
import os

# Ensure backend modules can be imported
sys.path.append(os.getcwd())

from backend.services.config_manager import config_manager
from backend.services.config_service import get_config_snapshot

print(">>> Inspecting ConfigManager State...")
try:
    changes = config_manager.reload()
    print(f"Changes detected: {changes}")
    
    restart_req = config_manager.get_restart_required()
    print(f"Restart Required: {restart_req}")
    
    # Access private attribute for debugging
    pending_keys = config_manager._pending_keys
    print(f"Pending Keys in Memory: {pending_keys}")
    
    snapshot = get_config_snapshot()
    print(f"Snapshot Restart Required: {snapshot.get('restart_required')}")

except Exception as e:
    print(f"Error: {e}")
