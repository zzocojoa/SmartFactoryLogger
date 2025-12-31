from config import APP_DATA_DIR
import os
import json

state_path = os.path.join(APP_DATA_DIR, "state.json")
print(f"State Path: {state_path}")

if os.path.exists(state_path):
    with open(state_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        print(json.dumps(data, indent=4))
else:
    print("State file not found.")
