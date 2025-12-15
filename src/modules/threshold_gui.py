import customtkinter as ctk
import tkinter as tk

class ThresholdSettingsWindow(ctk.CTkToplevel):
    _last_geometry = None

    def __init__(self, master, current_thresholds, on_save_callback):
        super().__init__(master)
        self.title("Threshold Settings")
        
        if ThresholdSettingsWindow._last_geometry:
             self.geometry(ThresholdSettingsWindow._last_geometry)
        else:
             self.geometry("400x600")
             
        self.resizable(False, True)
        self.attributes("-topmost", True)
        
        self.on_save_callback = on_save_callback
        self.thresholds = current_thresholds.copy() # Local copy
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # 1. Master Toggle
        self.frame_top = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_top.pack(fill="x", padx=20, pady=20)
        
        self.lbl_master = ctk.CTkLabel(self.frame_top, text="Show Threshold Lines", font=("Segoe UI", 16, "bold"))
        self.lbl_master.pack(side="left")
        
        self.switch_master = ctk.CTkSwitch(self.frame_top, text="", onvalue=True, offvalue=False)
        self.switch_master.pack(side="right")
        
        # Load Master State
        master_state = self.thresholds.get("MASTER_ON", False)
        if master_state: self.switch_master.select()
        else: self.switch_master.deselect()
        
        # 2. Scrollable Area for Items
        self.scroll = ctk.CTkScrollableFrame(self, label_text="Individual Thresholds")
        self.scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        self.entries = {}
        self.checks = {}
        
        # Data Keys (Should match graph_view keys)
        # We can pass keys or hardcode widely used ones. 
        # Better to keys passed in thresholds or hardcoded list if keys allow customization.
        # graph_view keys: Spot, Press, Billet, Temp_F, Temp_B, Count, Speed, EndPos, Billet_Temp, At_Pre, At_Temp
        
        self.items = [
            ('Speed', 'Extruder Speed'),
            ('Press', 'Extruder Pressure'),
            ('Spot', 'Spot Temp'),
            ('Temp_F', 'Front Temp'),
            ('Temp_B', 'Back Temp'),
            ('Billet', 'Billet Length'),
            ('Billet_Temp', 'Billet Temp'),
            ('At_Temp', 'Ambient Temp'),
            ('At_Pre', 'Ambient Pres'),
            ('Count', 'Product Count'),
            ('EndPos', 'End Position')
        ]
        
        for i, (key, label) in enumerate(self.items):
            row_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
            row_frame.pack(fill="x", pady=5)
            
            # Label
            ctk.CTkLabel(row_frame, text=label, width=120, anchor="w").pack(side="left")
            
            # Value Entry
            entry = ctk.CTkEntry(row_frame, width=80, placeholder_text="Limit")
            entry.pack(side="left", padx=10)
            
            # Load existing val
            existing = self.thresholds.get(key, {})
            if existing.get("value"):
                entry.insert(0, str(existing["value"]))
            
            self.entries[key] = entry
            
            # Enable Checkbox (Individual Toggle)
            chk = ctk.CTkCheckBox(row_frame, text="Enable", width=60)
            chk.pack(side="right")
            if existing.get("enabled", False):
                chk.select()
            else:
                chk.deselect()
            self.checks[key] = chk

        # 3. Footer Buttons
        self.frame_bot = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_bot.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkButton(self.frame_bot, text="Save & Apply", command=self.save_and_close, fg_color="#4ec9b0").pack(side="right", padx=5)
        ctk.CTkButton(self.frame_bot, text="Cancel", command=self.destroy, fg_color="#555555").pack(side="right", padx=5)
        
    def on_close(self):
        ThresholdSettingsWindow._last_geometry = self.geometry()
        self.destroy()

    def save_and_close(self):
        # Save Geometry
        ThresholdSettingsWindow._last_geometry = self.geometry()
        
        # Save Master
        self.thresholds["MASTER_ON"] = bool(self.switch_master.get())
        
        # Save Items
        for key, _ in self.items:
            try:
                val_str = self.entries[key].get().strip()
                val = float(val_str) if val_str else None
                enabled = bool(self.checks[key].get())
                
                self.thresholds[key] = {
                    "value": val,
                    "enabled": enabled
                }
            except ValueError:
                # Invalid number, ignore or disable
                self.thresholds[key] = {"value": None, "enabled": False}
        
        if self.on_save_callback:
            self.on_save_callback(self.thresholds)
            
        self.destroy()
