
import customtkinter as ctk
import tkinter as tk
from datetime import datetime
import collections
from config import COLOR_BG, COLOR_PANEL, COLOR_CARD, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_ACCENT, COLOR_WARNING, COLOR_DANGER, COLOR_SUCCESS, FONT_MAIN
from modules.ui_utils import CTkTooltip, ToastNotification

class StatusBar(ctk.CTkFrame):
    def __init__(self, master, height=38, **kwargs):
        super().__init__(master, height=height, fg_color="#2d2d2d", corner_radius=0, **kwargs)
        self.pack_propagate(False)
        self.grid_propagate(False)
        
        # Left Accent Stripe (Visual Status Indicator)
        self.status_stripe = ctk.CTkFrame(self, width=5, fg_color=COLOR_SUCCESS, corner_radius=0)
        self.status_stripe.pack(side="left", fill="y")
        
        # 1. Left Section: System Status
        self.left_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.left_frame.pack(side="left", padx=10, fill="y")
        
        self.lbl_status = ctk.CTkLabel(self.left_frame, text="Running", font=(FONT_MAIN, 14, "bold"), text_color=COLOR_TEXT)
        self.lbl_status.pack(side="left", pady=5)
        
        self.lbl_latency = ctk.CTkLabel(self.left_frame, text="0ms", font=(FONT_MAIN, 12), text_color=COLOR_TEXT_DIM)
        self.lbl_latency.pack(side="left", padx=(8, 0), pady=6)
        
        # 2. Center Section: Rolling Notification (Ticker)
        self.center_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.center_frame.pack(side="left", expand=True, fill="both", padx=20)
        
        self.lbl_ticker = ctk.CTkLabel(self.center_frame, text="", font=(FONT_MAIN, 13), text_color="#dddddd")
        self.lbl_ticker.place(relx=0.5, rely=0.5, anchor="center")

        # 3. Right Section: Controls & Info
        self.right_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.right_frame.pack(side="right", padx=10, fill="y")
        
        # Smart Action Buttons (Hidden by default)
        self.btn_reconnect = ctk.CTkButton(self.right_frame, text="🔌 Reconnect", width=90, height=24, 
                                           fg_color=COLOR_DANGER, hover_color="#cc0000", font=(FONT_MAIN, 11, "bold"))
        # Initially hidden
        
        self.btn_diag = ctk.CTkButton(self.right_frame, text="🩺 Diagnosis", width=80, height=24,
                                      fg_color=COLOR_WARNING, hover_color="#cc8800", text_color="black", font=(FONT_MAIN, 11, "bold"))
        # Initially hidden
        
        # Bell Icon with Badge
        self.bell_container = ctk.CTkFrame(self.right_frame, fg_color="transparent", width=30, height=30)
        self.bell_container.pack(side="left", padx=(5, 10))
        
        self.btn_bell = ctk.CTkButton(self.bell_container, text="🔔", width=30, height=30, 
                                      fg_color="transparent", hover_color="#444444", 
                                      font=("Segoe UI Emoji", 16),
                                      command=self.on_bell_click)
        self.btn_bell.place(relx=0.5, rely=0.5, anchor="center")
        
        # Red Badge (Hidden)
        self.badge = ctk.CTkLabel(self.bell_container, text="●", text_color=COLOR_DANGER, font=("Arial", 16), bg_color="transparent")
        # badge.place(relx=0.7, rely=0.2, anchor="center")
        
        # Clock
        self.lbl_clock = ctk.CTkLabel(self.right_frame, text="00:00:00", font=("Consolas", 14, "bold"), text_color=COLOR_TEXT_DIM)
        self.lbl_clock.pack(side="left", padx=10)
        
        # Storage Icon (Disk I/O)
        self.lbl_storage = ctk.CTkLabel(self.right_frame, text="💾", font=("Segoe UI Emoji", 14), text_color="gray")
        self.lbl_storage.pack(side="left", padx=5)

        # Settings Button
        self.btn_settings = ctk.CTkButton(self.right_frame, text="⚙️", width=30, height=30, 
                                          fg_color="transparent", hover_color="#444444", 
                                          font=("Arial", 16), command=self.on_settings_click)
        self.btn_settings.pack(side="left", padx=5)
        
        # Callbacks
        self.on_bell_callback = None
        self.on_settings_callback = None
        self.last_ticker_update = datetime.now()

    def on_settings_click(self):
        if self.on_settings_callback:
            self.on_settings_callback()

    def set_status(self, status, latency_ms=None):
        """
        status: 'Running' | 'Degraded' | 'Disconnected'
        """
        color = COLOR_SUCCESS
        text = "Running"
        
        if status == 'Degraded':
            color = COLOR_WARNING
            text = "Warning"
        elif status == 'Disconnected':
            color = COLOR_DANGER
            text = "Disconnected"
            
        self.status_stripe.configure(fg_color=color)
        self.lbl_status.configure(text=text, text_color="white" if status=='Disconnected' else COLOR_TEXT)
        
        if latency_ms is not None:
             self.lbl_latency.configure(text=f"{latency_ms}ms")
             # High latency warning
             if latency_ms > 200: self.lbl_latency.configure(text_color=COLOR_WARNING)
             else: self.lbl_latency.configure(text_color=COLOR_TEXT_DIM)
             
        if status == 'Disconnected':
            if not self.btn_reconnect.winfo_ismapped():
                self.btn_reconnect.pack(side="left", padx=5, before=self.bell_container)
            if not self.btn_diag.winfo_ismapped():
                self.btn_diag.pack(side="left", padx=5, before=self.bell_container)
        elif status == 'Degraded':
            if self.btn_reconnect.winfo_ismapped():
                self.btn_reconnect.pack_forget()
            if not self.btn_diag.winfo_ismapped():
                self.btn_diag.pack(side="left", padx=5, before=self.bell_container)
        else:
            if self.btn_reconnect.winfo_ismapped():
                self.btn_reconnect.pack_forget()
            if self.btn_diag.winfo_ismapped():
                self.btn_diag.pack_forget()

    def update_ticker(self, message, is_error=False):
        # Only update if enough time passed or priority message
        # Simple implementation: just update
        self.lbl_ticker.configure(text=message)
        self.lbl_ticker.configure(text_color=COLOR_DANGER if is_error else "#dddddd")

    def toggle_badge(self, visible):
        if visible:
            self.badge.place(relx=0.8, rely=0.3, anchor="center")
        else:
            self.badge.place_forget()

    def update_clock(self):
        now = datetime.now().strftime("%H:%M:%S")
        self.lbl_clock.configure(text=now)
        self.after(1000, self.update_clock)

    def on_bell_click(self):
        if self.on_bell_callback:
            self.on_bell_callback()


