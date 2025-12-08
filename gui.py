# gui.py
import customtkinter as ctk
import tkinter as tk
import math
import webbrowser
from datetime import datetime
from config import COLOR_BG, COLOR_PANEL, COLOR_CARD, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_ACCENT, COLOR_WARNING, COLOR_DANGER, COLOR_SUCCESS, COLOR_COLD, COLOR_HOT, PASSWORD
from settings_gui import SettingsWindow
from modules.ui_utils import CTkTooltip, ToastNotification

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
    def __init__(self, master, title, value="--", unit="", color=COLOR_SUCCESS, title_size=14, value_size=28, **kwargs):
        super().__init__(master, fg_color=COLOR_CARD, corner_radius=8, **kwargs) # 각진 모서리 (Modern)
        
        # 사이드 바 (상태 표시줄)
        self.side_bar = ctk.CTkFrame(self, width=6, fg_color=COLOR_CARD, corner_radius=0) # 초기엔 숨김(배경색과 동일)
        self.side_bar.pack(side="left", fill="y", padx=(0, 10))
        
        # 컨텐츠 영역
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        
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
            self.destroy()
        else:
            self.lbl_error.configure(text="Incorrect Password")
            self.entry.delete(0, 'end')
            # Shake animation or focus
            self.entry.focus_set()

    def on_cancel(self):
        PasswordDialog._last_geometry = self.geometry()
        self.destroy()

    def is_verified(self):
        return self.verified

