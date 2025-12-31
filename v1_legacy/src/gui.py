# gui.py
import customtkinter as ctk
import tkinter as tk
import math
import time
import webbrowser
from datetime import datetime
from datetime import datetime
import requests
import io
import io
import threading
import queue
import re # [Focus Logic]
from PIL import Image, ImageDraw
from config import COLOR_BG, COLOR_PANEL, COLOR_CARD, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_ACCENT, COLOR_WARNING, COLOR_DANGER, COLOR_SUCCESS, COLOR_COLD, COLOR_HOT, PASSWORD, URL_SPOT_IMAGE, SPOT_REFRESH_INTERVAL, SPOT_CROSSHAIR_X, SPOT_CROSSHAIR_Y, SPOT_WIDGET_WIDTH, SPOT_WIDGET_HEIGHT, SPOT_CROSSHAIR_COLOR, SPOT_CROSSHAIR_THICK, SPOT_CROSSHAIR_SIZE, SPOT_CROSSHAIR_GAP
from settings_gui import SettingsWindow
from modules.ui_utils import CTkTooltip, ToastNotification, draw_dashed_line
from modules.graph_view import TimeSeriesPanel
from modules.ui_components import StatusBar, NotificationDrawer

# 테마 설정
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# 폰트 상수
FONT_MAIN = "Segoe UI" # Windows Standard Modern Font
FONT_MONO = "Consolas"

class CircularGauge(ctk.CTkCanvas):
    def __init__(self, master, width=220, height=220, min_val=0, max_val=20, **kwargs):
        if 'bg' not in kwargs: kwargs['bg'] = COLOR_PANEL
        super().__init__(master, width=width, height=height, highlightthickness=0, **kwargs)
        self.width = width
        self.height = height
        self.min_val = min_val
        self.max_val = max_val
        self.value = 0
        
        self.bind('<Configure>', self.on_resize)
        self.after(100, self.draw_static) # Initial Draw

    def on_resize(self, event):
        self.width = event.width
        self.height = event.height
        self.draw_static()
        self.update_dynamic()

    def draw_static(self):
        self.delete("all")
        cx, cy = self.width / 2, self.height / 2
        size = min(self.width, self.height)
        if size < 50: return
        
        radius = size * 0.4
        start_angle = 225
        extent = 270
        
        # 1. 배경 아크 (트랙)
        self.create_arc(cx-radius, cy-radius, cx+radius, cy+radius,
                        start=start_angle, extent=-extent, style=tk.ARC, width=size*0.06, outline="#3a3a3a")
        
        # 2. 눈금 (Ticks)
        for i in range(11):
            val_norm = i / 10
            angle = start_angle - (extent * val_norm)
            rad = math.radians(angle)
            cos_val = math.cos(rad)
            sin_val = math.sin(rad)
            
            inner_r = radius - (size * 0.08)
            outer_r = radius
            self.create_line(cx + inner_r*cos_val, cy - inner_r*sin_val,
                             cx + outer_r*cos_val, cy - outer_r*sin_val,
                             fill="#666666", width=max(1, size*0.01))
            
            if i % 2 == 0:
                text_r = radius - (size * 0.15)
                val = self.min_val + (self.max_val - self.min_val) * val_norm
                self.create_text(cx + text_r*cos_val, cy - text_r*sin_val,
                                 text=f"{int(val)}", fill="#888888", font=(FONT_MAIN, int(size*0.04)))

        # 3. Dynamic Elements Placeholders (Initialize if not exist, actually just creating them here is easier)
        # Value Arc (Hidden initially or 0)
        self.create_arc(cx-radius, cy-radius, cx+radius, cy+radius,
                        start=start_angle, extent=0, style=tk.ARC, width=size*0.06, outline=COLOR_SUCCESS, tags="val_arc")
                        
        # Needle
        self.create_line(cx, cy, cx, cy, fill="white", width=max(2, size*0.015), 
                         arrow=tk.LAST, arrowshape=(size*0.05, size*0.06, size*0.02), tags="needle")
                         
        # Center Dot
        self.create_oval(cx-size*0.02, cy-size*0.02, cx+size*0.02, cy+size*0.02, fill="white", outline=COLOR_PANEL)
        
        # Text Value
        self.create_text(cx, cy+(size*0.25), text="0.0", fill="white", font=(FONT_MAIN, int(size*0.15), "bold"), tags="text_val")
        self.create_text(cx, cy+(size*0.38), text="mm/s", fill=COLOR_TEXT_DIM, font=(FONT_MAIN, int(size*0.05)))
        
        self.update_dynamic()

    def update_dynamic(self):
        cx, cy = self.width / 2, self.height / 2
        size = min(self.width, self.height)
        if size < 50: return
        
        radius = size * 0.4
        start_angle = 225
        extent = 270
        
        val_pct = (self.value - self.min_val) / (self.max_val - self.min_val)
        val_pct = max(0, min(1, val_pct))
        
        # Color Logic
        color = COLOR_SUCCESS
        if val_pct > 0.5: color = COLOR_WARNING
        if val_pct > 0.8: color = COLOR_DANGER
        
        # Update Value Arc
        val_extent = extent * val_pct
        if val_extent > 0:
            self.itemconfigure("val_arc", extent=-val_extent, outline=color, state="normal")
        else:
            self.itemconfigure("val_arc", state="hidden")
            
        # Update Needle
        needle_angle = start_angle - (extent * val_pct)
        needle_rad = math.radians(needle_angle)
        needle_len = radius - (size * 0.05)
        nx = cx + needle_len * math.cos(needle_rad)
        ny = cy - needle_len * math.sin(needle_rad)
        self.coords("needle", cx, cy, nx, ny)
        
        # Update Text
        self.itemconfigure("text_val", text=f"{self.value:.1f}")

    def set_value(self, val):
        if self.value != val:
            self.value = val
            self.update_dynamic()

