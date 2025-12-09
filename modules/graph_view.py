import customtkinter as ctk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from datetime import datetime
import collections
import time 
import os
import configparser # [Persistence]
from config import SNAPSHOT_PATH, THRESHOLDS_CONFIG, CONFIG_FILE # [Persistence]
from modules.threshold_gui import ThresholdSettingsWindow
from modules.ui_utils import ToastNotification 

class TimeSeriesPanel(ctk.CTkFrame):
    def __init__(self, master, visible_points=1200, **kwargs):
        super().__init__(master, **kwargs)
        self.visible_points = visible_points
        self.timestamps = collections.deque(maxlen=visible_points)
        
        # 11 Data Channels
        self.data_keys = [
            'Spot', 'Press', 'Billet', 'Temp_F', 'Temp_B', 
            'Count', 'Speed', 'EndPos', 'Billet_Temp', 'At_Pre', 'At_Temp'
        ]
        
        # Initialize Buffers
        self.data_buffers = {key: collections.deque(maxlen=visible_points) for key in self.data_keys}
        
        # Line Objects Store
        self.lines = {}
        self.legend_labels = {} 
        self.base_labels = {} 

        # Cursor Markers
        self.cursors = {} 
        self.vline = None 

        # Matplotlib Figure
        plt.style.use('dark_background')
        self.fig = Figure(figsize=(10, 8), dpi=100)
        self.fig.patch.set_facecolor('#2b2b2b')
        
        self.ax1 = self.fig.add_subplot(111) 
        
        # Blitting Background Storage
        self.bg = None
        
        # Thresholds Config loaded from config.py
        self.thresholds = THRESHOLDS_CONFIG.copy()
        self.hlines = {} # Store line objects
        # Track last data values
        self.last_values = {key: 0.0 for key in self.data_keys}
        self.is_hovering = False
        
        # Performance Throttling
        self.last_draw_time = 0.0
        self.draw_interval = 0.05 # 20 FPS Cap (Limit redraws)
        
        self.setup_plots()
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.draw()
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill="both", expand=True)

        # [Fix] Force redraw when tab becomes visible to prevent "Jump" artifacts
        self.bind('<Map>', self.on_map)
        
        # Overlay Buttons (Snapshot & Settings)
        self.setup_overlay_buttons()

        # Interactive Legend & Cursor
        self.fig.canvas.mpl_connect('pick_event', self.on_pick)
        self.fig.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        
        # [Blitting] Capture background on resize/draw
        self.cid_draw = self.fig.canvas.mpl_connect('draw_event', self.on_draw)

    def setup_overlay_buttons(self):
        # Place buttons on bottom-right of the graph frame
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.place(relx=0.98, rely=0.98, anchor="se")
        
        self.btn_snap = ctk.CTkButton(btn_frame, text="📷", width=40, height=30, 
                                      fg_color="#444444", hover_color="#666666",
                                      command=self.save_snapshot)
        self.btn_snap.pack(side="right", padx=5)
        
        self.btn_set = ctk.CTkButton(btn_frame, text="⚙️", width=40, height=30,
                                     fg_color="#444444", hover_color="#666666",
                                     command=self.open_threshold_settings)
        self.btn_set.pack(side="right", padx=5)

    def save_snapshot(self):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"Snapshot_{timestamp}.png"
            
            # Use Variable Path
            if not os.path.exists(SNAPSHOT_PATH):
                try: os.makedirs(SNAPSHOT_PATH)
                except: pass
                
            path = os.path.join(SNAPSHOT_PATH, filename)
            
            # Save visible extent
            self.fig.savefig(path, facecolor=self.fig.get_facecolor(), dpi=100)
            
            # Show toast
            if self.winfo_toplevel():
                ToastNotification(self.winfo_toplevel(), f"Snapshot Saved: {filename}")
        except Exception as e:
            print(f"Snapshot Failed: {e}")

    def open_threshold_settings(self):
        ThresholdSettingsWindow(self.winfo_toplevel(), self.thresholds, self.on_threshold_save)

    def on_threshold_save(self, new_thresholds):
        self.thresholds = new_thresholds
        
        # Update HLines
        master_on = self.thresholds.get("MASTER_ON", False)
        
        for key, line in self.hlines.items():
            cfg = self.thresholds.get(key, {})
            val = cfg.get("value")
            enabled = cfg.get("enabled", False)
            
            if master_on and enabled and val is not None:
                line.set_ydata([val, val])
                
                # Assign color matching the data line
                base_line = self.lines.get(key)
                if base_line:
                    line.set_color(base_line.get_color())
                
                # Visibility logic is handled in draw loop based on graph visibility
                # But we can set initial visibility here if graph line is visible
                # Actually, check_visibility updates this every frame or mouse move?
                # Let's do a draw_idle because Thresholds changed
            else:
                line.set_visible(False)
        
        self.canvas.draw_idle()

        # [Persistence] Save to config.ini
        try:
            cfg = configparser.ConfigParser()
            cfg.read(CONFIG_FILE, encoding='utf-8')
            
            if not cfg.has_section("THRESHOLDS_VALUE"): cfg.add_section("THRESHOLDS_VALUE")
            if not cfg.has_section("THRESHOLDS_ENABLE"): cfg.add_section("THRESHOLDS_ENABLE")
            
            # Save Master
            cfg.set("THRESHOLDS_ENABLE", "MASTER_ON", str(new_thresholds.get("MASTER_ON", False)))
            
            for key, data in new_thresholds.items():
                if key == "MASTER_ON": continue
                
                valid_val = data.get("value")
                enabled = data.get("enabled", False)
                
                # Write Value (None -> Empty string)
                val_str = str(valid_val) if valid_val is not None else ""
                cfg.set("THRESHOLDS_VALUE", key, val_str)
                
                # Write Enable
                cfg.set("THRESHOLDS_ENABLE", key, str(enabled))
                
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                cfg.write(f)
                
            print("[Thresholds] Saved to config.ini")
            
        except Exception as e:
            print(f"[Thresholds] Save Error: {e}")

    def setup_plots(self):
        items = [
            ('Spot', 'Spot', '#ffff00', 1.0),
            ('Press', 'Press', '#ff00ff', 0.8),
            ('Billet', 'BillLen', '#cccccc', 0.5),
            ('Temp_F', 'ConF', '#ff8800', 0.5),
            ('Temp_B', 'ConB', '#ff4400', 0.5),
            ('Count', 'Cnt', '#ffffff', 0.5),
            ('EndPos', 'EndP', '#8888ff', 0.5),
            ('Billet_Temp', 'BillT', '#00ffff', 0.8),
            ('At_Pre', 'AtPre', '#0088ff', 0.5),
            ('At_Temp', 'AtTmp', '#00ff88', 0.5),
            ('Speed', 'Spd', '#00ff00', 1.0)
        ]

        for key, label, color, lw in items:
            line, = self.ax1.plot([], [], label=label, color=color, linewidth=lw, alpha=0.9, animated=True)
            self.lines[key] = line
            self.base_labels[key] = label
            
            # Cursor marker (animated)
            marker, = self.ax1.plot([], [], marker='o', color=color, markersize=6, visible=False, animated=True)
            self.cursors[key] = marker

        # Vertical cursor (animated)
        self.vline = self.ax1.axvline(x=0, color='white', linestyle='--', alpha=0.5, visible=False, animated=True)

        # Initialize hidden threshold lines (Dashed)
        for key in self.data_keys:
             # We use animated=False usually for static lines.
             hline = self.ax1.axhline(y=0, color='white', linestyle='--', linewidth=1, alpha=0.7, visible=False)
             self.hlines[key] = hline

        self.ax1.set_ylabel('Value', color='#dddddd')
        self.ax1.tick_params(axis='y', colors='#dddddd')
        self.ax1.grid(True, linestyle='--', alpha=0.3)
        
        self.ax1.set_xlim(0, self.visible_points) 
        self.ax1.set_ylim(0, 1200)

        # [Custom Legend Layout]
        self.setup_custom_legend()
        
        # Adjust margins to account for custom legend at top
        self.fig.subplots_adjust(left=0.08, right=0.95, top=0.88, bottom=0.1) 

    def setup_custom_legend(self):
        # [Memory Optimization] Cleanup previous artists
        if hasattr(self, 'custom_artists'):
            for artist in self.custom_artists:
                try: artist.remove()
                except: pass
        self.custom_artists = []
        
        # Clear existing texts if any
        self.legend_labels = {} 
        self.legend_lines = [] 
        self.leg_map = {} 
        
        # 1. Spot (Left 1/3, Large)
        key = 'Spot'
        if key in self.lines:
            color = self.lines[key].get_color()
            label = self.base_labels[key]
            orig_line = self.lines[key]
            
            # Draw Line (Color Bar)
            line_x = 0.1
            line_y = 0.95
            line_len = 0.03
            
            l = Line2D([line_x, line_x + line_len], [line_y, line_y], 
                       transform=self.fig.transFigure, color=color, linewidth=4)
            l.set_picker(10) 
            self.fig.add_artist(l) 
            self.custom_artists.append(l) # Track
            self.leg_map[l] = orig_line
            
            # Text (White/Gray)
            t = self.fig.text(line_x + line_len + 0.01, line_y + 0.01, f"{label} --", 
                              color='#dddddd', fontsize=24, fontweight='bold',
                              va='top', ha='left')
            t.set_picker(5) 
            self.legend_labels[key] = t
            self.custom_artists.append(t) # Track
            self.leg_map[t] = orig_line

        # 2. Others (Right 2/3, 2 Rows Grid)
        row1_keys = ['Press', 'Billet', 'Temp_F', 'Temp_B', 'Count']
        row2_keys = ['EndPos', 'Billet_Temp', 'At_Pre', 'At_Temp', 'Speed']
        
        start_x = 0.32
        col_width = 0.13
        line_len = 0.025
        
        y_row1 = 0.965
        y_row2 = 0.925
        
        font_props = {'fontsize': 12, 'fontweight': 'bold', 'va': 'center', 'ha': 'left'}

        def add_item(k, cx, cy):
            if k in self.lines:
                c = self.lines[k].get_color()
                lbl = self.base_labels[k]
                orig_line_ref = self.lines[k]
                
                # Line
                l = Line2D([cx, cx + line_len], [cy, cy], 
                           transform=self.fig.transFigure, color=c, linewidth=3)
                l.set_picker(10) 
                self.fig.add_artist(l) 
                self.custom_artists.append(l) # Track
                self.leg_map[l] = orig_line_ref
                
                # Text
                t = self.fig.text(cx + line_len + 0.005, cy, f"{lbl} --", color='#cccccc', **font_props)
                t.set_picker(5) 
                self.legend_labels[k] = t
                self.custom_artists.append(t) # Track
                self.leg_map[t] = orig_line_ref

        for i, k in enumerate(row1_keys):
            add_item(k, start_x + (i * col_width), y_row1)

        for i, k in enumerate(row2_keys):
            add_item(k, start_x + (i * col_width), y_row2) 

    def on_draw(self, event):
        """Called whenever the canvas is fully redrawn (e.g. resize). Capture background."""
        if event is not None and event.canvas != self.fig.canvas:
            return
        self.bg = self.fig.canvas.copy_from_bbox(self.fig.bbox)
        # Note: We do NOT draw animated artists here, they will be drawn in next update loop or if we explicitly call drawing logic.
        # But Matplotlib 'draw' calls draw everything usually unless 'animated=True' is set.
        # Since we set animated=True, lines are NOT drawn during standard draw().
        # We must manually draw them once? Or trust the loop.
        # Actually for initial view, we might need to draw them once.
        self._draw_animated()

    def _draw_animated(self):
        """Draw all animated artists and blit."""
        if self.bg is None: return
        
        # 1. Restore background
        self.fig.canvas.restore_region(self.bg)
        
        # 2. Draw animated artists
        for line in self.lines.values():
            if line.get_visible():
               self.ax1.draw_artist(line)
        
        if self.vline.get_visible():
            self.ax1.draw_artist(self.vline)
            
        for marker in self.cursors.values():
            if marker.get_visible():
                self.ax1.draw_artist(marker)
                
        # 3. Blit
        self.fig.canvas.blit(self.fig.bbox)
        self.fig.canvas.flush_events()

    def on_pick(self, event):
        artist = event.artist
        # Lookup original data line from the clicked legend artist (Text or Line2D)
        orig_line = self.leg_map.get(artist)
        
        if orig_line:
            # Toggle visibility
            vis = not orig_line.get_visible()
            orig_line.set_visible(vis)
            
            # Update Cursor Visibility to match
            for key, line in self.lines.items():
                if line == orig_line:
                    c = self.cursors.get(key)
                    if c: c.set_visible(vis and self.is_hovering)
                    break

            # Update Legend Appearance (Dim if hidden)
            for leg_artist, linked_line in self.leg_map.items():
                if linked_line == orig_line:
                    leg_artist.set_alpha(1.0 if vis else 0.3)
            
            # Force redraw to show changes
            self.canvas.draw_idle()

    def on_mouse_move(self, event):
        if not event.inaxes:
            if self.is_hovering:
                self.is_hovering = False
                self.vline.set_visible(False)
                for marker in self.cursors.values():
                    marker.set_visible(False)
                self.update_legend_text(self.last_values)
                self._draw_animated() # Fast update (Blit)
            return

        self.is_hovering = True
        x = int(event.xdata)
        
        if x < 0 or x >= len(self.timestamps):
             return
             
        self.vline.set_xdata([x, x])
        self.vline.set_visible(True)
        
        hover_values = {}
        for key in self.data_keys:
            if len(self.data_buffers[key]) > x:
                val = self.data_buffers[key][x]
                hover_values[key] = val
                
                marker = self.cursors[key]
                if self.lines[key].get_visible():
                    marker.set_data([x], [val])
                    marker.set_visible(True)
                else:
                    marker.set_visible(False)
        
        self.update_legend_text(hover_values)
        self._draw_animated() # Fast update (Blit)

    def update_legend_text(self, values_dict):
        master_on = self.thresholds.get("MASTER_ON", False)
        
        # 1. Update Threshold Lines Visibility based on Data Line Visibility
        # This function is called frequently (hover or data update), good place to sync visibility
        if master_on:
            for key, hline in self.hlines.items():
                cfg = self.thresholds.get(key, {})
                enabled = cfg.get("enabled", False)
                line_vis = self.lines[key].get_visible()
                
                if enabled and line_vis and cfg.get("value") is not None:
                    hline.set_visible(True)
                else:
                    hline.set_visible(False)
        else:
             for hline in self.hlines.values(): hline.set_visible(False)

        # 2. Update Text & Alert
        for key, val in values_dict.items():
            if key in self.legend_labels:
                base = self.base_labels[key]
                f_val = float(val)
                val_str = f"{int(f_val)}" if f_val > 100 else f"{f_val:.1f}"
                
                # Alert Check
                cfg = self.thresholds.get(key, {})
                limit = cfg.get("value")
                is_alert = False
                
                if cfg.get("enabled", False) and limit is not None:
                     if f_val > limit:
                         is_alert = True
                
                # Check visibility
                is_visible = self.lines[key].get_visible()
                
                if is_visible:
                    if is_alert:
                        self.legend_labels[key].set_text(f"{base} {val_str} ⚠️")
                        self.legend_labels[key].set_color("#ff4444") # Red Alert
                        self.legend_labels[key].set_alpha(1.0)
                    else:
                        self.legend_labels[key].set_text(f"{base} {val_str}")
                        self.legend_labels[key].set_color("#dddddd")
                        self.legend_labels[key].set_alpha(1.0)
                else:
                    # Hidden (Dimmed)
                    self.legend_labels[key].set_text(f"{base} {val_str}")
                    self.legend_labels[key].set_color("#dddddd")
                    self.legend_labels[key].set_alpha(0.3) 

    def on_map(self, event):
        """Called when the widget becomes visible (mapped). Force a full redraw."""
        self.canvas.draw_idle()
        
    def update_data(self, data_packet):
        timestamp_obj = data_packet.get('Time') 
        if timestamp_obj:
            if isinstance(timestamp_obj, datetime):
                current_time = timestamp_obj.strftime("%H:%M:%S")
            else:
                 current_time = str(timestamp_obj).split(' ')[-1]
        else:
            current_time = datetime.now().strftime("%H:%M:%S")
            
        self.timestamps.append(current_time)
        
        max_val_in_view = 0.0 
        
        for key in self.data_keys:
            val = data_packet.get(key)
            try:
                f_val = float(val) if val is not None and val != "" else 0.0
            except:
                f_val = 0.0
            
            self.data_buffers[key].append(f_val)
            self.last_values[key] = f_val 
            
            if f_val > max_val_in_view:
                max_val_in_view = f_val

        now = time.time()
        if now - self.last_draw_time < self.draw_interval:
            return  
            
        self.last_draw_time = now
        
        x_data = range(len(self.timestamps))
        
        for key, line in self.lines.items():
            if line.get_visible():
                line.set_data(x_data, self.data_buffers[key])
        
        if max_val_in_view > 1200:
             self.ax1.set_ylim(0, max_val_in_view * 1.1) 
             # Y-axis changed: Must do Full Redraw to update ticks/grid
             self.canvas.draw_idle()
             return 
        else:
             self.ax1.set_ylim(0, 1200) 
        
        # X-Axis Labels also change every frame -> Full Redraw needed for X-axis?
        # If we Blit, we restore background (which has old X-ticks).
        # So blinking X-ticks?
        # Ideally, Blitting is best for FIXED axes where only lines move.
        # Here X-ticks move (timestamps).
        # So Blitting might not be suitable for X-axis labels unless we exclude X-axis from background or redraw it.
        # Standard optimization for scrolling graph: 
        # 1. Strip charts (just shift data) -> Fast.
        # 2. But we have timestamps.
        # If we use Blitting, we won't update X-axis labels! They will be frozen or disappear.
        # Correct.
        # So for this specific use case (Moving X-Axis Labels), Blitting Full Figure is hard.
        # BUT, we can just Blit the lines and keep X-labels static? No, user wants timestamps.
        # Compromise: Update X-labels every 1 sec? (Throttled X-axis).
        # OR: Just accept full redraw but optimize by limiting FPS (which we did).
        # The user asked for optimization.
        # Let's stick to FPS throttling (which is implemented) and maybe optimizing 'draw_idle' overhead?
        # Actually, standard Blit does NOT update ticks.
        # So I will remove Blitting logic for X-axis update frames, BUT use it for Mouse Hover (Cursor)?
        # Mouse Hover does NOT change X-axis. So Blitting is PERFECT for Cursor.
        # Data Update -> Full Draw (Throttled).
        # Mouse Move -> Blit (Fast!).
        # This is the hybrid approach.
        
        if len(self.timestamps) > 0:
            tick_indices = range(0, self.visible_points + 1, 200)
            labels = []
            for i in tick_indices:
                if i < len(self.timestamps):
                    labels.append(self.timestamps[i])
                else:
                    labels.append("")
            
            self.ax1.set_xticks(list(tick_indices))
            self.ax1.set_xticklabels(labels, rotation=0, fontsize='small')
            
        if not self.is_hovering:
            self.update_legend_text(self.last_values)
        
        # Full Redraw for Data Update (because axes/labels change)
        self.canvas.draw_idle()
