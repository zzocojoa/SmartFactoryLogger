import sys
import os
from pathlib import Path
import multiprocessing
import threading
import webbrowser
import time
import traceback
from PIL import Image
import pystray

# Explicitly import pydantic dependencies
import pydantic
import pydantic_core
from pydantic import BaseModel, field_validator

# --- CRITICAL: SCRIPT SETUP FOR WINDOWLESS EXECUTION ---
# 1. Initialize Freeze Support immediately for multiprocessing
if __name__ == "__main__":
    multiprocessing.freeze_support()

# 2. Redirect Standard Streams (Fix for noconsole crash)
# In noconsole mode, sys.stdin/stdout/stderr are None or invalid.
try:
    # Fix stdin
    if sys.stdin is None or sys.stdin.fileno() < 0:
        sys.stdin = open(os.devnull, "r")

    # Setup Logging Directory
    app_data = os.getenv("APPDATA")
    if app_data:
        log_dir = Path(app_data) / "SmartFactoryLogger" / "logs"
    else:
        log_dir = Path.home() / "SmartFactoryLogger" / "logs"
    
    log_dir.mkdir(parents=True, exist_ok=True)
    
    stdout_path = log_dir / "server_stdout.log"
    stderr_path = log_dir / "server_stderr.log"

    class StreamToLogger:
        def __init__(self, path):
            self.file = open(path, "a", encoding="utf-8", buffering=1)
        
        def write(self, buf):
            try:
                self.file.write(buf)
                self.file.flush()
            except:
                pass
        
        def flush(self):
            try:
                self.file.flush()
            except:
                pass

        def isatty(self):
            return False
            
        def fileno(self):
            return self.file.fileno()

    # Redirect stdout/stderr if they are None or we want to capture them
    # For noconsole, we MUST redirect them to avoid crashes on print()
    sys.stdout = StreamToLogger(stdout_path)
    sys.stderr = StreamToLogger(stderr_path)
    
    # Write startup marker
    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Launcher Starting (PID: {os.getpid()})...")

except Exception as e:
    # If logging setup fails, we are flying blind, but try to continue
    pass
# -------------------------------------------------------

# Add project root to sys.path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import App
try:
    import uvicorn
    try:
        from backend.app import app
        from backend import config
    except ImportError:
        from app import app
        import config
except Exception as e:
    print("CRITICAL: Code Import Failed")
    traceback.print_exc()
    sys.exit(1)

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = str(Path(__file__).parent)
    return os.path.join(base_path, relative_path)

def open_browser(icon=None, item=None):
    try:
        target_url = f"http://127.0.0.1:{config.BACKEND_PORT}"
        print(f"[Launcher] Opening browser at {target_url}")
        webbrowser.open(target_url)
    except Exception as e:
        print(f"Failed to open browser: {e}")

def quit_app(icon, item):
    icon.stop()
    os._exit(0)

def run_server():
    try:
        print(f"[Server] Starting Uvicorn on {config.BACKEND_PORT}...")
        uvicorn.run(app, host="0.0.0.0", port=config.BACKEND_PORT, reload=False, log_level="info")
    except Exception as e:
        print(f"[Server] CRASHED: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    try:
        # Start Server thread
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

        # optional: Give server a moment to init before UI logic
        time.sleep(0.5)

        # Setup System Tray
        icon_path = resource_path(os.path.join("backend", "assets", "icon.png"))
        if not os.path.exists(icon_path):
             icon_path = resource_path(os.path.join("assets", "icon.png"))
        
        if os.path.exists(icon_path):
            print(f"[Tray] Loading icon from {icon_path}")
            image = Image.open(icon_path)
            
            menu = pystray.Menu(
                pystray.MenuItem("Open Dashboard", open_browser, default=True),
                pystray.MenuItem("Exit", quit_app)
            )
            
            icon = pystray.Icon("SmartFactoryLogger", image, "Smart Factory Logger", menu)
            icon.run()
        else:
            print(f"[Tray] Icon not found at {icon_path}. Running handling loop without tray.")
            server_thread.join()

    except Exception as e:
        print(f"[Launcher] Main Loop Crash: {e}")
        traceback.print_exc()
        # Ensure we log before dying
        sys.stderr.flush()
        sys.stdout.flush()