class InfoCard(ctk.CTkFrame):
    def __init__(self, master, title, value="--", unit="", color=COLOR_SUCCESS, title_size=14, value_size=28, height=None, **kwargs):
        # [Fix] Fixed Height Application
        if height:
            kwargs['height'] = height
            
        super().__init__(master, fg_color=COLOR_CARD, corner_radius=8, **kwargs) # 각진 모서리 (Modern)
        
        if height:
            self.pack_propagate(False) # 고정 높이 강제 (내용물에 의해 줄어들지 않음)
        
        # 사이드 바 (상태 표시줄)
        self.side_bar = ctk.CTkFrame(self, width=6, fg_color=COLOR_CARD, corner_radius=0) # 초기엔 숨김(배경색과 동일)
        self.side_bar.pack(side="left", fill="y", padx=(0, 5)) 
        
        # 컨텐츠 영역 (Vertical Center Alignment for Fixed Height)
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        self.title_lbl = ctk.CTkLabel(self.content, text=title, font=(FONT_MAIN, title_size), text_color=COLOR_TEXT_DIM)
        self.title_lbl.pack(anchor="w")
        
        self.value_container = ctk.CTkFrame(self.content, fg_color="transparent")
        self.value_container.pack(anchor="w", pady=(5, 0))
        
        self.value_lbl = ctk.CTkLabel(self.value_container, text=value, font=(FONT_MAIN, value_size, "bold"), text_color=color)
        self.value_lbl.pack(side="left")
        
        if unit:
            self.unit_lbl = ctk.CTkLabel(self.value_container, text=f" {unit}", font=(FONT_MAIN, value_size//2), text_color=COLOR_TEXT_DIM)
            self.unit_lbl.pack(side="left", padx=(4, 0), pady=(8, 0))
        
    def update_value(self, value, color=None, status_color=None):
        self.value_lbl.configure(text=value)
        if color:
            self.value_lbl.configure(text_color=color)
        
        # 사이드 바 색상 변경 (상태 표시)
        if status_color:
            self.side_bar.configure(fg_color=status_color)
        else:
            self.side_bar.configure(fg_color=COLOR_CARD) # 기본 상태

    def set_status(self, level):
        """
        level: 0 (Normal), 1 (Warning), 2 (Danger)
        """
        if level == 2:
            self.configure(border_width=2, border_color=COLOR_DANGER)
            self.side_bar.configure(fg_color=COLOR_DANGER)
        elif level == 1:
            self.configure(border_width=2, border_color=COLOR_WARNING)
            self.side_bar.configure(fg_color=COLOR_WARNING)
        else:
            self.configure(border_width=0)
            self.side_bar.configure(fg_color=COLOR_CARD)

    def add_button(self, text, command, tooltip=None):
        # Use absolute positioning relative to content frame (top-right)
        # We need to ensure we track how many buttons to stack them
        if not hasattr(self, 'btn_count'): self.btn_count = 0
        
        btn = ctk.CTkButton(self.content, text=text, width=30, height=30, 
                            fg_color="#444444", hover_color="#666666", 
                            font=("Segoe UI Emoji", 16), command=command)
        
        # Place at top right: relx=1.0 - padding
        # offset based on btn_count
        offset_x = -35 * self.btn_count
        btn.place(relx=1.0, x=offset_x, y=0, anchor="ne")
        
        if tooltip:
             CTkTooltip(btn, tooltip)
        
        self.btn_count += 1

class PasswordDialog(ctk.CTkToplevel):
    _last_geometry = None

    def __init__(self, parent, expected_password, title="Authentication"):
        super().__init__(parent)
        self.title(title)
        self.expected_password = expected_password
        self.verified = False
        
        # 이전 위치 복원 또는 중앙 정렬
        if PasswordDialog._last_geometry:
            self.geometry(PasswordDialog._last_geometry)
        else:
            self.geometry("300x180") # Error msg space added
            
        self.resizable(False, False)
        self.attributes("-topmost", True)
        
        ctk.CTkLabel(self, text="Enter Password:", font=("Arial", 14)).pack(pady=(15, 5))
        
        self.entry = ctk.CTkEntry(self, width=200, show="*")
        self.entry.pack(pady=5)
        self.entry.bind("<Return>", self.on_ok)
        
        # Error Label
        self.lbl_error = ctk.CTkLabel(self, text="", text_color=COLOR_DANGER, font=("Arial", 12))
        self.lbl_error.pack(pady=(0, 5))
        
        # 0.1초 후 강제 포커스
        self.after(100, self.safe_focus)
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10)
        
        ctk.CTkButton(btn_frame, text="OK", width=80, command=self.on_ok).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Cancel", width=80, fg_color="#555555", hover_color="#333333", command=self.on_cancel).pack(side="left", padx=5)
        
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        
        self.grab_set()
        self.wait_window()
        
    def safe_focus(self):
        try:
            if self.entry.winfo_exists():
                self.entry.focus_force()
        except: pass

    def on_ok(self, event=None):
        pw = self.entry.get()
        if pw == self.expected_password:
            self.verified = True
            PasswordDialog._last_geometry = self.geometry()
            self.grab_release()
            self.destroy()
        else:
            self.lbl_error.configure(text="Incorrect Password")
            self.entry.delete(0, 'end')
            # Shake animation or focus
            self.entry.focus_set()

    def on_cancel(self):
        PasswordDialog._last_geometry = self.geometry()
        self.grab_release()
        self.destroy()

    def is_verified(self):
        return self.verified

class CameraWidget(ctk.CTkFrame):
    def __init__(self, master, url, width=320, height=240, refresh_rate=1.0, **kwargs):
        super().__init__(master, width=width, height=height, fg_color="black", corner_radius=10, **kwargs)
        self.pack_propagate(False) # [Fix] Prevent collapsing when empty
        self.grid_propagate(False) 
        
        self.url = url
        self.target_width = width
        self.target_height = height
        self.crosshair_x = SPOT_CROSSHAIR_X
        self.crosshair_y = SPOT_CROSSHAIR_Y
        self.refresh_interval = int(1000 / refresh_rate) # ms
        self.running = True
        self.current_image = None
        self.error_msg = "Initializing..."
        self.lock = threading.Lock()
        
        # Image Display Label (Create FIRST so buttons overlay it)
        self.lbl_image = ctk.CTkLabel(self, text="")
        self.lbl_image.pack(expand=True, fill="both", padx=2, pady=2)

        # Placeholder / Status Label
        self.lbl_status = ctk.CTkLabel(self, text=self.error_msg, text_color="gray", wraplength=width-40)
        self.lbl_status.place(relx=0.5, rely=0.5, anchor="center")
        
        # Focus Controls (Overlay - Create AFTER image to be on top)
        # [User Request] Swapped Positions (Left button to Right, Right button to Left)
        self.btn_left = ctk.CTkButton(self, text="◀", width=30, height=50, 
                                      fg_color="#333333", hover_color="#555555", 
                                      font=("Segoe UI Emoji", 20),
                                      command=lambda: self.change_focus(-1))
        self.btn_left.place(relx=0.94, rely=0.5, anchor="center") # Moved to Right
        
        self.btn_right = ctk.CTkButton(self, text="▶", width=30, height=50, 
                                       fg_color="#333333", hover_color="#555555", 
                                       font=("Segoe UI Emoji", 20),
                                       command=lambda: self.change_focus(1))
        self.btn_right.place(relx=0.06, rely=0.5, anchor="center") # Moved to Left
        
        # Focus Queue
        self.focus_queue = queue.Queue()
        threading.Thread(target=self.focus_loop, daemon=True).start()
        
        # [Optimization] Use requests.Session for Keep-Alive
        self.session = requests.Session()

        # Start Fetch Thread
        self.thread = threading.Thread(target=self.fetch_loop, daemon=True)
        self.thread.start()
        
        # Start UI Update Loop
        self.after(500, self.update_image_ui)

    def fetch_loop(self):
        while self.running:
            try:
                # Try to fetch using requests Session (Keep-Alive)
                response = self.session.get(self.url, timeout=2)
                response.raise_for_status()
                
                img = Image.open(io.BytesIO(response.content))
                
                # [Memory Optimization] Resize immediately to target size
                # [Perf Optimization] Use BILINEAR instead of LANCZOS for video streams
                if self.target_width > 0 and self.target_height > 0:
                    img = img.resize((self.target_width, self.target_height), Image.Resampling.BILINEAR)
                
                # [Draw Crosshair] Enhanced Double-Layered Dashed Line
                draw = ImageDraw.Draw(img)
                w, h = img.size
                cx, cy = w * self.crosshair_x, h * self.crosshair_y
                
                # Configurable Style
                arm_len = SPOT_CROSSHAIR_SIZE
                gap = SPOT_CROSSHAIR_GAP
                thick = SPOT_CROSSHAIR_THICK
                color_fg = SPOT_CROSSHAIR_COLOR
                color_bg = "black"
                
                # Helper to draw double layer line
                def draw_double_Line(p1, p2):
                    # 1. Background (Contrast) - Thicker, Black
                    draw_dashed_line(draw, p1, p2, fill=color_bg, width=thick+2, dash=(4, 4))
                    # 2. Foreground (Visibility) - Nominal, Lime/Yellow
                    draw_dashed_line(draw, p1, p2, fill=color_fg, width=thick, dash=(4, 4))

                # Draw 4 Arms with Gap (Always Start from Center -> Outwards for Symmetry)
                # Left (Center -> Left)
                draw_double_Line((cx - gap, cy), (cx - arm_len, cy))
                # Right (Center -> Right)
                draw_double_Line((cx + gap, cy), (cx + arm_len, cy))
                # Top (Center -> Top)
                draw_double_Line((cx, cy - gap), (cx, cy - arm_len))
                # Bottom (Center -> Bottom)
                draw_double_Line((cx, cy + gap), (cx, cy + arm_len))

                # [Optional] Center Circle (Reticle)
                # Small ring to mark the absolute center
                r = 3 
                draw.ellipse((cx-r, cy-r, cx+r, cy+r), outline="black", width=3) # Background
                draw.ellipse((cx-r, cy-r, cx+r, cy+r), outline=color_fg, width=1) # Foreground
                
                with self.lock:
                    self.current_image = img
                    self.error_msg = None
            except Exception as e:
                # [Log] Print error to console
                print(f"[Camera] Connection Error: {e}")
                with self.lock:
                    self.error_msg = f"Error: {e}"
                
            time.sleep(SPOT_REFRESH_INTERVAL) # Fetch interval from config
            
    def update_image_ui(self):
        if not self.winfo_exists():
            self.running = False
            return
            
        img = None
        err = None
        with self.lock:
            img = self.current_image
            err = self.error_msg
            # self.current_image = None # Keep last image to avoid flicker
            
        if img:
            # Create CTkImage
            w, h = img.size
            ratio = min(self.target_width/w, self.target_height/h)
            new_w = int(w * ratio)
            new_h = int(h * ratio)
            
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(new_w, new_h))
            
            # Show Image Label, Hide Status
            self.lbl_image.configure(image=ctk_img)
            self.lbl_image.pack(expand=True, fill="both", padx=2, pady=2)
            self.lbl_status.place_forget()
        elif err:
            # Hide Image Label to ensure text is visible
            self.lbl_image.pack_forget()
            
            # Show Status
            self.lbl_status.configure(text=err, text_color="#ff5555")
            self.lbl_status.place(relx=0.5, rely=0.5, anchor="center")
            
        self.after(500, self.update_image_ui)

    def change_focus(self, direction):
        # direction: 1 (increase) or -1 (decrease)
        print(f"[UI] Button Clicked: {direction}")
        self.focus_queue.put(direction)

    def focus_loop(self):
        try:
             # from config import URL_SPOT_FOCUS, SPOT_FOCUS_STEP, IP_SPOT
             # [Switch] Use Actuator Config
             from config import URL_SPOT_ACTUATOR, SPOT_ACTUATOR_STEP, IP_SPOT
             
             while self.running:
                try:
                    # 1. Wait for first item (Blocking)
                    direction = self.focus_queue.get()
                    
                    # 2. Check for burst clicks (Queue Merging)
                    steps = direction
                    while not self.focus_queue.empty():
                        try:
                             steps += self.focus_queue.get_nowait()
                        except queue.Empty:
                            break
                    
                    if steps == 0: continue
                    
                    # 3. Execute Control (Actuator API: scan.cgi)
                    try:
                        # [Step 1] Read Current Position
                        # GET /scan.cgi?scan=3 (Assume this returns current state/form)
                        # We need 'scan=3' because user used it.
                        read_url = f"{URL_SPOT_ACTUATOR}?scan=3"
                        
                        # [Fix] Use Bytes Regex to avoid encoding issues (BOM, etc.)
                        resp_read = requests.get(read_url, timeout=3)
                        resp_content = resp_read.content
                        
                        # Pattern: ...<!--#Pos-->592... (Bytes)
                        match = re.search(rb'Pos-->\s*(\d+)', resp_content)
                        if not match:
                             # Fallback: Dump raw bytes
                             raise ValueError(f"Parse fail. Raw: {resp_content[:60]}")
                             
                        current_val = int(match.group(1).decode('ascii'))
                        
                        # [Step 2] Calculate New Position
                        delta = steps * SPOT_ACTUATOR_STEP
                        new_val = current_val + delta
                        new_val = max(0, min(1000, new_val)) # Clamp (Assume 0-1000 range based on 593)
                        
                        print(f"[Actuator] Steps: {steps} | {current_val} -> {new_val}")
                        
                        if new_val != current_val:
                            # [Step 3] Write New Position
                            # GET /scan.cgi?scan=3&move={new_val}
                            write_url = f"{URL_SPOT_ACTUATOR}?scan=3&move={new_val}"
                            
                            resp_write = requests.get(write_url, timeout=3)
                            
                            
                            if resp_write.status_code == 200:
                                 # Toast Success
                                 self.after(0, lambda: ToastNotification(self, f"Pos OK: {new_val} (Step: {SPOT_ACTUATOR_STEP})", duration=1000, color=COLOR_SUCCESS))
                            else:
                                 raise Exception(f"HTTP {resp_write.status_code}")
                        else:
                            self.after(0, lambda: ToastNotification(self, "Limit Reached", duration=1000, color=COLOR_WARNING))
                                
                    except Exception as e:
                        print(f"[Actuator] IO Error: {e}")
                        # Show error with URL context
                        err_str = f"[{read_url}] {e}"
                        if len(err_str) > 50: err_str = err_str[:50] + "..."
                        self.after(0, lambda: ToastNotification(self, f"Actuator Error: {err_str}", duration=4000, color=COLOR_DANGER))
                        
                    # Small delay
                    time.sleep(0.1)
                    
                except Exception as e:
                    print(f"[ActuatorWorker] Loop Error: {e}")
        except Exception as e:
             print(f"[ActuatorWorker] Fatal Error: {e}")



    def destroy(self):
        self.running = False
        try: self.session.close()
        except: pass
        super().destroy()

