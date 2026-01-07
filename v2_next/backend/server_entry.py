import sys
import os
from pathlib import Path

# Explicitly import pydantic dependencies to force PyInstaller to include them
import pydantic
import pydantic_core
from pydantic import BaseModel, field_validator

import threading
import webbrowser

# Add project root to sys.path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import uvicorn
# Import the app factor or app object from app.py
try:
    from backend.app import app
    from backend import config
except ImportError:
    from app import app
    import config

def open_browser():
    target_url = f"http://127.0.0.1:{config.BACKEND_PORT}"
    print(f"[Launcher] Opening browser at {target_url}")
    webbrowser.open(target_url)

if __name__ == "__main__":
    # Schedule browser launch (wait 1.5s for server startup)
    threading.Timer(1.5, open_browser).start()

    # Host and port are hardcoded for production convenience
    uvicorn.run(app, host="0.0.0.0", port=config.BACKEND_PORT, reload=False)
