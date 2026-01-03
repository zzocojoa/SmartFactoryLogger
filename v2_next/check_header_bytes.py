from pathlib import Path

path = Path(r"..\v1_legacy\logs\Aligned_Results\Factory_Integrated_Log_20251231_000000.csv")

if not path.exists():
    path = Path(r"c:\Users\user\Documents\GitHub\SmartFactoryLogger\v1_legacy\logs\Aligned_Results\Factory_Integrated_Log_20251231_000000.csv")

try:
    with path.open("rb") as f:
        header_bytes = f.readline()
        print(f"Header bytes: {header_bytes}")
        
        try:
            print(f"Decoded cp949: {header_bytes.decode('cp949')}")
        except:
            print("cp949 decode failed")
            
        try:
            print(f"Decoded utf-8: {header_bytes.decode('utf-8')}")
        except:
            print("utf-8 decode failed")
except Exception as e:
    print(f"Error: {e}")
