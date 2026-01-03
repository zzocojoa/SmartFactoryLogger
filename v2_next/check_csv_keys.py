import csv
from pathlib import Path

csv_path = Path(r"c:\Users\user\Documents\GitHub\SmartFactoryLogger\v2_next\Factory_Integrated_Log_20251217_000000.csv") # I need to check where the file is.
# Checking .env for V2_CSV_PATH first would be better, but let's assume standard location or check env.

def load_and_print_keys(path):
    print(f"Loading {path}...")
    if not path.exists():
        print("File not found!")
        return

    def read_with_encoding(enc):
        with path.open("r", encoding=enc) as f:
            reader = csv.DictReader(f)
            return [{k.strip(): v for k, v in row.items() if k} for row in reader]

    try:
        try:
            rows = read_with_encoding("utf-8-sig")
            print("Loaded with utf-8-sig")
        except UnicodeDecodeError:
            print("UTF-8 failed, trying CP949...")
            rows = read_with_encoding("cp949")
            print("Loaded with cp949")
            
        if rows:
            print("First row keys:", list(rows[0].keys()))
            print("First row values:", list(rows[0].values()))
            
            # Check for specific keys
            print("\nKey Check:")
            target_keys = ["현재속도", "Speed", "메인압력", "Temperature", "압출종료 위치"]
            for target in target_keys:
                found = target in rows[0]
                print(f"  '{target}': {'FOUND' if found else 'MISSING'}")
        else:
            print("No rows found.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Check paths
    paths = [
        Path(r"..\v1_legacy\logs\Aligned_Results\Factory_Integrated_Log_20251231_000000.csv"),
        Path(r"c:\Users\user\Documents\GitHub\SmartFactoryLogger\v1_legacy\logs\Aligned_Results\Factory_Integrated_Log_20251231_000000.csv"),
    ]
    for p in paths:
        load_and_print_keys(p)
