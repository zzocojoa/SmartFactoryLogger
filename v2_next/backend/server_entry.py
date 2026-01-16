import sys
import os
from pathlib import Path
import multiprocessing
import threading
import webbrowser
import time
import traceback
from PIL import Image, ImageTk
import pystray
import tkinter as tk

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
        from backend.scripts.migrate_json_to_db import migrate_json_files, get_default_data_dir
    except ImportError:
        from app import app
        import config
        from scripts.migrate_json_to_db import migrate_json_files, get_default_data_dir
except Exception as e:
    print("CRITICAL: Code Import Failed")
    traceback.print_exc()
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
        print(f"[Launcher] Main Loop Crash: {e}")
        traceback.print_exc()
        # Ensure we log before dying
        sys.stderr.flush()
        sys.stdout.flush()
