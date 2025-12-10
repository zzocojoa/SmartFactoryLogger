import pandas as pd
import numpy as np
import datetime

# [Configuration]
LOG_FILE = r"c:\Users\user\Documents\GitHub\SmartFactoryLogger\logs\Factory_Integrated_Log_20251210_000000.csv"
OUTPUT_FILE = "Factory_Integrated_Log_Shifted.csv"
DISTANCE_TO_SENSOR_M = 0.5  # 금형에서 센서까지 거리 (미터)

def process_log(filepath):
    print(f"Loading {filepath} using Pandas...")
    
    # 1. Load Data
    # Assuming standard mapping:
    # Date(0),Time(1),Temperature(2),Press(3),...,Speed(8)
    try:
        df = pd.read_csv(filepath, encoding='utf-8-sig', on_bad_lines='skip')
    except:
        df = pd.read_csv(filepath, encoding='cp949', on_bad_lines='skip')
        
    print(f"Loaded {len(df)} rows.")

    # 2. Preprocess Columns (Mapping)
    # We find columns by known names or indices
    col_map = {
        'Time': 'Time',
        'Date': 'Date',
        'Temperature': 'Temp', 
        '메인압력': 'Press', # Assuming Korean Header
        '현재속도': 'Speed'
    }
    
    # Check if headers exist
    missing_cols = [k for k in col_map.keys() if k not in df.columns]
    if missing_cols:
        print(f"Warning: Columns not found: {missing_cols}. Trying index based mapping.")
        # Fallback to index mapping if specific korean headers are missing
        # Date,Time,Temperature,메인압력,빌렛길이,콘F,콘B,CNT,현재속도
        df.columns.values[0] = 'Date'
        df.columns.values[1] = 'Time'
        df.columns.values[2] = 'Temp'
        df.columns.values[3] = 'Press'
        df.columns.values[8] = 'Speed'
    else:
        # Rename for easier access
        df.rename(columns=col_map, inplace=True)
    
    # 3. Timestamp Parsing (Robust)
    # Combine Date and Time
    print("Parsing Timestamps...")
    
    # Custom parser for "00:00.6" issue
    def parse_ts(date_str, time_str):
        try:
            return pd.to_datetime(f"{date_str} {time_str}", format="%Y-%m-%d %H:%M:%S.%f")
        except:
            try:
                # Fix "00:00.6" -> "00:00:00.6"
                if str(time_str).count(':') == 1:
                    time_str = "00:" + str(time_str)
                return pd.to_datetime(f"{date_str} {time_str}") # Smart parse
            except:
                return pd.NaT

    # Apply parser (Vectorized is cleaner but for fuzzy parsing apply might be needed)
    # To speed up, we correct 'Time' column first
    def fix_time(t):
        t = str(t)
        if t.count(':') == 1: return "00:" + t
        return t
    
    df['Time'] = df['Time'].apply(fix_time)
    df['FullPC'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], errors='coerce')
    
    # Drop rows with invalid timestamps
    initial_len = len(df)
    df = df.dropna(subset=['FullPC'])
    if len(df) < initial_len:
        print(f"Dropped {initial_len - len(df)} rows due to invalid timestamps.")

    # 4. Calculation (Vectorized)
    print("Calculating Distance...")
    # Fill NaN Speed/Press with 0
    df['Speed'] = pd.to_numeric(df['Speed'], errors='coerce').fillna(0)
    df['Temp'] = pd.to_numeric(df['Temp'], errors='coerce') # Leave NaN as NaN or fill? None usually means sensor error or off
    
    # Calculate dt (Time Delta in Seconds)
    df['dt'] = df['FullPC'].diff().dt.total_seconds().fillna(0)
    
    # Distance Step (m) = Speed(mm/s) * dt(s) / 1000.0
    df['dist_step'] = (df['Speed'] * df['dt']) / 1000.0
    
    # Cumulative Distance
    df['cum_dist'] = df['dist_step'].cumsum()
    
    # 5. Alignment (Shift Logic)
    print(f"Aligning Temperature (Distance {DISTANCE_TO_SENSOR_M}m)...")
    
    # Target Distance for each row (Spawn) = Current CumDist + Sensor Distance
    # This means: "Find the row in the future where cum_dist >= My_cum_dist + 2.0"
    target_dist = df['cum_dist'] + DISTANCE_TO_SENSOR_M
    
    # SearchSorted: Find indices where target_dist fits in cum_dist
    # side='left' -> Find first index where cum_dist >= target
    future_indices = np.searchsorted(df['cum_dist'].values, target_dist.values, side='left')
    
    # Valid indices (within bounds)
    valid_mask = future_indices < len(df)
    
    # Create Aligned Column (initialized with NaN)
    df['Aligned_Temp'] = np.nan
    
    # Map values
    # df.loc[valid_mask, 'Aligned_Temp'] = df['Temp'].iloc[future_indices[valid_mask]].values
    # Note: iloc uses integer position.
    mapped_temps = df['Temp'].values[future_indices[valid_mask]]
    df.loc[valid_mask, 'Aligned_Temp'] = mapped_temps
    
    # 6. Apply to Original Column
    # User originally requested replacing the Temperature column.
    df['Temp'] = df['Aligned_Temp']
    
    # 7. Output Formatting
    print("Formatting Output...")
    # Force standard string format for CSV
    df['Date'] = df['FullPC'].dt.strftime('%Y-%m-%d')
    df['Time'] = df['FullPC'].dt.strftime('%H:%M:%S.%f').str[:-3] # Milliseconds
    
    # Drop temp columns
    cols_to_drop = ['FullPC', 'dt', 'dist_step', 'cum_dist', 'Aligned_Temp']
    df_final = df.drop(columns=cols_to_drop)
    
    # Restore Original Column Names if needed?
    # Original headers were: Date,Time,Temperature,메인압력...
    # We normalized to: Date,Time,Temp,Press,Speed...
    # Let's map back to match original file structure exactly if we can.
    # Actually, df still has other original columns (Mold1, etc).
    # We only renamed specific ones.
    reverse_map = {v:k for k,v in col_map.items()}
    df_final.rename(columns=reverse_map, inplace=True)
    
    # 8. Save
    print(f"Saving to {OUTPUT_FILE}...")
    df_final.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig') # EUC-KR or UTF-8-SIG? Log seems UTF-8-SIG based on previous.
    print("Done.")

if __name__ == "__main__":
    process_log(LOG_FILE)
