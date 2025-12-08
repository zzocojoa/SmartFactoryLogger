import customtkinter as ctk
import tkinter as tk

class ToastNotification(ctk.CTkToplevel):
    def __init__(self, master, message, duration=2000):
        super().__init__(master)
        self.message = message
        self.duration = duration
        
        # Remove title bar
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        
        # Transparent background effect (pseudo)
        self.configure(fg_color="#333333")
        
        # Label
        self.lbl = ctk.CTkLabel(self, text=message, font=("Segoe UI", 14), text_color="white", padx=20, pady=10)
        self.lbl.pack()
        
        # Position logic (Bottom Center of Master)
        self.update_idletasks()
        try:
            m_x = master.winfo_rootx()
            m_y = master.winfo_rooty()
            m_w = master.winfo_width()
            m_h = master.winfo_height()
            
            w = self.winfo_reqwidth()
            h = self.winfo_reqheight()
            
            x = m_x + (m_w // 2) - (w // 2)
            y = m_y + m_h - h - 50 # 50px padding from bottom
            
            self.geometry(f"+{x}+{y}")
        except:
             # Fallback
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            self.geometry(f"+{sw//2}+{sh-100}")

        # Fade out animation start
        self.after(duration, self.fade_out)
        
    def fade_out(self):
        try:
            alpha = self.attributes("-alpha")
            if alpha > 0:
                alpha -= 0.1
                self.attributes("-alpha", alpha)
                self.after(50, self.fade_out)
            else:
                self.destroy()
        except:
            self.destroy()

class CTkTooltip:
    def __init__(self, widget, text, delay=500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tooltip_window = None
        self.id = None
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)
        
    def on_enter(self, event=None):
        self.id = self.widget.after(self.delay, self.show_tooltip)
        
    def on_leave(self, event=None):
        self.hide_tooltip()
        
    def show_tooltip(self):
        if self.tooltip_window or not self.text:
            return
        
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(self.tooltip_window, text=self.text, justify='left',
                         background="#ffffe0", relief='solid', borderwidth=1,
                         font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)
        
    def hide_tooltip(self):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

def draw_dashed_line(draw, start, end, fill="red", width=1, dash=(5, 5)):
    """
    PIL ImageDraw에 점선을 그리는 함수
    dash=(선 길이, 공백 길이)
    """
    import math
    x0, y0 = start
    x1, y1 = end
    dx, dy = x1 - x0, y1 - y0
    dist = math.sqrt(dx**2 + dy**2)
    if dist == 0: return
    
    dash_len, gap_len = dash
    step_x = dx / dist
    step_y = dy / dist
    
    curr_dist = 0
    while curr_dist < dist:
        e_dist = min(curr_dist + dash_len, dist)
        s_x = x0 + step_x * curr_dist
        s_y = y0 + step_y * curr_dist
        e_x = x0 + step_x * e_dist
        e_y = y0 + step_y * e_dist
        draw.line((s_x, s_y, e_x, e_y), fill=fill, width=width)
        curr_dist += dash_len + gap_len
