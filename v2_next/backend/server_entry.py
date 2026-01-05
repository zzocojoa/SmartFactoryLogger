import sys
import os
from pathlib import Path

# Add project root to sys.path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import uvicorn
# Import the app factor or app object from app.py
from backend.app import app

if __name__ == "__main__":
    # Host and port are hardcoded for production convenience
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
