import sys
import os
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
import time
import traceback
import uuid

# --- EARLY LOGGING REDIRECTION ---
# Define EarlyLogger BEFORE using it
class EarlyLogger:
    def __init__(self, path):
        self.file = open(path, "a", encoding="utf-8", buffering=1)
    def write(self, buf):
        try:
            self.file.write(buf)
            self.file.flush()
        except: pass
    def flush(self):
        try: self.file.flush()
        except: pass
    def isatty(self): return False
    def fileno(self): return self.file.fileno()

def get_log_dir():
    app_data = os.getenv("APPDATA")
    if app_data:
        path = Path(app_data) / "SmartFactoryLogger" / "logs"
    else:
        path = Path.home() / "SmartFactoryLogger" / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path

LOG_DIR = get_log_dir()
STDOUT_PATH = LOG_DIR / "server_stdout.log"
STDERR_PATH = LOG_DIR / "server_stderr.log"

# Force redirection to capture EVERYTHING in the frozen environment
if getattr(sys, 'frozen', False):
    sys.stdout = EarlyLogger(STDOUT_PATH)
    sys.stderr = EarlyLogger(STDERR_PATH)

SESSION_ID = uuid.uuid4().hex[:12]
SESSION_STARTED_AT = datetime.now(timezone.utc).isoformat(timespec="seconds")
SESSION_PID = os.getpid()

print(
    f"\n--- SESSION START ({time.strftime('%Y-%m-%d %H:%M:%S')}) "
    f"session={SESSION_ID} pid={SESSION_PID} started_at={SESSION_STARTED_AT} ---"
)
print(f"DEBUG: sys.executable: {sys.executable}")
print(f"DEBUG: sys.path at startup: {sys.path}")

def _is_known_disconnect_error(exc):
    return isinstance(exc, ConnectionResetError) and getattr(exc, "winerror", None) == 10054


def _filter_asyncio_disconnect_noise(record):
    exc_info = getattr(record, "exc_info", None)
    if not exc_info or len(exc_info) < 2:
        return True
    exc = exc_info[1]
    return not _is_known_disconnect_error(exc)


if os.name == "nt":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        print("INFO: WindowsSelectorEventLoopPolicy enabled")
    except Exception as exc:
        print(f"WARNING: Failed to enable WindowsSelectorEventLoopPolicy: {exc}")
    logging.getLogger("asyncio").addFilter(_filter_asyncio_disconnect_noise)

# --- STANDARD IMPORTS ---
import multiprocessing
import threading
import webbrowser
from PIL import Image, ImageTk
import pystray
import tkinter as tk
import pydantic
import pydantic_core
from pydantic import BaseModel, field_validator

# 1. Initialize Freeze Support immediately for multiprocessing
if __name__ == "__main__":
    multiprocessing.freeze_support()

# --- 2. PROJECT ROOT & PATH SETUP ---
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # In PyInstaller bundle, the project root is the extraction directory
    project_root = Path(sys._MEIPASS)
    print(f"DEBUG: Frozen mode detected. sys._MEIPASS: {sys._MEIPASS}")
    try:
        meipass_content = os.listdir(sys._MEIPASS)
        print(f"DEBUG: Contents of sys._MEIPASS: {meipass_content}")
        if 'backend' in meipass_content:
            backend_content = os.listdir(project_root / 'backend')
            print(f"DEBUG: Contents of backend/ inside _MEIPASS: {backend_content}")
        else:
            print("WARNING: 'backend' directory NOT FOUND in sys._MEIPASS")
    except Exception as e:
        print(f"DEBUG: Error inspecting _MEIPASS: {e}")
else:
    # In development: v2_next/backend/scripts/legacy_servers/server_entry.py
    # .parent -> legacy_servers, .parent -> scripts, .parent -> backend, .parent -> v2_next
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    print(f"DEBUG: Dev mode detected. project_root: {project_root}")

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
    print(f"DEBUG: Added {project_root} to sys.path")

print(f"DEBUG: sys.path after injection: {sys.path}")

try:
    from backend.version import get_runtime_info
    print(f"INFO: Runtime info: {get_runtime_info()}")
except Exception as e:
    print(f"WARNING: Failed to load runtime info: {e}")

# --- CORE IMPORTS ---
try:
    print("DEBUG: Importing backend modules...")
    import uvicorn
    # Test absolute import
    from backend.app import app
    from backend import config
    from backend.scripts.migrate_json_to_db import migrate_json_files, get_default_data_dir
    print("DEBUG: Imports successful!")
except Exception as e:
    print(f"CRITICAL: Code Import Failed: {e}")
    traceback.print_exc()
    sys.stderr.flush()
    sys.stdout.flush()
    sys.exit(1)