class SmartFactoryApp(ctk.CTk):
    def __init__(self, queue):
        super().__init__()
        self.queue = queue
        self.title("HOIHOU Smart Factory")
        self.geometry("1600x900")
        self.configure(fg_color=COLOR_BG)
        
        # [Icon] 작업표시줄 및 타이틀바 아이콘 적용 (PyInstaller 호환)
        import os, sys
        def resource_path(relative_path):
            """ Get absolute path to resource, works for dev and for PyInstaller """
            try:
                # PyInstaller creates a temp folder and stores path in _MEIxxxxxx
                base_path = sys._MEIPASS
            except Exception:
                base_path = os.path.abspath(".")
            return os.path.join(base_path, relative_path)

        try:
            icon_path = resource_path("assets/icon.ico")
            self.iconbitmap(icon_path)
        except Exception as e:
            print(f"Icon load failed: {e}")
                
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=0) # Status Bar
        self.grid_rowconfigure(1, weight=0) # Nav Bar
        self.grid_rowconfigure(2, weight=1) # Main Content

        self.last_data_time = datetime.now() # Watchdog timer

        self.setup_ui()
        
        # View Management
        self.current_view = "dashboard" # "dashboard" or "graph"
        self.btn_dashboard.configure(text_color=COLOR_ACCENT) # Active State visual (optional)
        
        self.check_queue()
        
