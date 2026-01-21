import json
import os
from pathlib import Path
from collections import Counter

# Path to the file user is looking at
FILE_PATH = Path(r"c:\Users\user\Documents\GitHub\SmartFactoryLogger\mes_data\생산\공정이동_현황\2025.json")

def check_extrusion_factories():
    if not FILE_PATH.exists():
        print(f"File not found: {FILE_PATH}")
        return

    try:
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        rows = data.get("data", [])
        print(f"Total rows in file: {len(rows)}")
        
        # Filter for Process = "압출"
        extrusion_rows = [r for r in rows if r.get("공정") == "압출"]
        print(f"Rows with '공정': '압출': {len(extrusion_rows)}")
        
        if not extrusion_rows:
            # Check distinct processes
            processes = Counter(r.get("공정") for r in rows)
            print("\nAvailable Processes:")
            for p, c in processes.items():
                print(f"  {p}: {c}")
            return

        # Check factories for Extrusion
        factories = Counter(r.get("공장") for r in extrusion_rows)
        print("\nFactories dealing with '압출':")
        for f, c in factories.items():
            print(f"  {f}: {c}")

        # Also check factories for other processes just in case
        print("\nFactories for ALL processes:")
        all_factories = Counter(r.get("공장") for r in rows)
        for f, c in all_factories.most_common(5):
            print(f"  {f}: {c}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_extrusion_factories()