class SmartFactoryApp(ctk.CTk):
    def __init__(self, queue):
        super().__init__()
        self.queue = queue
        self.title("Smart Factory Logger - Line 1 Final")
        self.geometry("1600x900")
        self.configure(fg_color=COLOR_BG)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.last_data_time = datetime.now() # Watchdog timer

        self.setup_ui()
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


    def setup_ui(self):
        # === Header ===
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.grid(row=0, column=0, columnspan=3, sticky="ew", padx=30, pady=15)
        
        ctk.CTkLabel(self.header, text="🏭 창녕 2호기", font=(FONT_MAIN, 32, "bold"), text_color="white").pack(side="left")
        
        # 구분선 (Vertical Separator)
        ctk.CTkFrame(self.header, width=2, height=30, fg_color="#444444").pack(side="left", padx=20)
        
        self.clock_lbl = ctk.CTkLabel(self.header, text="00:00:00", font=(FONT_MONO, 28), text_color=COLOR_TEXT_DIM)
        self.clock_lbl.pack(side="left")

        # Settings Button (Gear) -> Right side
        self.btn_settings = ctk.CTkButton(self.header, text="⚙️", width=40, height=40, font=("Arial", 20),
                                          fg_color="transparent", hover_color="#333333", command=self.open_settings)
        self.btn_settings.pack(side="right", padx=(10, 0))
        CTkTooltip(self.btn_settings, "Settings & Configuration")
        
        self.status_lbl = ctk.CTkLabel(self.header, text="● Running", font=(FONT_MAIN, 18), text_color=COLOR_SUCCESS)
        self.status_lbl.pack(side="right")
        self.status_lbl.bind("<Button-1>", self.show_diagnostics)
        self.status_lbl.configure(cursor="hand2")
        CTkTooltip(self.status_lbl, "System Status: Click for details")

        # === Column 1: KPIs ===
        self.col1 = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=10)
        self.col1.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
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
        
        self.card_count = InfoCard(self.col1, "📦 Prod Count", "0", "", value_size=42)
        self.card_count.pack(fill="x", pady=10, padx=20)
        self.card_endpos = InfoCard(self.col1, "📏 End Position", "0", "mm", value_size=42)
        self.card_endpos.pack(fill="x", pady=10, padx=20)

        # === Column 2: Temperatures ===
        self.col2 = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=10)
        self.col2.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)
        
        ctk.CTkLabel(self.col2, text="🌡️ TEMPERATURES", font=(FONT_MAIN, 24, "bold"), text_color=COLOR_TEXT_DIM).pack(anchor="w", pady=20, padx=20)
        
        self.card_spot = InfoCard(self.col2, "🎯 SPOT Temp (Product)", "0.0", "°C", color=COLOR_WARNING, title_size=24, value_size=78)
        self.card_spot.pack(fill="x", pady=20, padx=20)
        self.card_spot.add_button("🌍", lambda: webbrowser.open("http://10.1.10.60/index.ssi"), "Open Settings (Actuator)")
        self.card_spot.add_button("📷", lambda: webbrowser.open("http://10.1.10.50/image.ssi"), "Open Camera View")
        CTkTooltip(self.card_spot, "Infrared Sensor Reading (Non-contact)")
        
        self.frame_cont = ctk.CTkFrame(self.col2, fg_color="transparent")
        self.frame_cont.pack(fill="x", pady=10, padx=20)
        self.card_cont_f = InfoCard(self.frame_cont, "🔥 Cont. Front", "0", "°C", value_size=42)
        self.card_cont_f.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.card_cont_b = InfoCard(self.frame_cont, "🔥 Cont. Back", "0", "°C", value_size=42)
        self.card_cont_b.pack(side="right", fill="x", expand=True, padx=(10, 0))
        
        self.frame_billet = ctk.CTkFrame(self.col2, fg_color="transparent")
        self.frame_billet.pack(fill="x", pady=10, padx=20)
        self.card_billet_t = InfoCard(self.frame_billet, "🥖 Billet Temp", "0", "°C", value_size=42)
        self.card_billet_t.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.card_billet_l = InfoCard(self.frame_billet, "📏 Billet Length", "0", "mm", value_size=42)
        self.card_billet_l.pack(side="right", fill="x", expand=True, padx=(10, 0))

        # === Column 3: Molds & Env ===
        self.col3 = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=10)
        self.col3.grid(row=1, column=2, sticky="nsew", padx=10, pady=10)
        
        ctk.CTkLabel(self.col3, text="⚙️ MOLDS & ENV", font=(FONT_MAIN, 24, "bold"), text_color=COLOR_TEXT_DIM).pack(anchor="w", pady=20, padx=20)
        
        self.mold_frame = ctk.CTkFrame(self.col3, fg_color="transparent")
        self.mold_frame.pack(fill="x", padx=15)
        self.mold_cards = []
        for i in range(6):
            card = InfoCard(self.mold_frame, f"🛡️ Mold {i+1}", "0", "°C", value_size=42)
            r, c = divmod(i, 2)
            card.grid(row=r, column=c, sticky="ew", padx=5, pady=5)
            self.mold_frame.grid_columnconfigure(c, weight=1)
            self.mold_cards.append(card)
            CTkTooltip(card, f"Mold Zone {i+1} Temperature")
            
        self.frame_env = ctk.CTkFrame(self.col3, fg_color="transparent")
        self.frame_env.pack(fill="x", pady=25, padx=20)
        self.card_at_temp = InfoCard(self.frame_env, "🏠 At Temp", "0.0", "°C")
        self.card_at_temp.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.card_at_pre = InfoCard(self.frame_env, "💧 At Pre", "0.0", "")
        self.card_at_pre.pack(side="right", fill="x", expand=True, padx=(10, 0))

        # === Footer ===
        self.footer = ctk.CTkFrame(self, height=30, fg_color="#111111")
        self.footer.grid(row=2, column=0, columnspan=3, sticky="ew")
        self.log_lbl = ctk.CTkLabel(self.footer, text="System Ready.", font=(FONT_MONO, 12), text_color="gray")
        self.log_lbl.pack(side="left", padx=20)
        
        self.copyright_lbl = ctk.CTkLabel(self.footer, text="Created by HOIHOU", font=(FONT_MAIN, 12, "bold"), text_color="#555555")
        self.copyright_lbl.pack(side="right", padx=20)

    def check_queue(self):
        try:
            while not self.queue.empty():
                data = self.queue.get_nowait()
                self.update_ui(data)
        except: pass
        
        # Connection Watchdog
        if (datetime.now() - self.last_data_time).total_seconds() > 3:
            self.status_lbl.configure(text="● Disconnected", text_color=COLOR_DANGER)
        else:
            self.status_lbl.configure(text="● Running", text_color=COLOR_SUCCESS)
            
        self.after(100, self.check_queue)

    def update_ui(self, data):
        self.last_data_time = datetime.now()
        self.clock_lbl.configure(text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
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
        self.card_spot.update_value(f"{spot:.1f}")
        
        self.card_cont_f.update_value(data.get('Temp_F', 0))
        self.card_cont_b.update_value(data.get('Temp_B', 0))
        self.card_billet_t.update_value(data.get('Billet_Temp', 0))
        self.card_billet_l.update_value(data.get('Billet', 0))
        
        # Molds (Side Bar Color Logic)
        for i in range(6):
            val = data.get(f'Mold{i+1}', 0) or 0
            f_val = float(val)
            
            # 100도 미만: 파랑(Cold), 이상: 빨강(Hot)
            status_color = COLOR_COLD if f_val < 100 else COLOR_HOT
            self.mold_cards[i].update_value(val, status_color=status_color)
            
        self.card_at_temp.update_value(data.get('At_Temp', 0))
        self.card_at_pre.update_value(data.get('At_Pre', 0))
        
        self.log_lbl.configure(text=f"Last Update: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")

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
            SettingsWindow(self)
        # elif pw is not None:
             # tk.messagebox.showerror("Error", "Incorrect Password")