# ... [StartLine 362 to EndLine 504 are unchanged, but we are replacing class definition wrapper if needed or just appending/modifying]
# Actually, let's just insert PasswordDialog before SmartFactoryApp and update open_settings. 
# Since I cannot easily insert a class in the middle without finding a good anchor, I will put it before SmartFactoryApp and update open_settings.

# However, replace_file_content is better for contiguous blocks.
# Let's Modify `open_settings` to use the new class, but we need to define the class first.
# I will define PasswordDialog at the top (after InfoCard) and then update open_settings.

# Wait, I can define PasswordDialog right before SmartFactoryApp or even as a nested class (helper).
# Let's put it before SmartFactoryApp.

# Strategy:
# 1. Insert PasswordDialog class before SmartFactoryApp.
# 2. Update open_settings in SmartFactoryApp.

# Multi-replace is better here.


    def open_notification_center(self):
        self.status_bar.toggle_badge(False)
        self.drawer.show()

    def show_diagnostics(self, event=None):
        pass

    def setup_ui(self):
        # === Header (Replaced by Status Bar) ===
        self.status_bar = StatusBar(self, height=38)
        self.status_bar.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.status_bar.update_clock()
        
        # === Drawer (Overlay) ===
        self.drawer = NotificationDrawer(self, width=320, height=450)
        # Link Bell Button
        self.status_bar.on_bell_callback = self.open_notification_center
        # Link Smart Buttons
        self.status_bar.btn_diag.configure(command=self.show_diagnostics)
        self.status_bar.on_settings_callback = self.open_settings
        
        # === Navigation / Sub-Header (Optional, kept for View Switching) ===
        self.nav_frame = ctk.CTkFrame(self, fg_color="transparent", height=40)
        self.nav_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=20, pady=(5, 0))
        
        self.btn_dashboard = ctk.CTkButton(self.nav_frame, text="🏭 창녕 2호기", font=(FONT_MAIN, 24, "bold"), 
                                           fg_color="transparent", hover_color="#222222", 
                                           command=lambda: self.switch_view("dashboard"))
        self.btn_dashboard.pack(side="left")
        
        self.btn_graph = ctk.CTkButton(self.nav_frame, text="📈 Time Series", font=(FONT_MAIN, 18), 
                                       fg_color="transparent", hover_color="#222222", text_color="gray",
                                       command=lambda: self.switch_view("graph"))
        self.btn_graph.pack(side="left", padx=(10, 0))

        # Settings Icon (Moved to Nav Frame or Status Bar? Plan said Status Bar, but keep here for access)
        # Actually Status Bar has placeholders. Let's redirect Status Bar buttons if needed.
        # But for P0, we just need basic integration.
        


        # === Views Container ===
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=2, column=0, columnspan=3, sticky="nsew") # Shifted to Row 2
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        # 1. Dashboard View
        self.view_dashboard = ctk.CTkFrame(self.container, fg_color="transparent")
        self.view_dashboard.grid(row=0, column=0, sticky="nsew")
        
        # [Fix] Expand Row 0 to fill vertical space
        self.view_dashboard.grid_rowconfigure(0, weight=1)
        self.view_dashboard.grid_columnconfigure(0, weight=1)
        self.view_dashboard.grid_columnconfigure(1, weight=1)
        self.view_dashboard.grid_columnconfigure(2, weight=1)

        # ... (Dashboard Content setup remains same) ...


        # === Column 1: KPIs ===
        self.col1 = ctk.CTkFrame(self.view_dashboard, fg_color=COLOR_PANEL, corner_radius=10)
        self.col1.grid(row=0, column=0, sticky="nsew", padx=5, pady=5) # Reduced 10->5
        
        lbl_kpi = ctk.CTkLabel(self.col1, text="⚡ PROCESS KPI", font=(FONT_MAIN, 24, "bold"), text_color=COLOR_TEXT_DIM)
        lbl_kpi.pack(anchor="w", pady=20, padx=20)
        CTkTooltip(lbl_kpi, "Key Process Indicators: Speed, Pressure, Count")
        
        self.speed_gauge = CircularGauge(self.col1, width=260, height=260, max_val=20, bg=COLOR_PANEL)
        self.speed_gauge.pack(pady=10)
        
        ctk.CTkLabel(self.col1, text="⏲️ Main Pressure", font=(FONT_MAIN, 20), text_color=COLOR_TEXT_DIM).pack(anchor="w", pady=(20, 5), padx=20)
        self.press_bar = ctk.CTkProgressBar(self.col1, orientation="horizontal", height=20, progress_color=COLOR_ACCENT)
        self.press_bar.set(0)
        self.press_bar.pack(fill="x", pady=(0, 5), padx=20)
        self.press_val = ctk.CTkLabel(self.col1, text="0.0 bar", font=(FONT_MAIN, 24, "bold"))
        self.press_val.pack(anchor="e", padx=20)
        
        self.card_count = InfoCard(self.col1, "📦 Prod Count", "0", "", value_size=42, height=90)
        self.card_count.pack(fill="x", pady=10, padx=20)
        self.card_endpos = InfoCard(self.col1, "📏 End Position", "0", "mm", value_size=42, height=90)
        self.card_endpos.pack(fill="x", pady=10, padx=20)

        # === Column 2: Temperatures ===
        self.col2 = ctk.CTkFrame(self.view_dashboard, fg_color=COLOR_PANEL, corner_radius=10)
        self.col2.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(self.col2, text="🌡️ TEMPERATURES", font=(FONT_MAIN, 24, "bold"), text_color=COLOR_TEXT_DIM).pack(anchor="w", pady=20, padx=20)
        
        self.card_spot = InfoCard(self.col2, "🎯 SPOT Temp (Product)", "0.0", "°C", color=COLOR_WARNING, title_size=24, value_size=78, height=145)
        self.card_spot.pack(fill="x", pady=20, padx=20)
        self.card_spot.add_button("🌍", lambda: webbrowser.open("http://10.1.10.60/index.ssi"), "Open Settings (Actuator)")
        self.card_spot.add_button("📷", lambda: webbrowser.open("http://10.1.10.50/image.ssi"), "Open Camera View")
        CTkTooltip(self.card_spot, "Infrared Sensor Reading (Non-contact)")
        
        self.frame_cont = ctk.CTkFrame(self.col2, fg_color="transparent")
        self.frame_cont.pack(fill="x", pady=10, padx=20)
        self.card_cont_f = InfoCard(self.frame_cont, "🔥 Cont. Front", "0", "°C", value_size=42, height=90)
        self.card_cont_f.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.card_cont_b = InfoCard(self.frame_cont, "🔥 Cont. Back", "0", "°C", value_size=42, height=90)
        self.card_cont_b.pack(side="right", fill="x", expand=True, padx=(10, 0))
        
        self.frame_billet = ctk.CTkFrame(self.col2, fg_color="transparent")
        self.frame_billet.pack(fill="x", pady=10, padx=20)
        self.card_billet_t = InfoCard(self.frame_billet, "🥖 Billet Temp", "0", "°C", value_size=42, height=90)
        self.card_billet_t.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.card_billet_l = InfoCard(self.frame_billet, "📏 Billet Length", "0", "mm", value_size=42, height=90)
        self.card_billet_l.pack(side="right", fill="x", expand=True, padx=(10, 0))

        # === Column 3: Molds & Env ===
        self.col3 = ctk.CTkFrame(self.view_dashboard, fg_color=COLOR_PANEL, corner_radius=10)
        self.col3.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(self.col3, text="⚙️ MOLDS & ENV", font=(FONT_MAIN, 24, "bold"), text_color=COLOR_TEXT_DIM).pack(anchor="w", pady=20, padx=20)
        
        self.mold_frame = ctk.CTkFrame(self.col3, fg_color="transparent")
        self.mold_frame.pack(fill="x", padx=15)
        self.mold_cards = []
        for i in range(6):
            card = InfoCard(self.mold_frame, f"🛡️ Mold {i+1}", "0", "°C", value_size=42, height=90)
            r, c = divmod(i, 2)
            card.grid(row=r, column=c, sticky="ew", padx=5, pady=5)
            self.mold_frame.grid_columnconfigure(c, weight=1)
            self.mold_cards.append(card)
            CTkTooltip(card, f"Mold Zone {i+1} Temperature")
            
        self.frame_env = ctk.CTkFrame(self.col3, fg_color="transparent")
        self.frame_env.pack(fill="x", pady=25, padx=20)
        self.card_at_temp = InfoCard(self.frame_env, "🏠 At Temp", "0.0", "°C", height=90, value_size=36)
        self.card_at_temp.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.card_at_pre = InfoCard(self.frame_env, "💧 At Pre", "0.0", "%", height=90, value_size=36)
        self.card_at_pre.pack(side="right", fill="x", expand=True, padx=(10, 0))

        # [NEW] Operator Notice Card (Enhanced Visibility)
        self.card_notice = ctk.CTkFrame(self.col3, fg_color=COLOR_CARD, corner_radius=12, border_width=2, border_color=COLOR_WARNING)
        self.card_notice.pack(fill="x", pady=(10, 20), padx=20)
        
        # Header
        notice_header = ctk.CTkFrame(self.card_notice, fg_color="transparent")
        notice_header.pack(fill="x", padx=20, pady=(15, 10))
        ctk.CTkLabel(notice_header, text="⚠️ OPERATOR CHECK", font=(FONT_MAIN, 22, "bold"), text_color=COLOR_WARNING).pack(side="left")
        
        # Body Content (Split for styling)
        content_frame = ctk.CTkFrame(self.card_notice, fg_color="transparent")
        content_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        # 1. Main Instruction
        ctk.CTkLabel(content_frame, text="적외선 센서 조준 상태를 상시 확인하십시오.", 
                     font=(FONT_MAIN, 18, "bold"), text_color="white", justify="left").pack(anchor="w", pady=(0, 5))
        
        # 2. Reasoning (Dimmed)
        ctk.CTkLabel(content_frame, text="※ 제품 위치 변동 시 온도가 측정되지 않을 수 있습니다.", 
                     font=(FONT_MAIN, 14), text_color="#aaaaaa", justify="left").pack(anchor="w", pady=(0, 10))
        
        # 3. Action Call (Highlighted)
        ctk.CTkLabel(content_frame, text="▶ 'SPOT Camera View' 화살표로\n    포인트 위치를 조정해 주세요.", 
                     font=(FONT_MAIN, 20, "bold"), text_color=COLOR_ACCENT, justify="left").pack(anchor="w")

        # [NEW] Camera Widget in Column 2 (Bottom)
        self.cam_frame = ctk.CTkFrame(self.col2, fg_color="transparent")
        self.cam_frame.pack(fill="both", expand=True, padx=20, pady=10)
        ctk.CTkLabel(self.cam_frame, text="📷 SPOT Camera View", font=(FONT_MAIN, 16, "bold"), text_color=COLOR_TEXT_DIM).pack(anchor="w", pady=(0, 5))
        
        # Use URL from config
        # [Resize] Configurable size from config.ini
        self.camera_widget = CameraWidget(self.cam_frame, url=URL_SPOT_IMAGE, width=SPOT_WIDGET_WIDTH, height=SPOT_WIDGET_HEIGHT)
        self.camera_widget.pack(anchor="center") # Center it instead of fill/expand to keep aspect ratio

        # 2. Time Series View (Lazy Load or Init now)
        self.view_graph = TimeSeriesPanel(self.container, fg_color="transparent")
        self.view_graph.grid(row=0, column=0, sticky="nsew")
        self.view_graph.grid_remove() # Hide initially

        # === Footer ===
        self.footer = ctk.CTkFrame(self, height=30, fg_color="#111111")
        self.footer.grid(row=3, column=0, columnspan=3, sticky="ew") # Shifted to Row 3
        self.log_lbl = ctk.CTkLabel(self.footer, text="System Ready.", font=(FONT_MONO, 12), text_color="gray")
        self.log_lbl.pack(side="left", padx=20)
        
        self.copyright_lbl = ctk.CTkLabel(self.footer, text="Copyright © HOIHOU. All Rights Reserved.", font=(FONT_MAIN, 12, "bold"), text_color="#555555")
        self.copyright_lbl.pack(side="right", padx=20)

    def switch_view(self, view_name):
        self.current_view = view_name
        
        if view_name == "dashboard":
            self.view_graph.grid_remove()
            self.view_dashboard.grid()
            self.btn_dashboard.configure(text_color=COLOR_ACCENT)
            self.btn_graph.configure(text_color="gray")
        else:
            self.view_dashboard.grid_remove()
            self.view_graph.grid()
            self.btn_dashboard.configure(text_color="gray")
            self.btn_graph.configure(text_color=COLOR_ACCENT)
    
    def check_queue(self):
        try:
            # [Optimization] Time-Budget Processing (10ms)
            start_time = time.time()
            while (time.time() - start_time) < 0.010: # 10ms budget
                # Support both Queue and Deque
                if hasattr(self.queue, 'empty') and self.queue.empty(): break
                if hasattr(self.queue, '__len__') and len(self.queue) == 0: break
                
                try:
                    if hasattr(self.queue, 'get_nowait'):
                        data = self.queue.get_nowait()
                    else:
                        data = self.queue.popleft() # Deque
                    self.update_ui(data)
                except: break
        except: pass
        
        # [UX] Connection Watchdog & Warning Retention
        # If we have a recent warning, keep it visible for at least 2 seconds
        is_warning_active = False
        if hasattr(self, 'warning_until') and datetime.now() < self.warning_until:
            is_warning_active = True
            
        if not is_warning_active:
            if (datetime.now() - self.last_data_time).total_seconds() > 3:
                # self.status_lbl.configure(text="● Disconnected", text_color=COLOR_DANGER)
                self.status_bar.set_status('Disconnected')
            else:
                # self.status_lbl.configure(text="● Running", text_color=COLOR_SUCCESS)
                self.status_bar.set_status('Running')
            
        self.after(100, self.check_queue)

    def update_ui(self, data):
        # [Watchdog Update] Alive Signal
        self.last_data_time = datetime.now()
        
        # [Error Handling]
        if 'error' in data:
            err = data['error']
            ToastNotification(self, f"System Error: {err}", duration=5000, color=COLOR_DANGER)
            # Self-healing status bar
            self.status_bar.set_status('Disconnected')
            self.status_bar.update_ticker(f"Error: {err}", is_error=True)
            self.drawer.add_notification("System Error", err, level="error")
            self.status_bar.toggle_badge(True)
            return

        # [Warning Handling] (Queue Full, etc)
        if 'warning' in data:
            msg = data['warning']
            # No Toast, just Status Label (Orange) as per plan
            # self.status_lbl.configure(text=f"● {msg}", text_color=COLOR_WARNING)
            self.status_bar.set_status('Degraded')
            self.status_bar.update_ticker(msg, is_error=False)
            self.drawer.add_notification("Warning", msg, level="warning")
            self.status_bar.toggle_badge(True)
            # Keep this status for 2 seconds

            self.warning_until = datetime.now() + datetime.timedelta(seconds=2)
            return

        # Latency Calculation
        latency = 0
        data_time = data.get('Time')
        if data_time:
            if isinstance(data_time, datetime):
                delta = datetime.now() - data_time
                latency = int(delta.total_seconds() * 1000)
            elif isinstance(data_time, str):
                # Try parse? Simplified: just 0 if str
                pass
        
        # Update Status Bar with Latency
        current_status_text = self.status_bar.lbl_status.cget("text") # Hacky check?
        # Better: determine status based on 'warning' flag in data or queue emptiness
        # But here running is default.
        if 'warning' not in data: # If warning exists, it was handled above.
             self.status_bar.set_status('Running', latency_ms=latency)

        
        # Speed
        speed = data.get('Speed', 0) or 0
        self.speed_gauge.set_value(float(speed))
        
        # Pressure
        press = data.get('Press', 0) or 0
        self.press_bar.set(min(1.0, float(press)/250.0))
        self.press_val.configure(text=f"{press} bar")
        
        self.card_count.update_value(data.get('Count', 0))
        self.card_endpos.update_value(data.get('EndPos', 0))
        
        # Spot
        spot = data.get('Spot', 0) or 0
        f_spot = float(spot)
        self.card_spot.update_value(f"{f_spot:.1f}")

        # [Logic] 4-Stage Color for SPOT Temp
        spot_color = COLOR_COLD
        if f_spot >= 550:
            spot_color = COLOR_HOT
            self.card_spot.set_status(2) # Danger Glow
        elif f_spot >= 500:
            spot_color = COLOR_SUCCESS
            self.card_spot.set_status(0)
        elif f_spot >= 450:
            spot_color = COLOR_WARNING # Yellow
            self.card_spot.set_status(1) # Warning Glow
        else:
            spot_color = COLOR_COLD # Blue
            self.card_spot.set_status(0)
        self.card_spot.update_value(f"{f_spot:.1f}", color=spot_color, status_color=spot_color)
        
        
        # [Logic] 4-Stage Color for Container Temps
        cont_f = data.get('Temp_F', 0)
        f_cont_f = float(cont_f)
        cont_f_color = COLOR_COLD
        if f_cont_f >= 450: 
            cont_f_color = COLOR_HOT
            self.card_cont_f.set_status(2)
        elif f_cont_f >= 400: 
            cont_f_color = COLOR_SUCCESS
            self.card_cont_f.set_status(0)
        elif f_cont_f >= 350: 
            cont_f_color = COLOR_WARNING
            self.card_cont_f.set_status(1)
        else:
            self.card_cont_f.set_status(0)
            
        self.card_cont_f.update_value(cont_f, color=cont_f_color, status_color=cont_f_color)

        cont_b = data.get('Temp_B', 0)
        f_cont_b = float(cont_b)
        cont_b_color = COLOR_COLD
        if f_cont_b >= 450: 
            cont_b_color = COLOR_HOT
            self.card_cont_b.set_status(2)
        elif f_cont_b >= 400: 
            cont_b_color = COLOR_SUCCESS
            self.card_cont_b.set_status(0)
        elif f_cont_b >= 350: 
            cont_b_color = COLOR_WARNING
            self.card_cont_b.set_status(1)
        else:
            self.card_cont_b.set_status(0)

        self.card_cont_b.update_value(cont_b, color=cont_b_color, status_color=cont_b_color)
        
        # [Logic] 4-Stage Color for Billet Temp
        billet_t = data.get('Billet_Temp', 0)
        f_billet_t = float(billet_t)
        billet_t_color = COLOR_COLD
        if f_billet_t >= 480: 
            billet_t_color = COLOR_HOT
            self.card_billet_t.set_status(2)
        elif f_billet_t >= 460: 
            billet_t_color = COLOR_SUCCESS
            self.card_billet_t.set_status(0)
        elif f_billet_t >= 440: 
            billet_t_color = COLOR_WARNING
            self.card_billet_t.set_status(1)
        else:
             self.card_billet_t.set_status(0)
        
        self.card_billet_t.update_value(billet_t, color=billet_t_color, status_color=billet_t_color)
        self.card_billet_l.update_value(data.get('Billet', 0))
        
        # Molds (Side Bar Color Logic)
        for i in range(6):
            val = data.get(f'Mold{i+1}', 0) or 0
            f_val = float(val)
            
            # 100도 미만: 파랑(Cold), 이상: 빨강(Hot)
            status_color = COLOR_COLD if f_val < 100 else COLOR_HOT
            self.mold_cards[i].update_value(val, status_color=status_color)
            
            self.mold_cards[i].update_value(val, status_color=status_color)
            
        # [Logic] Env Color & Text Logic
        # At Temp: <10 추움(Blue), 10-28 쾌적(Green), >28 더움(Red)
        at_temp = data.get('At_Temp', 0)
        f_at_temp = float(at_temp)
        at_temp_color = COLOR_SUCCESS
        at_temp_text = "쾌적"
        
        if f_at_temp >= 28:
            at_temp_color = COLOR_HOT
            at_temp_text = "더움"
        elif f_at_temp < 10:
            at_temp_color = COLOR_COLD
            at_temp_text = "추움"
            
        self.card_at_temp.update_value(f"{f_at_temp} ({at_temp_text})", color=at_temp_color)

        # At Pre (Humidity): <30 건조(Yellow), 30-60 쾌적(Green), >60 다습(Blue)
        at_pre = data.get('At_Pre', 0)
        f_at_pre = float(at_pre)
        at_pre_color = COLOR_SUCCESS
        at_pre_text = "쾌적"
        
        if f_at_pre >= 60:
            at_pre_color = COLOR_COLD # Blue for Humid
            at_pre_text = "다습"
        elif f_at_pre < 30:
            at_pre_color = COLOR_WARNING # Yellow for Dry
            at_pre_text = "건조"

        self.card_at_pre.update_value(f"{f_at_pre} ({at_pre_text})", color=at_pre_color)
        
        self.log_lbl.configure(text=f"Last Update: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
        
        
        # [Fix] Update Graph Data Buffers (Background Buffering)
        # Always send data to graph module so it maintains history even when hidden.
        # Graph module handles drawing optimization (only draws if visible/needed).
        self.view_graph.update_data(data)

    def show_diagnostics(self, event=None):
        win = ctk.CTkToplevel(self)
        win.title("Connection Diagnostics")
        win.geometry("400x350")
        win.attributes("-topmost", True)
        
        ctk.CTkLabel(win, text="System Health Check", font=("Segoe UI", 20, "bold")).pack(pady=15)
        
        time_diff = (datetime.now() - self.last_data_time).total_seconds()
        
        status_frame = ctk.CTkFrame(win)
        status_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        def add_row(parent, name, status, color):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=5)
            ctk.CTkLabel(row, text=name, font=("Segoe UI", 16)).pack(side="left", padx=10)
            ctk.CTkLabel(row, text=status, font=("Segoe UI", 16, "bold"), text_color=color).pack(side="right", padx=10)

        if time_diff < 5:
             add_row(status_frame, "Data Collection Loop", "Active", COLOR_SUCCESS)
             add_row(status_frame, "Extruder (Main)", "Receiving", COLOR_SUCCESS)
             add_row(status_frame, "LS PLC (Thermal)", "Receiving", COLOR_SUCCESS) 
             add_row(status_frame, "SPOT Sensor", "Receiving", COLOR_SUCCESS)
        else:
             add_row(status_frame, "Data Collection Loop", "Stalled / Offline", COLOR_DANGER)
             add_row(status_frame, "Extruder (Main)", "Unknown", COLOR_TEXT_DIM)
             add_row(status_frame, "LS PLC (Thermal)", "Unknown", COLOR_TEXT_DIM)
             add_row(status_frame, "SPOT Sensor", "Unknown", COLOR_TEXT_DIM)
             
        ctk.CTkLabel(win, text=f"Last Packet: {time_diff:.1f}s ago", text_color="gray").pack(pady=10)
        ctk.CTkButton(win, text="Close", command=win.destroy).pack(pady=10)

    def open_settings(self):
        # dialog = ctk.CTkInputDialog(text="Enter Password:", title="Authentication")
        # pw = dialog.get_input()
        dialog = PasswordDialog(self, expected_password=PASSWORD, title="Authentication")
        # pw = dialog.get_input()
        
        if dialog.is_verified():
            if hasattr(self, 'settings_window') and self.settings_window and self.settings_window.winfo_exists():
                self.settings_window.focus()
            else:
                self.settings_window = SettingsWindow(self)
        # elif pw is not None:
             # tk.messagebox.showerror("Error", "Incorrect Password")