# --- CLI ARGUMENT PARSING ---
def parse_args():
    """Parse command line arguments."""
    import argparse
    parser = argparse.ArgumentParser(description="SmartFactory Logger Backend")
    parser.add_argument(
        "--migrate-json",
        action="store_true",
        help="Migrate legacy JSON files to SQLite database before starting"
    )
    parser.add_argument(
        "--migrate-only",
        action="store_true",
        help="Run migration only without starting the server"
    )
    return parser.parse_args()


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = str(Path(__file__).parent)
    return os.path.join(base_path, relative_path)

# --- SPLASH SCREEN ---
_splash_window = None
_splash_closed = threading.Event()

def show_splash():
    """Display a splash screen while application loads."""
    global _splash_window
    try:
        splash_path = resource_path(os.path.join("backend", "assets", "splash.png"))
        if not os.path.exists(splash_path):
            splash_path = resource_path(os.path.join("assets", "splash.png"))
        
        if not os.path.exists(splash_path):
            print("[Splash] Splash image not found, skipping splash screen.")
            _splash_closed.set()
            return
        
        print(f"[Splash] Loading splash from {splash_path}")
        
        root = tk.Tk()
        _splash_window = root
        
        # Configure splash window
        root.overrideredirect(True)  # No window decorations
        root.attributes("-topmost", True)  # Always on top
        root.configure(bg='#1a1a2e')
        
        # Load and display image
        img = Image.open(splash_path)
        
        # Resize image to a reasonable splash size (max 400x400)
        max_size = 400
        if img.width > max_size or img.height > max_size:
            ratio = min(max_size / img.width, max_size / img.height)
            new_width = int(img.width * ratio)
            new_height = int(img.height * ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        photo = ImageTk.PhotoImage(img)
        
        # Center on screen
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        x = (screen_width - img.width) // 2
        y = (screen_height - img.height) // 2
        root.geometry(f"{img.width}x{img.height}+{x}+{y}")
        
        label = tk.Label(root, image=photo, bg='#1a1a2e')
        label.image = photo  # Keep reference
        label.pack()
        
        print("[Splash] Splash window displayed.")
        root.mainloop()
        
    except Exception as e:
        print(f"[Splash] Failed to show splash: {e}")
        traceback.print_exc()
    finally:
        _splash_closed.set()

def close_splash():
    """Close the splash screen from another thread."""
    global _splash_window
    try:
        if _splash_window:
            print("[Splash] Closing splash window...")
            _splash_window.after(0, _splash_window.destroy)
            _splash_window = None
    except Exception as e:
        print(f"[Splash] Failed to close splash: {e}")

def open_browser(icon=None, item=None):
    try:
        target_url = f"http://127.0.0.1:{config.BACKEND_PORT}"
        print(f"[Launcher] Opening browser at {target_url}")
        webbrowser.open(target_url)
    except Exception as e:
        print(f"Failed to open browser: {e}")

def quit_app(icon, item):
    print(f"[Launcher] Quit requested session={SESSION_ID} pid={SESSION_PID} started_at={SESSION_STARTED_AT}")
    icon.stop()
    os._exit(0)

def run_server():
    try:
        print(
            f"[Server] Starting Uvicorn on {config.BACKEND_PORT} "
            f"session={SESSION_ID} pid={SESSION_PID} started_at={SESSION_STARTED_AT}"
        )
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=config.BACKEND_PORT,
            reload=False,
            log_level="info",
            access_log=False,
        )
    except Exception as e:
        print(
            f"[Server] CRASHED: {e} "
            f"session={SESSION_ID} pid={SESSION_PID} started_at={SESSION_STARTED_AT}"
        )
        traceback.print_exc()

if __name__ == "__main__":
    try:
        # Parse CLI arguments
        args = parse_args()
        
        # Run JSON migration if requested
        if args.migrate_json or args.migrate_only:
            print("[Migration] Starting JSON to SQLite migration...")
            data_dir = get_default_data_dir()
            db_path = data_dir / "mes_data.db"
            migrate_json_files(data_dir, db_path, dry_run=False)
            print("[Migration] Migration complete.")
            
            if args.migrate_only:
                print("[Migration] --migrate-only flag set. Exiting without starting server.")
                sys.exit(0)
        
        # Start Splash Screen in separate thread (GUI must run in main for some OSes, but we'll try)
        splash_thread = threading.Thread(target=show_splash, daemon=True)
        splash_thread.start()
        
        # Give splash a moment to appear
        time.sleep(0.3)
        
        # Start Server thread
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

        # Wait for server to initialize (give it a moment)
        time.sleep(2.0)
        
        # Close splash and open browser
        close_splash()
        time.sleep(0.3)

        # Auto-open browser
        threading.Timer(0.5, open_browser).start()

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
        print(
            f"[Launcher] Main Loop Crash: {e} "
            f"session={SESSION_ID} pid={SESSION_PID} started_at={SESSION_STARTED_AT}"
        )
        traceback.print_exc()
        # Ensure we log before dying
        sys.stderr.flush()
        sys.stdout.flush()
