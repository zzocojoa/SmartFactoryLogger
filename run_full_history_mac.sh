#!/bin/bash

# SmartFactoryLogger Full Historical Data Extraction (Mac/Linux)
# Usage: ./run_full_history_mac.sh

echo "Starting Full Historical Data Extraction (2016-2026)..."
echo "This process may take several hours."

# 1. Activate Virtual Environment (if used)
# source venv/bin/activate

# 2. Install Dependencies (Optional check)
# pip install -r requirements.txt
# playwright install chromium

# 3. Ensure we are in the project root
cd "$(dirname "$0")"

# 4. Run Collector
python3 -m v2_next.backend.mes_bridge.collector --from-year 2016 --to-year 2026

echo "Extraction Complete!"
