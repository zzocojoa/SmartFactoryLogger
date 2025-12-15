import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import configparser
import os
import sys
from config import CONFIG_FILE, IP_EXT, PORT_EXT, IP_LS, PORT_LS, IP_SPOT, LOG_PATH, PASSWORD, SNAPSHOT_PATH

class SettingsWindow(ctk.CTkToplevel):
    _last_geometry = None

    def __init__(self, master):
        super().__init__(master)
        self.title("Settings")
        
        if SettingsWindow._last_geometry:
            self.geometry(SettingsWindow._last_geometry)
        else:
            self.geometry("600x500")
            
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.grab_set() # 모달 창으로 설정 (뒤 화면 클릭 방지)

        self.config = configparser.ConfigParser()
        self.config.read(CONFIG_FILE, encoding='utf-8')
        
        self.setup_ui()
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Escape>", self.on_close)
        self.bind("<Return>", self.save_settings)
        
    def setup_ui(self):
        # 탭 뷰 생성
        self.tabview = ctk.CTkTabview(self, width=580, height=420)
        self.tabview.pack(padx=10, pady=10)
        
        # 탭 추가
        self.tab_conn = self.tabview.add("📡 Connection")
        self.tab_store = self.tabview.add("💾 Storage")
        self.tab_sys = self.tabview.add("🔒 System")
        self.tab_snap = self.tabview.add("📷 Snapshot") # [Added]
        self.tab_ext = self.tabview.add("➕ Extended") # Future use
        
        self.setup_connection_tab()
        self.setup_storage_tab()
        self.setup_snapshot_tab() # [Added]
        self.setup_system_tab()
        
        # 하단 저장 버튼
        self.btn_save = ctk.CTkButton(self, text="Save & Close", command=self.save_settings, 
                                      fg_color="#4ec9b0", hover_color="#3ea890")
        self.btn_save.pack(side="bottom", pady=15)

    def setup_connection_tab(self):
        # Extruder
        lbl_ext = ctk.CTkLabel(self.tab_conn, text="[ Extruder ]", font=("Segoe UI", 16, "bold"))
        lbl_ext.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(self.tab_conn, text="IP Address:").grid(row=1, column=0, sticky="w", padx=20, pady=5)
        self.entry_ext_ip = ctk.CTkEntry(self.tab_conn, width=200)
        self.entry_ext_ip.grid(row=1, column=1, sticky="w", padx=10)
        self.entry_ext_ip.insert(0, self.config.get("EXTRUDER Sensor", "IP", fallback=IP_EXT))
        self.entry_ext_ip.bind("<FocusOut>", lambda e: self.on_validate(self.entry_ext_ip, "ip"))
        
        ctk.CTkLabel(self.tab_conn, text="Port:").grid(row=2, column=0, sticky="w", padx=20, pady=5)
        self.entry_ext_port = ctk.CTkEntry(self.tab_conn, width=100)
        self.entry_ext_port.grid(row=2, column=1, sticky="w", padx=10)
        self.entry_ext_port.insert(0, self.config.get("EXTRUDER", "Port", fallback=str(PORT_EXT)))
        self.entry_ext_port.bind("<FocusOut>", lambda e: self.on_validate(self.entry_ext_port, "port"))
        
        # LS PLC
        lbl_ls = ctk.CTkLabel(self.tab_conn, text="[ Thermal & Env. ]", font=("Segoe UI", 16, "bold"))
        lbl_ls.grid(row=3, column=0, sticky="w", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(self.tab_conn, text="IP Address:").grid(row=4, column=0, sticky="w", padx=20, pady=5)
        self.entry_ls_ip = ctk.CTkEntry(self.tab_conn, width=200)
        self.entry_ls_ip.grid(row=4, column=1, sticky="w", padx=10)
        self.entry_ls_ip.insert(0, self.config.get("LS_PLC", "IP", fallback=IP_LS))
        self.entry_ls_ip.bind("<FocusOut>", lambda e: self.on_validate(self.entry_ls_ip, "ip"))
        
        ctk.CTkLabel(self.tab_conn, text="Port:").grid(row=5, column=0, sticky="w", padx=20, pady=5)
        self.entry_ls_port = ctk.CTkEntry(self.tab_conn, width=100)
        self.entry_ls_port.grid(row=5, column=1, sticky="w", padx=10)
        self.entry_ls_port.insert(0, self.config.get("LS_PLC", "Port", fallback=str(PORT_LS)))
        self.entry_ls_port.bind("<FocusOut>", lambda e: self.on_validate(self.entry_ls_port, "port"))
        
        # SPOT
        lbl_spot = ctk.CTkLabel(self.tab_conn, text="[ SPOT Sensor ]", font=("Segoe UI", 16, "bold"))
        lbl_spot.grid(row=6, column=0, sticky="w", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(self.tab_conn, text="IP Address:").grid(row=7, column=0, sticky="w", padx=20, pady=5)
        self.entry_spot_ip = ctk.CTkEntry(self.tab_conn, width=200)
        self.entry_spot_ip.grid(row=7, column=1, sticky="w", padx=10)
        self.entry_spot_ip.insert(0, self.config.get("SPOT", "IP", fallback=IP_SPOT))
        self.entry_spot_ip.bind("<FocusOut>", lambda e: self.on_validate(self.entry_spot_ip, "ip"))

    def setup_storage_tab(self):
        lbl_store = ctk.CTkLabel(self.tab_store, text="[ Log Storage Path ]", font=("Segoe UI", 16, "bold"))
        lbl_store.pack(anchor="w", padx=20, pady=(20, 10))
        
        frame_path = ctk.CTkFrame(self.tab_store, fg_color="transparent")
        frame_path.pack(fill="x", padx=20)
        
        self.entry_path = ctk.CTkEntry(frame_path, width=350)
        self.entry_path.pack(side="left", fill="x", expand=True)
        self.entry_path.insert(0, self.config.get("SETTINGS", "LogPath", fallback=LOG_PATH))
        
        btn_browse = ctk.CTkButton(frame_path, text="...", width=40, command=self.browse_folder)
        btn_browse.pack(side="left", padx=10)
        
        # [NEW] Auto Save Toggle
        self.switch_autosave = ctk.CTkSwitch(self.tab_store, text="Automatic CSV Save", 
                                             font=("Segoe UI", 14), 
                                             onvalue=True, offvalue=False)
        self.switch_autosave.pack(anchor="w", padx=20, pady=(20, 5))
        
        # Load value (Need to handle string "True"/"False" from config manually if not using ConfigParser's getboolean inside GUI logic heavily, 
        # but here we use config object directly)
        is_auto_save = self.config.getboolean("SETTINGS", "AutoSave", fallback=True)
        if is_auto_save:
            self.switch_autosave.select()
        else:
            self.switch_autosave.deselect()

        # --- [Cycle Logging Settings] ---
        # Separator
        ctk.CTkFrame(self.tab_store, height=2, fg_color="gray").pack(fill="x", padx=20, pady=10)
        
        lbl_cycle = ctk.CTkLabel(self.tab_store, text="[ Cycle Logging (Billet Split) ]", font=("Segoe UI", 16, "bold"))
        lbl_cycle.pack(anchor="w", padx=20, pady=(5, 10))

        # Toggle Billet Splitting
        self.switch_billet = ctk.CTkSwitch(self.tab_store, text="Pressure-Triggered Log Split",
                                           font=("Segoe UI", 14),
                                           command=self.toggle_billet_settings)
        self.switch_billet.pack(anchor="w", padx=20, pady=5)
        
        # Determine initial state
        current_mode = self.config.get("LOGGING", "RotationMode", fallback="DAILY")
        if current_mode == "BILLET":
            self.switch_billet.select()
        else:
            self.switch_billet.deselect()

        # Detailed Settings Frame
        self.frame_billet = ctk.CTkFrame(self.tab_store, fg_color="transparent")
        self.frame_billet.pack(fill="x", padx=40, pady=5)

        # Idle Time
        ctk.CTkLabel(self.frame_billet, text="Idle Time (sec):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.entry_idle = ctk.CTkEntry(self.frame_billet, width=80)
        self.entry_idle.grid(row=0, column=1, sticky="w", padx=5)
        self.entry_idle.insert(0, self.config.get("LOGGING", "CycleIdleTime", fallback="10"))
        
        # Threshold
        ctk.CTkLabel(self.frame_billet, text="Start Threshold (bar):").grid(row=0, column=2, sticky="w", padx=(20, 5), pady=5)
        self.entry_thres = ctk.CTkEntry(self.frame_billet, width=80)
        self.entry_thres.grid(row=0, column=3, sticky="w", padx=5)
        self.entry_thres.insert(0, self.config.get("LOGGING", "CycleThresholdPress", fallback="20.0"))
        
        # Initialize UI State
        self.toggle_billet_settings()
            
        ctk.CTkLabel(self.tab_store, text="* Changes will take effect after restart.", text_color="orange").pack(anchor="w", padx=20, pady=10)

    def toggle_billet_settings(self):
        if self.switch_billet.get() == 1:
            self.entry_idle.configure(state="normal")
            self.entry_thres.configure(state="normal")
        else:
            self.entry_idle.configure(state="disabled")
            self.entry_thres.configure(state="disabled")

    # ... [browse_folder unchanged] ...

    def browse_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.entry_path.delete(0, tk.END)
            self.entry_path.insert(0, path)

    def setup_system_tab(self):
        lbl_sys = ctk.CTkLabel(self.tab_sys, text="[ System Security ]", font=("Segoe UI", 16, "bold"))
        lbl_sys.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(self.tab_sys, text="Change Password:").grid(row=1, column=0, sticky="w", padx=20, pady=5)
        
        # 비밀번호 입력 및 토글 버튼을 위한 프레임
        pw_frame = ctk.CTkFrame(self.tab_sys, fg_color="transparent")
        pw_frame.grid(row=1, column=1, sticky="w", padx=10)
        
        self.entry_pw = ctk.CTkEntry(pw_frame, width=150, show="*")
        self.entry_pw.pack(side="left")
        self.entry_pw.insert(0, self.config.get("SETTINGS", "Password", fallback=PASSWORD))
        
        self.btn_toggle_pw = ctk.CTkButton(pw_frame, text="👁️", width=30, command=self.toggle_password_visibility,
                                           fg_color="transparent", hover_color="#444444", text_color="white")
        self.btn_toggle_pw.pack(side="left", padx=(5, 0))

        # Log Viewer Button
        ctk.CTkLabel(self.tab_sys, text="System Logs:").grid(row=2, column=0, sticky="w", padx=20, pady=(20, 5))
        self.btn_logs = ctk.CTkButton(self.tab_sys, text="📄 View Recent Logs", command=self.view_recent_logs,
                                      fg_color="#3B8ED0", hover_color="#36719F")
        self.btn_logs.grid(row=2, column=1, sticky="w", padx=10, pady=(20, 5))

    def toggle_password_visibility(self):
        if self.entry_pw.cget("show") == "*":
            self.entry_pw.configure(show="")
            self.btn_toggle_pw.configure(text="🚫") # 감추기 아이콘
        else:
            self.entry_pw.configure(show="*")
            self.btn_toggle_pw.configure(text="👁️") # 보이기 아이콘

    def on_close(self, event=None):
        SettingsWindow._last_geometry = self.geometry()
        self.grab_release()
        self.destroy()

    def on_validate(self, entry, type_):
        val = entry.get()
        valid = True
        if type_ == "ip":
            parts = val.split(".")
            if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                valid = False
        elif type_ == "port":
            if not val.isdigit() or not (1 <= int(val) <= 65535):
                valid = False
        
        if not valid:
            entry.configure(border_color="red")
        else:
            entry.configure(border_color=["#979da2", "#565b5e"]) # Default colors

    def setup_snapshot_tab(self):
        lbl_snap = ctk.CTkLabel(self.tab_snap, text="[ Snapshot Save Path ]", font=("Segoe UI", 16, "bold"))
        lbl_snap.pack(anchor="w", padx=20, pady=(20, 10))
        
        frame_path = ctk.CTkFrame(self.tab_snap, fg_color="transparent")
        frame_path.pack(fill="x", padx=20)
        
        self.entry_snap_path = ctk.CTkEntry(frame_path, width=350)
        self.entry_snap_path.pack(side="left", fill="x", expand=True)
        self.entry_snap_path.insert(0, self.config.get("SETTINGS", "SnapshotPath", fallback=SNAPSHOT_PATH))
        
        btn_browse_snap = ctk.CTkButton(frame_path, text="...", width=40, command=self.browse_snap_folder)
        btn_browse_snap.pack(side="left", padx=10)
        
        ctk.CTkLabel(self.tab_snap, text="* Default: ./snapshots in project folder", text_color="gray").pack(anchor="w", padx=20, pady=10)

    def browse_snap_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.entry_snap_path.delete(0, tk.END)
            self.entry_snap_path.insert(0, path)

    def view_recent_logs(self):
        log_path = self.config.get("SETTINGS", "LogPath", fallback="logs")
        if not os.path.isabs(log_path):
             log_path = os.path.join(BASE_DIR, log_path)
             
        if not os.path.exists(log_path):
            messagebox.showerror("Error", f"Log path does not exist:\n{log_path}")
            return
            
        try:
            files = [os.path.join(log_path, f) for f in os.listdir(log_path) 
                     if f.startswith("Factory_Integrated_Log_") and f.endswith(".csv")]
            
            if not files:
                messagebox.showinfo("Info", "No log files found.")
                return
                
            latest_file = max(files, key=os.path.getmtime)
            
            with open(latest_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                last_20 = lines[-20:] if len(lines) > 20 else lines
                content = "".join(last_20)
                
            # Log Viewer Window
            log_win = ctk.CTkToplevel(self)
            log_win.title(f"Log Viewer - {os.path.basename(latest_file)}")
            log_win.geometry("800x400")
            
            textbox = ctk.CTkTextbox(log_win, font=("Consolas", 12))
            textbox.pack(fill="both", expand=True, padx=10, pady=10)
            textbox.insert("0.0", content)
            textbox.configure(state="disabled") # Read-only
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read log file: {e}")

    def save_settings(self, event=None):
        SettingsWindow._last_geometry = self.geometry()
        
        # Update Config Object
        if not self.config.has_section("SETTINGS"): self.config.add_section("SETTINGS")
        if not self.config.has_section("EXTRUDER"): self.config.add_section("EXTRUDER")
        if not self.config.has_section("LS_PLC"): self.config.add_section("LS_PLC")
        if not self.config.has_section("SPOT"): self.config.add_section("SPOT")
        
        # Connection
        self.config.set("EXTRUDER", "IP", self.entry_ext_ip.get())
        self.config.set("EXTRUDER", "Port", self.entry_ext_port.get())
        
        self.config.set("LS_PLC", "IP", self.entry_ls_ip.get())
        self.config.set("LS_PLC", "Port", self.entry_ls_port.get())
        
        self.config.set("SPOT", "IP", self.entry_spot_ip.get())
        
        # Storage
        self.config.set("SETTINGS", "LogPath", self.entry_path.get())
        
        # Snapshot
        self.config.set("SETTINGS", "SnapshotPath", self.entry_snap_path.get())
        
        # [NEW] Check Auto Save Toggle
        auto_save_val = "True" if self.switch_autosave.get() == 1 else "False" # CTkSwitch returns 1 or 0 usually or configured values
        # Actually in CTkSwitch, get() returns the value (True/False if configured with onvalue/offvalue, or 1/0 default)
        # We configured onvalue=True, offvalue=False.
        self.config.set("SETTINGS", "AutoSave", str(self.switch_autosave.get()))
        
        # System
        self.config.set("SETTINGS", "Password", self.entry_pw.get())
        
        # [NEW] Cycle Logging
        if not self.config.has_section("LOGGING"): self.config.add_section("LOGGING")
        
        rotation_mode = "BILLET" if self.switch_billet.get() == 1 else "DAILY"
        self.config.set("LOGGING", "RotationMode", rotation_mode)
        self.config.set("LOGGING", "CycleIdleTime", self.entry_idle.get())
        self.config.set("LOGGING", "CycleThresholdPress", self.entry_thres.get())
        
        # Write to file
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as configfile:
                self.config.write(configfile)
            
            # Use Local Import to avoid circular dependency
            from modules.ui_utils import ToastNotification
            if self.master:
                # [Fix] Delay destroy to process button events
                self.after(100, lambda: self._safe_close_with_toast(ToastNotification))
            else:
                self.after(50, self.destroy)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def _safe_close_with_toast(self, ToastClass):
        if not self.winfo_exists(): return
        try:
             ToastClass(self.master, "설정이 저장되었습니다. 변경 사항을 적용하려면 프로그램을 재시작하세요.", duration=5000)
        except: pass
        self.destroy()

    def on_close(self, event=None):
        SettingsWindow._last_geometry = self.geometry()
        self.grab_release()
        try: self.master.focus_set()
        except: pass
        self.destroy()
