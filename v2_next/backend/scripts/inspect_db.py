import sys
import os

# Add v2_next to path to allow imports from backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.MESSync import repository as db_manager

def inspect_page(page_key):
    print(f"Testing db_manager.get_latest_data('{page_key}')...")
    try:
        result = db_manager.get_latest_data(page_key)
        if result:
            data = result['data']
            print(f"Record Count: {len(data)}")
            
            # Check for empty rows
            empty_indices = []
            for i, record in enumerate(data):
                if not any(str(v).strip() for v in record.values() if v is not None):
                    empty_indices.append(i)
            
            if empty_indices:
                print(f"Still found empty rows at indices: {empty_indices}")
            else:
                print("No empty rows found in result.")
            
            if len(data) > 74:
                print(f"DEBUG Row 75 (Index 74): {data[74]}")
                # Debug why it wasn't filtered
                record = data[74]
                print(f"Debug values: {[str(v).strip() for v in record.values() if v is not None]}")
                print(f"Any valid? {any(str(v).strip() for v in record.values() if v is not None)}")
        else:
            print("No result found.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_page("shape_hist")