class NotificationDrawer(ctk.CTkFrame):
    def __init__(self, master, width=300, height=400, **kwargs):
        super().__init__(master, width=width, height=height, fg_color="#222222", corner_radius=10, border_width=1, border_color="#444444", **kwargs)
        self.pack_propagate(False)
        self.grid_propagate(False)
        
        # Header
        self.header = ctk.CTkFrame(self, height=40, fg_color="#333333", corner_radius=0)
        self.header.pack(fill="x", side="top")
        
        ctk.CTkLabel(self.header, text="🔔 Notification History", font=(FONT_MAIN, 14, "bold")).pack(side="left", padx=10, pady=8)
        
        self.btn_close = ctk.CTkButton(self.header, text="✕", width=30, height=30, fg_color="transparent", hover_color="#555555", command=self.hide)
        self.btn_close.pack(side="right", padx=5)
        
        # List Container (Scrollable)
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.notifications = collections.deque(maxlen=20)

    def add_notification(self, title, message, level="info"):
        """
        level: 'info' | 'warning' | 'error'
        """
        ts = datetime.now().strftime("%H:%M:%S")
        item = {
            "ts": ts,
            "title": title,
            "msg": message,
            "level": level
        }
        self.notifications.appendleft(item)
        self.refresh_list()

    def refresh_list(self):
        # Clear current
        for widget in self.scroll.winfo_children():
            widget.destroy()
            
        # Draw items
        for note in self.notifications:
            self.draw_item(note)
            
    def draw_item(self, note):
        # Frame
        color_map = {
            "info": "#444444",
            "warning": COLOR_WARNING,
            "error": COLOR_DANGER
        }
        border = color_map.get(note["level"], "#444444")
        
        card = ctk.CTkFrame(self.scroll, fg_color="#2b2b2b", border_width=0, corner_radius=6)
        card.pack(fill="x", pady=2)
        
        # Left Stripe
        stripe = ctk.CTkFrame(card, width=4, fg_color=border, corner_radius=0)
        stripe.pack(side="left", fill="y")
        
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True, padx=8, pady=5)
        
        # Title Row
        row1 = ctk.CTkFrame(content, fg_color="transparent")
        row1.pack(fill="x")
        ctk.CTkLabel(row1, text=note["title"], font=(FONT_MAIN, 12, "bold"), text_color="white").pack(side="left")
        ctk.CTkLabel(row1, text=note["ts"], font=("Consolas", 10), text_color="gray").pack(side="right")
        
        # Message
        ctk.CTkLabel(content, text=note["msg"], font=(FONT_MAIN, 11), text_color="gray", wraplength=240, justify="left").pack(anchor="w", mt=2)

    def show(self):
        # Should be placed by parent
        self.lift()
        self.place(relx=1.0, rely=0.06, anchor="ne", x=-10) # Position below Status Bar

    def hide(self):
        self.place_forget()
