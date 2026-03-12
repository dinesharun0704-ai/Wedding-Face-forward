import sys
import os
import subprocess
import threading
import time
import multiprocessing
from pathlib import Path
from datetime import datetime
import webbrowser

BASE_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(FRONTEND_DIR))

try:
    import customtkinter as ctk
except ImportError:
    print("CustomTkinter not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"])
    import customtkinter as ctk

import tkinter as tk
import math
from PIL import Image, ImageTk, ImageFilter, ImageEnhance

from app.config import get_config
from app.db import get_db


# =============================================================================
# Color Theme - Design Guide Palette
# =============================================================================
COLORS = {
    "bg":              ("#f5f5f7", "#1c1c1e"),       # Soft grey / Dark
    "bg_card":         ("#ffffff", "#2c2c2e"),
    "border":          ("#e8e8ed", "#38383a"),
    "accent":          ("#007aff", "#0a84ff"),
    "success":         ("#34c759", "#30d158"),
    "warning":         ("#ff9500", "#ff9f0a"),
    "error":           ("#ff3b30", "#ff453a"),
    "text_primary":    ("#1d1d1f", "#f5f5f7"),
    "text_secondary":  ("#86868b", "#98989d"),
    # Modern card styling
    "stat_bg":         ("#f0f0f5", "#2c2c2e"),       # Soft neutral / dark variant
    "stat_highlight":  ("#e8eaf6", "#33335a"),       # Soft lavender / dark variant
    "thick_border":    ("#e0e0e5", "#444446"),        # Soft subtle borders
    "log_outer":       ("#1e1e2e", "#1a1a2e"),       # Deep slate for log bg
    "log_inner":       ("#141422", "#111120"),        # Deep dark for terminal
}


# =============================================================================
# Animated Status Indicator
# =============================================================================
class StatusIndicator(ctk.CTkFrame):
    """Animated status dot with label."""
    
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        self.dot = ctk.CTkLabel(self, text="●", font=("Segoe UI", 12), text_color=COLORS["text_secondary"])
        self.dot.pack(side="left", padx=(0, 6))
        
        self.label = ctk.CTkLabel(self, text="Stopped", font=("Segoe UI", 13), text_color=COLORS["text_secondary"])
        self.label.pack(side="left")
        
        self._pulsing = False
        self._pulse_step = 0
    
    def set_running(self):
        self._pulsing = True
        self.label.configure(text="Running", text_color=COLORS["success"])
        self._pulse()
    
    def set_starting(self):
        self._pulsing = True
        self.label.configure(text="Starting...", text_color=COLORS["warning"])
        self._pulse()
    
    def set_stopping(self):
        self._pulsing = True
        self.label.configure(text="Stopping...", text_color=COLORS["warning"])
        self._pulse()
    
    def set_stopped(self):
        self._pulsing = False
        self.dot.configure(text_color=COLORS["text_secondary"])
        self.label.configure(text="Stopped", text_color=COLORS["text_secondary"])
    
    def _pulse(self):
        if not self._pulsing:
            return
        
        colors = [COLORS["success"], ("#5fd47a", "#4cd964"), COLORS["success"], ("#2aa64a", "#248a3d")]
        if "Stopping" in self.label.cget("text") or "Starting" in self.label.cget("text"):
            colors = [COLORS["warning"], ("#ffaa33", "#ffb340"), COLORS["warning"], ("#cc7700", "#d98816")]
        
        self.dot.configure(text_color=colors[self._pulse_step % len(colors)])
        self._pulse_step += 1
        
        self.after(400, self._pulse)


# =============================================================================
# System Health Indicator (All Workers Status)
# =============================================================================
class SystemHealthIndicator(ctk.CTkFrame):
    """Shows overall system health: green = all idle, red/orange = workers busy."""
    
    def __init__(self, parent):
        super().__init__(
            parent, 
            fg_color=COLORS["bg_card"], 
            corner_radius=20,
            border_width=1,
            border_color=COLORS["border"]
        )
        
        # Inner container for padding
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(padx=12, pady=6)
        
        self.dot = ctk.CTkLabel(inner, text="●", font=("Segoe UI", 14), text_color=COLORS["text_secondary"])
        self.dot.pack(side="left", padx=(0, 8))
        
        self.label = ctk.CTkLabel(
            inner, text="System Idle", 
            font=("Segoe UI", 11, "bold"), 
            text_color=COLORS["text_secondary"]
        )
        self.label.pack(side="left")
        
        self._state = "offline"  # "offline", "idle", or "busy"
        self._pulsing = False
        self._pulse_step = 0
        self._scale = 1.0
        self._target_scale = 1.0
    
    def set_idle(self):
        """All workers are idle - show green pulsating dot."""
        if self._state == "idle":
            return  # Already idle, no change
        
        self._state = "idle"
        self._pulsing = True
        self._target_scale = 1.0
        self.configure(border_color=COLORS["success"])
        self.label.configure(text="System Idle", text_color=COLORS["success"])
        self._pulse()
    
    def set_busy(self):
        """At least one worker is busy - show red/orange pulsating dot."""
        if self._state == "busy":
            return  # Already busy, no change
        
        self._state = "busy"
        self._pulsing = True
        self._target_scale = 1.05
        self.configure(border_color=COLORS["warning"])
        self.label.configure(text="Workers Active", text_color=COLORS["warning"])
        self._pulse()
    
    def set_offline(self):
        """System is stopped - show grey static dot."""
        if self._state == "offline":
            return  # Already offline
        
        self._state = "offline"
        self._pulsing = False
        self._target_scale = 1.0
        self.configure(border_color=COLORS["border"])
        self.dot.configure(text_color=COLORS["text_secondary"])
        self.label.configure(text="System Offline", text_color=COLORS["text_secondary"])
    
    def _pulse(self):
        if not self._pulsing:
            return
        
        if self._state == "busy":
            # Red/Orange pulsating for busy
            colors = [
                COLORS["error"], 
                ("#ff6b60", "#ff6b60"), 
                COLORS["warning"], 
                ("#ffaa33", "#ffb340")
            ]
        else:
            # Green pulsating for idle
            colors = [
                COLORS["success"], 
                ("#5fd47a", "#4cd964"), 
                COLORS["success"], 
                ("#2aa64a", "#248a3d")
            ]
        
        self.dot.configure(text_color=colors[self._pulse_step % len(colors)])
        self._pulse_step += 1
        
        self.after(500, self._pulse)

class StatCard(ctk.CTkFrame):
    """A stat card with big number and label — peach/beige background."""
    
    def __init__(self, parent, title: str, value: str = "0", highlight: bool = False):
        bg_color = COLORS["stat_highlight"] if highlight else COLORS["stat_bg"]
        super().__init__(
            parent, fg_color=bg_color, corner_radius=14,
            border_width=1, border_color=COLORS["border"]
        )
        
        self._bg_color = bg_color
        self.value_label = ctk.CTkLabel(
            self, text=value, font=("Segoe UI", 26, "bold"),
            text_color=COLORS["text_primary"]
        )
        self.value_label.pack(pady=(18, 4))
        
        self.title_label = ctk.CTkLabel(
            self, text=title.upper(), font=("Segoe UI", 10),
            text_color=COLORS["text_primary"]
        )
        self.title_label.pack(pady=(0, 16))
        
        self._last_value = value
    
    def update_value(self, value: str):
        if value != self._last_value:
            self.value_label.configure(text_color=COLORS["accent"])
            self.after(300, lambda: self.value_label.configure(text_color=COLORS["text_primary"]))
            self.value_label.configure(text=value)
            self._last_value = value


# =============================================================================
# Status Card (Thick Black Border) — for PROCESSING, CLOUD SYNC, STUCK
# =============================================================================
class StatusCard(ctk.CTkFrame):
    """Status card with thick black border, white bg, bold text — matches design guide."""
    
    def __init__(self, parent, title: str):
        super().__init__(
            parent, fg_color=COLORS["bg_card"], corner_radius=14,
            border_width=1, border_color=COLORS["border"]
        )
        
        self.title_label = ctk.CTkLabel(
            self, text=title.upper(), font=("Segoe UI", 12, "bold"),
            text_color=COLORS["text_primary"]
        )
        self.title_label.pack(pady=(12, 4))
        
        self.value_label = ctk.CTkLabel(
            self, text="—", font=("Segoe UI", 22, "bold"),
            text_color=COLORS["text_secondary"]
        )
        self.value_label.pack(pady=(0, 4))
        
        self.detail_label = ctk.CTkLabel(
            self, text="", font=("Segoe UI", 10),
            text_color=COLORS["text_secondary"]
        )
        self.detail_label.pack(pady=(0, 10))
    
    def set_status(self, value: str, detail: str = "", color=None):
        self.value_label.configure(
            text=value,
            text_color=color or COLORS["text_primary"]
        )
        self.detail_label.configure(text=detail)


# =============================================================================
# Processing Widget (Circular Progress Bar)
# =============================================================================
class ProcessingWidget(ctk.CTkFrame):
    """Animated circular progress bar with percentage and status."""
    
    def __init__(self, parent):
        super().__init__(parent, fg_color=COLORS["bg_card"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        
        self.title_label = ctk.CTkLabel(
            self, text="PROCESSING", font=("Segoe UI", 12, "bold"),
            text_color=COLORS["text_primary"], anchor="w"
        )
        self.title_label.pack(fill="x", padx=20, pady=(12, 4))
        
        # Canvas for circular progress
        self.canvas_size = 120
        self.canvas = ctk.CTkCanvas(
            self, width=self.canvas_size, height=self.canvas_size,
            bg=COLORS["bg_card"][0], highlightthickness=0
        )
        self.canvas.pack(pady=4)
        
        self.progress_label = ctk.CTkLabel(
            self, text="0 / 0 Photos", font=("Segoe UI", 11),
            text_color=COLORS["text_secondary"]
        )
        self.progress_label.pack(pady=(0, 2))
        
        self.status_label = ctk.CTkLabel(
            self, text="Idle", font=("Segoe UI", 12),
            text_color=COLORS["text_secondary"]
        )
        self.status_label.pack(pady=(0, 10))
        
        self._animating = False
        self._angle = 0
        self._mode = "light"
        
        self._target_progress = 0.0
        self._current_progress = 0.0
        self._completed = 0
        self._total = 0
        
        self._draw_ring()

    def set_appearance_mode(self, mode):
        self._mode = mode.lower()
        bg = COLORS["bg_card"][1] if self._mode == "dark" else COLORS["bg_card"][0]
        self.canvas.configure(bg=bg)
        self._draw_ring()

    def _draw_ring(self):
        """Draw the circular progress ring with current state."""
        self.canvas.delete("all")
        cx, cy = self.canvas_size / 2, self.canvas_size / 2
        r = 45
        line_w = 6
        
        track_color = "#3a3a3c" if self._mode == "dark" else "#e0e0e0"
        self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, outline=track_color, width=line_w)
        
        progress = self._current_progress
        if progress > 0:
            extent = progress * 360
            
            if progress >= 1.0:
                arc_color = COLORS["success"][1] if self._mode == "dark" else COLORS["success"][0]
            else:
                arc_color = COLORS["accent"][1] if self._mode == "dark" else COLORS["accent"][0]
            
            self.canvas.create_arc(
                cx-r, cy-r, cx+r, cy+r,
                start=90, extent=-extent,
                outline=arc_color, width=line_w, style="arc"
            )
            
            if 0 < progress < 1.0:
                angle_rad = math.radians(90 - extent)
                dot_x = cx + r * math.cos(angle_rad)
                dot_y = cy - r * math.sin(angle_rad)
                dot_r = 4
                self.canvas.create_oval(
                    dot_x-dot_r, dot_y-dot_r, dot_x+dot_r, dot_y+dot_r,
                    fill=arc_color, outline=""
                )
        
        pct_color = COLORS["text_primary"][1] if self._mode == "dark" else COLORS["text_primary"][0]
        
        if self._total == 0 and not self._animating:
            self.canvas.create_text(
                cx, cy - 4, text="--",
                fill=track_color, font=("Segoe UI", 24, "bold")
            )
            self.canvas.create_text(
                cx, cy + 16, text="IDLE",
                fill=track_color, font=("Segoe UI", 9)
            )
        elif progress >= 1.0:
            done_color = COLORS["success"][1] if self._mode == "dark" else COLORS["success"][0]
            self.canvas.create_text(
                cx, cy - 2, text="DONE",
                fill=done_color, font=("Segoe UI", 18, "bold")
            )
        else:
            pct = int(progress * 100)
            self.canvas.create_text(
                cx, cy - 6, text=f"{pct}",
                fill=pct_color, font=("Segoe UI", 28, "bold")
            )
            self.canvas.create_text(
                cx, cy + 16, text="%",
                fill=COLORS["text_secondary"][1] if self._mode == "dark" else COLORS["text_secondary"][0],
                font=("Segoe UI", 11)
            )

    def update_progress(self, completed: int, total: int):
        """Update progress bar with current counts."""
        self._completed = completed
        self._total = total
        
        if total > 0:
            self._target_progress = min(completed / total, 1.0)
        else:
            self._target_progress = 0.0
        
        if total == 0:
            self.progress_label.configure(text="No photos queued")
            self.status_label.configure(text="Idle", text_color=COLORS["text_secondary"])
        elif completed >= total:
            self.progress_label.configure(text=f"{completed} / {total} Photos")
            self.status_label.configure(text="All Done!", text_color=COLORS["success"])
        else:
            self.progress_label.configure(text=f"{completed} / {total} Photos")
            self.status_label.configure(text="Processing...", text_color=COLORS["accent"])

    def start_processing(self):
        if not self._animating:
            self._animating = True
            self._animate()

    def stop_processing(self):
        self._animating = False
        if self._total == 0:
            self.status_label.configure(text="Idle", text_color=COLORS["text_secondary"])
            self._current_progress = 0
            self._target_progress = 0
            self._draw_ring()

    def draw_static_ring(self):
        """Legacy compatibility."""
        self._draw_ring()

    def _animate(self):
        if not self._animating:
            return
        
        diff = self._target_progress - self._current_progress
        if abs(diff) > 0.002:
            self._current_progress += diff * 0.12
        else:
            self._current_progress = self._target_progress
        
        self._draw_ring()
        self.after(33, self._animate)

class CloudWidget(ctk.CTkFrame):
    """Animated cloud upload status."""
    
    def __init__(self, parent):
        super().__init__(parent, fg_color=COLORS["bg_card"], corner_radius=14, border_width=1, border_color=COLORS["border"])
        
        self.title_label = ctk.CTkLabel(
            self, text="CLOUD SYNC", font=("Segoe UI", 12, "bold"),
            text_color=COLORS["text_primary"], anchor="w"
        )
        self.title_label.pack(fill="x", padx=20, pady=(12, 4))
        
        self.canvas_size = 120
        self.canvas = ctk.CTkCanvas(
            self, width=self.canvas_size, height=self.canvas_size,
            bg=COLORS["bg_card"][0], highlightthickness=0
        )
        self.canvas.pack(pady=4)
        
        self.status_label = ctk.CTkLabel(
            self, text="Synced", font=("Segoe UI", 12),
            text_color=COLORS["text_secondary"]
        )
        self.status_label.pack(pady=(0, 10))
        
        self._uploading = False
        self._offset = 0
        self._mode = "light"
        
        self.draw_static_cloud()

    def set_appearance_mode(self, mode):
        self._mode = mode.lower()
        bg = COLORS["bg_card"][1] if self._mode == "dark" else COLORS["bg_card"][0]
        self.canvas.configure(bg=bg)
        if not self._uploading:
            self.draw_static_cloud()

    def draw_static_cloud(self):
        self.canvas.delete("all")
        self._draw_cloud_icon(offset=0, color=COLORS["text_secondary"][1] if self._mode == "dark" else COLORS["text_secondary"][0])

    def start_uploading(self):
        if not self._uploading:
            self._uploading = True
            self.status_label.configure(text="Uploading...", text_color=COLORS["accent"])
            self._animate()

    def stop_uploading(self):
        if self._uploading:
            self._uploading = False
            self.status_label.configure(text="Synced", text_color=COLORS["success"])
            self.draw_static_cloud()

    def _draw_cloud_icon(self, offset=0, color="gray"):
        cx, cy = self.canvas_size / 2, self.canvas_size / 2
        
        self.canvas.create_oval(cx-30, cy-10, cx+10, cy+20, fill=color, outline="")
        self.canvas.create_oval(cx-10, cy-20, cx+30, cy+10, fill=color, outline="")
        self.canvas.create_oval(cx+10, cy-10, cx+40, cy+20, fill=color, outline="")
        self.canvas.create_oval(cx-20, cy+5, cx+30, cy+20, fill=color, outline="")
        
        if self._uploading:
            arrow_y = cy + 10 - offset
            ac = COLORS["success"][1] if self._mode == "dark" else COLORS["success"][0]
            self.canvas.create_line(cx, arrow_y, cx, arrow_y-20, width=3, fill=ac, capstyle="round")
            self.canvas.create_line(cx, arrow_y-20, cx-8, arrow_y-12, width=3, fill=ac, capstyle="round")
            self.canvas.create_line(cx, arrow_y-20, cx+8, arrow_y-12, width=3, fill=ac, capstyle="round")

    def _animate(self):
        if not self._uploading:
            return
            
        self.canvas.delete("all")
        cloud_color = COLORS["text_primary"][1] if self._mode == "dark" else COLORS["text_primary"][0]
        self._draw_cloud_icon(offset=self._offset, color=cloud_color)
        
        self._offset = (self._offset + 2) % 20
        self.after(50, self._animate)


# =============================================================================
# Stuck Photos Card
# =============================================================================
class StuckPhotosCard(ctk.CTkFrame):
    """Shows stuck photos in processing — both image analysis and cloud upload."""
    
    def __init__(self, parent):
        super().__init__(
            parent, fg_color=COLORS["bg_card"], corner_radius=14,
            border_width=1, border_color=COLORS["border"]
        )
        
        self.title_label = ctk.CTkLabel(
            self, text="STUCK PHOTOS", font=("Segoe UI", 12, "bold"),
            text_color=COLORS["text_primary"]
        )
        self.title_label.pack(pady=(12, 8))
        
        # Processing stuck
        proc_frame = ctk.CTkFrame(self, fg_color="transparent")
        proc_frame.pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(
            proc_frame, text="Image Analysis", font=("Segoe UI", 11),
            text_color=COLORS["text_secondary"]
        ).pack(side="left")
        self.proc_stuck_label = ctk.CTkLabel(
            proc_frame, text="0", font=("Segoe UI", 14, "bold"),
            text_color=COLORS["text_primary"]
        )
        self.proc_stuck_label.pack(side="right")
        
        # Cloud stuck
        cloud_frame = ctk.CTkFrame(self, fg_color="transparent")
        cloud_frame.pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(
            cloud_frame, text="Cloud Upload", font=("Segoe UI", 11),
            text_color=COLORS["text_secondary"]
        ).pack(side="left")
        self.cloud_stuck_label = ctk.CTkLabel(
            cloud_frame, text="0", font=("Segoe UI", 14, "bold"),
            text_color=COLORS["text_primary"]
        )
        self.cloud_stuck_label.pack(side="right")
        
        # Total
        sep = ctk.CTkFrame(self, fg_color=COLORS["border"], height=1)
        sep.pack(fill="x", padx=16, pady=(6, 4))
        
        total_frame = ctk.CTkFrame(self, fg_color="transparent")
        total_frame.pack(fill="x", padx=16, pady=(0, 10))
        ctk.CTkLabel(
            total_frame, text="Total Stuck", font=("Segoe UI", 11, "bold"),
            text_color=COLORS["text_primary"]
        ).pack(side="left")
        self.total_stuck_label = ctk.CTkLabel(
            total_frame, text="0", font=("Segoe UI", 14, "bold"),
            text_color=COLORS["text_primary"]
        )
        self.total_stuck_label.pack(side="right")
    
    def update_stuck(self, proc_stuck: int, cloud_stuck: int):
        total = proc_stuck + cloud_stuck
        
        self.proc_stuck_label.configure(
            text=str(proc_stuck),
            text_color=COLORS["warning"] if proc_stuck > 0 else COLORS["success"]
        )
        self.cloud_stuck_label.configure(
            text=str(cloud_stuck),
            text_color=COLORS["warning"] if cloud_stuck > 0 else COLORS["success"]
        )
        self.total_stuck_label.configure(
            text=str(total),
            text_color=COLORS["error"] if total > 0 else COLORS["success"]
        )
class ActivityLog(ctk.CTkFrame):
    """Activity log with dark grey bg and black terminal — per design guide."""
    
    def __init__(self, parent):
        super().__init__(
            parent, fg_color=COLORS["log_outer"], corner_radius=14,
            border_width=0
        )
        
        self.title_label = ctk.CTkLabel(
            self, text="ACTIVITY LOG", font=("Segoe UI", 12, "bold"),
            text_color=("#a0a0b0", "#a0a0b0"), anchor="w"
        )
        self.title_label.pack(fill="x", padx=16, pady=(12, 8))
        
        # Black terminal inside
        self.textbox = ctk.CTkTextbox(
            self, font=("Consolas", 11),
            fg_color=COLORS["log_inner"],
            text_color=("#c0c0d0", "#b0b0c0"),
            corner_radius=10, height=120
        )
        self.textbox.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.textbox.configure(state="disabled")
        
        # Define tags for coloring
        self.textbox.tag_config("proc", foreground="#5ac8fa")
        self.textbox.tag_config("db", foreground="#ffcc00")
        self.textbox.tag_config("cloud", foreground="#af52de")
        self.textbox.tag_config("whatsapp", foreground="#34c759")
        self.textbox.tag_config("server", foreground="#007aff")
        self.textbox.tag_config("error", foreground="#ff3b30")
        self.textbox.tag_config("timestamp", foreground="#888888")
    
    def add_log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        icon = "•"
        tag = "info"
        display_msg = message

        lower_msg = message.lower()
        
        if "app.processor" in lower_msg or "processing" in lower_msg:
            icon = "⚙️"
            tag = "proc"
            display_msg = message.replace("app.processor |", "").strip()
            if display_msg.startswith("[Worker]"): display_msg = display_msg.replace("[Worker]", "").strip()
            display_msg = f"Processor | {display_msg}"
            
        elif "app.db" in lower_msg or "database" in lower_msg:
            icon = "🗄️"
            tag = "db"
            display_msg = message.replace("app.db |", "").strip()
            if display_msg.startswith("[Worker]"): display_msg = display_msg.replace("[Worker]", "").strip()
            display_msg = f"Database | {display_msg}"
            
        elif "app.cloud" in lower_msg or "drive" in lower_msg:
            icon = "☁️"
            tag = "cloud"
            display_msg = message.replace("app.cloud |", "").strip()
            if display_msg.startswith("[Worker]"): display_msg = display_msg.replace("[Worker]", "").strip()
            display_msg = f"Cloud | {display_msg}"
            
        elif "whatsapp" in lower_msg:
            icon = "💬"
            tag = "whatsapp"
            if display_msg.startswith("[WhatsApp]"): display_msg = display_msg.replace("[WhatsApp]", "").strip()
            display_msg = f"WhatsApp | {display_msg}"
            
        elif "server" in lower_msg:
            icon = "🌐"
            tag = "server"
            if display_msg.startswith("[Server]"): display_msg = display_msg.replace("[Server]", "").strip()
            display_msg = f"Server | {display_msg}"
            
        elif level == "error":
            icon = "✗"
            tag = "error"
        elif level == "success":
            icon = "✓"
            tag = "whatsapp"

        self.textbox.configure(state="normal")
        
        self.textbox.insert("1.0", f"{display_msg}\n")
        
        prefix = f"{timestamp}  {icon}  "
        self.textbox.insert("1.0", prefix, (tag,))
        
        self.textbox.configure(state="disabled")


# =============================================================================
# Folder Choice Popup (Hover Menu)
# =============================================================================
class FolderChoicePopup(ctk.CTkToplevel):
    """Floating popup: face thumbnail + Local / Cloud buttons."""
    
    THUMB_W = 230           # thumbnail width (+10% increase)
    THUMB_H = 290           # thumbnail height
    BTN_AREA_H = 30         # height for the button row
    PADDING = 4             # removed padding to accommodate wider image without growing window
    
    def __init__(self, parent, x, y, person_name, on_local, on_cloud, thumbnail_path=None):
        # Always parent to the root window to avoid "bad window path" errors
        # when the scrollable frame widget hierarchy changes (especially on external displays)
        root = parent.winfo_toplevel()
        super().__init__(root)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        
        # Windows transparency fix for rounded outer corners
        if sys.platform.startswith("win"):
            self.attributes("-transparentcolor", "#000001")
            self.configure(fg_color="#000001")
        else:
            self.configure(fg_color="transparent")
        
        curr_mode = ctk.get_appearance_mode()
        bg_color = COLORS["bg_card"][1] if curr_mode == "Dark" else COLORS["bg_card"][0]
        
        has_thumb = thumbnail_path and Path(thumbnail_path).exists()
        popup_w = self.THUMB_W + self.PADDING * 2 + 4  # +4 for border
        popup_h = (self.THUMB_H + self.BTN_AREA_H + self.PADDING * 3 + 4) if has_thumb else (self.BTN_AREA_H + self.PADDING * 2 + 4)
        
        # Outer border frame
        self.outer_frame = ctk.CTkFrame(self, fg_color=COLORS["border"], corner_radius=16)
        self.outer_frame.pack(padx=0, pady=0)
        
        # Inner card
        self.frame = ctk.CTkFrame(self.outer_frame, fg_color=bg_color, corner_radius=14, border_width=0)
        self.frame.pack(padx=2, pady=2)
        
        # ---- Thumbnail (clear, clipped to rounded rect) ----
        self._tk_thumb = None
        if has_thumb:
            try:
                img = Image.open(thumbnail_path).convert("RGBA")
                
                # Crop to portrait ratio from center
                tw, th = self.THUMB_W, self.THUMB_H
                w, h = img.size
                target_ratio = tw / th
                src_ratio = w / h
                if src_ratio > target_ratio:
                    # Source is wider — crop sides
                    new_w = int(h * target_ratio)
                    left = (w - new_w) // 2
                    img = img.crop((left, 0, left + new_w, h))
                else:
                    # Source is taller — crop top/bottom
                    new_h = int(w / target_ratio)
                    top = (h - new_h) // 2
                    img = img.crop((0, top, w, top + new_h))
                img = img.resize((tw, th), Image.LANCZOS)
                
                # Create rounded mask to clip corners
                from PIL import ImageDraw
                radius = 10
                mask = Image.new("L", (tw, th), 0)
                draw = ImageDraw.Draw(mask)
                draw.rounded_rectangle(
                    [(0, 0), (tw - 1, th - 1)],
                    radius=radius, fill=255
                )
                
                # Apply mask — composite onto bg color
                bg_img = Image.new("RGBA", (tw, th), bg_color)
                bg_img.paste(img, (0, 0), mask)
                
                self._tk_thumb = ImageTk.PhotoImage(bg_img.convert("RGB"))
                
                thumb_label = tk.Label(
                    self.frame, image=self._tk_thumb, bd=0,
                    highlightthickness=0, bg=bg_color
                )
                thumb_label.pack(padx=self.PADDING, pady=(self.PADDING, 0))
            except Exception:
                pass
        
        # ---- Button row (horizontal) ----
        btn_row = ctk.CTkFrame(self.frame, fg_color="transparent")
        btn_row.pack(pady=(3, 4))  # Centered horizontally, increased bottom margin
        
        btn_w = 30  # Further reduced width to eliminate horizontal empty space
        
        self.btn_local = ctk.CTkButton(
            btn_row, text="📁Local", height=26, width=btn_w, corner_radius=13,
            fg_color=("#e8e8e8", "#2c2c2e"), hover_color=("#d0d0d0", "#3a3a3c"),
            text_color=COLORS["text_primary"],
            font=("Segoe UI", 9),
            command=lambda: [on_local(), self._safe_destroy()]
        )
        self.btn_local.pack(side="left", padx=(0, 2))
        
        self.btn_cloud = ctk.CTkButton(
            btn_row, text="☁Cloud", height=26, width=btn_w, corner_radius=13,
            fg_color=("#e8e8e8", "#2c2c2e"), hover_color=("#d0d0d0", "#3a3a3c"),
            text_color=COLORS["text_primary"],
            font=("Segoe UI", 9),
            command=lambda: [on_cloud(), self._safe_destroy()]
        )
        self.btn_cloud.pack(side="left", padx=(2, 0))
        
        # Set explicit size AND position to avoid inconsistent sizing
        self.geometry(f"{popup_w}x{popup_h}+{x-5}+{y-5}")
        
        # Grace period before enabling auto-close (longer for external displays)
        self._can_close = False
        self._destroying = False
        self.after(500, self._enable_close)
        
        # Leave tracking
        self.outer_frame.bind("<Leave>", self._on_mouse_leave)
        self.btn_local.bind("<Enter>", lambda e: self._cancel_close())
        self.btn_cloud.bind("<Enter>", lambda e: self._cancel_close())

    def _safe_destroy(self):
        """Safely destroy popup, guarding against already-destroyed windows."""
        if self._destroying:
            return
        self._destroying = True
        try:
            if self.winfo_exists():
                self.destroy()
        except Exception:
            pass

    def _enable_close(self):
        if self._destroying:
            return
        self._can_close = True
        # Wait until window is mapped and has valid geometry before checking position
        self.after(200, self._check_position_loop)

    def _on_mouse_leave(self, event):
        if self._can_close and not self._destroying:
            self.after(150, self._check_really_left)

    def _check_really_left(self):
        if self._destroying:
            return
        try:
            if not self.winfo_exists():
                return
            mx = self.winfo_pointerx()
            my = self.winfo_pointery()
            wx = self.winfo_rootx()
            wy = self.winfo_rooty()
            ww = self.winfo_width()
            wh = self.winfo_height()
            # Sanity check: skip if geometry is not yet valid
            if ww < 5 or wh < 5:
                return
            padding = 15
            if not (wx-padding <= mx <= wx+ww+padding and wy-padding <= my <= wy+wh+padding):
                self._safe_destroy()
        except Exception:
            pass

    def _check_position_loop(self):
        """Continuously check if mouse is still near the popup."""
        if self._destroying:
            return
        try:
            if not self.winfo_exists():
                return
            mx = self.winfo_pointerx()
            my = self.winfo_pointery()
            wx = self.winfo_rootx()
            wy = self.winfo_rooty()
            ww = self.winfo_width()
            wh = self.winfo_height()
            # Sanity check: skip position checks until geometry is valid
            if ww < 5 or wh < 5:
                self.after(200, self._check_position_loop)
                return
            padding = 25
            if not (wx-padding <= mx <= wx+ww+padding and wy-padding <= my <= wy+wh+padding):
                self._safe_destroy()
                return
            self.after(150, self._check_position_loop)
        except Exception:
            try:
                self._safe_destroy()
            except Exception:
                pass

    def _cancel_close(self):
        pass

class PeopleList(ctk.CTkScrollableFrame):
    """Person list with pill-shaped items — thick black border, white bg."""
    
    def __init__(self, parent):
        super().__init__(parent, fg_color=COLORS["bg_card"], corner_radius=14)
        self._last_hash = None
        self._hover_id = None
        self._popup = None
        self._thumb_cache = {}  # person_id -> thumbnail path
    

    def _get_person_thumbnail(self, person_id, person_name, enrollment=None):
        """Get or generate a face thumbnail for a person.
        
        Priority:
        1. Cached thumbnail
        2. Enrollment selfie (enrolled users)
        3. Auto-crop from first detected face (non-enrolled)
        
        Returns path string or None.
        """
        # Check memory cache
        if person_id in self._thumb_cache:
            cached = self._thumb_cache[person_id]
            if cached and Path(cached).exists():
                return cached
        
        try:
            from app.config import get_config
            config = get_config()
            
            # Check for enrollment selfie first
            if enrollment:
                selfie = Path(enrollment.selfie_path)
                if selfie.exists():
                    self._thumb_cache[person_id] = str(selfie)
                    return str(selfie)
            
            # Check for reference selfie in person folder
            person_dir = config.people_dir / person_name
            ref_selfie = person_dir / "00_REFERENCE_SELFIE.jpg"
            if ref_selfie.exists():
                self._thumb_cache[person_id] = str(ref_selfie)
                return str(ref_selfie)
            
            # Auto-generate from face bbox
            cache_dir = config.people_dir / ".thumbnails"
            cache_dir.mkdir(exist_ok=True)
            thumb_path = cache_dir / f"person_{person_id}.jpg"
            
            if thumb_path.exists():
                self._thumb_cache[person_id] = str(thumb_path)
                return str(thumb_path)
            
            # Generate: crop face from source photo
            db = get_db()
            face_info = db.get_first_face_for_person(person_id)
            if not face_info or not face_info["processed_path"]:
                self._thumb_cache[person_id] = None
                return None
            
            src_path = Path(face_info["processed_path"])
            if not src_path.exists():
                self._thumb_cache[person_id] = None
                return None
            
            img = Image.open(src_path)
            bx, by, bw, bh = face_info["bbox_x"], face_info["bbox_y"], face_info["bbox_w"], face_info["bbox_h"]
            
            # Add generous padding around the face crop
            pad = int(max(bw, bh) * 0.4)
            x1 = max(0, bx - pad)
            y1 = max(0, by - pad)
            x2 = min(img.width, bx + bw + pad)
            y2 = min(img.height, by + bh + pad)
            
            face_crop = img.crop((x1, y1, x2, y2))
            face_crop = face_crop.resize((120, 120), Image.LANCZOS)
            face_crop.save(str(thumb_path), "JPEG", quality=85)
            
            self._thumb_cache[person_id] = str(thumb_path)
            return str(thumb_path)
            
        except Exception:
            self._thumb_cache[person_id] = None
            return None

    def _open_person_folder(self, person_name):
        """Open the specific person's folder in file explorer."""
        try:
            from app.config import get_config
            config = get_config()
            folder_path = config.people_dir / person_name
            if folder_path.exists():
                os.startfile(str(folder_path))
        except Exception:
            pass

    def _open_cloud_folder(self, person_name):
        """Determine cloud URL and open in browser."""
        def task():
            try:
                from app.cloud import get_cloud
                cloud = get_cloud()
                if cloud.is_enabled:
                    folder_id = cloud.ensure_folder_path(["People", person_name])
                    if folder_id:
                        url = f"https://drive.google.com/drive/folders/{folder_id}"
                        webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=task, daemon=True).start()

    def _close_popup(self):
        """Close the popup if it exists."""
        try:
            if self._popup and self._popup.winfo_exists():
                self._popup._safe_destroy()
        except Exception:
            pass
        self._popup = None

    def _show_choice_popup(self, x, y, person_name, person_id=None, enrollment=None):
        """Show the floating choice menu with optional face thumbnail."""
        # Close any existing popup safely
        self._close_popup()
        
        # Get thumbnail
        thumb = None
        if person_id is not None:
            thumb = self._get_person_thumbnail(person_id, person_name, enrollment)
        
        try:
            self._popup = FolderChoicePopup(
                self, x, y, person_name,
                on_local=lambda: self._open_person_folder(person_name),
                on_cloud=lambda: self._open_cloud_folder(person_name),
                thumbnail_path=thumb
            )
        except Exception:
            # If popup creation fails (e.g. external display timing issue),, just skip
            self._popup = None

    def update_persons(self, persons: list, enrollments: dict):
        current_counts = {}
        for p in persons:
            name = enrollments.get(p.id).user_name if p.id in enrollments else p.name
            current_counts[name] = p.face_count

        changes = []
        if hasattr(self, "_last_counts"):
            for name, count in current_counts.items():
                old_count = self._last_counts.get(name, 0)
                if count > old_count:
                    changes.append(name)
        
        self._last_counts = current_counts

        data_hash = str([(p.id, p.name, p.face_count) for p in persons])
        if data_hash == self._last_hash:
            pass
        else:
            self._last_hash = data_hash
            
            for w in self.winfo_children():
                w.destroy()
            
            if not persons:
                ctk.CTkLabel(self, text="No people detected yet", font=("Segoe UI", 13), text_color=COLORS["text_secondary"]).pack(pady=20)
                return
            
            for person in persons:
                enrollment = enrollments.get(person.id)
                name = enrollment.user_name if enrollment else person.name
                icon = "✓ " if enrollment else ""
                p_name = person.name # Current folder name
                
                # Pill-shaped row: thick black border, fully rounded, white bg
                row = ctk.CTkFrame(
                    self, fg_color=COLORS["bg_card"], corner_radius=50,
                    border_width=1, border_color=COLORS["border"],
                    height=36
                )
                row.pack(fill="x", padx=4, pady=3)
                row.pack_propagate(False)
                row.configure(cursor="hand2")
                
                # Hover effect & Popup trigger
                def on_enter(e, r=row, pn=p_name, pid=person.id, enr=enrollment): 
                    r.configure(fg_color=("#f2f2f2", "#3a3a3c"))
                    # Start timer for popup
                    if self._hover_id: self.after_cancel(self._hover_id)
                    self._hover_id = self.after(600, lambda: self._show_choice_popup(e.x_root, e.y_root, pn, pid, enr))

                def on_leave(e, r=row): 
                    r.configure(fg_color=COLORS["bg_card"])
                    # Cancel timer if popup hasn't appeared yet
                    if self._hover_id:
                        self.after_cancel(self._hover_id)
                        self._hover_id = None
                    # Don't close popup immediately - let the popup's own tracking handle it
                
                # Click handler (still opens local immediately as quick action)
                def on_click(e, pn=p_name): 
                    if self._hover_id: self.after_cancel(self._hover_id)
                    self._open_person_folder(pn)
                
                row.bind("<Enter>", on_enter)
                row.bind("<Leave>", on_leave)
                row.bind("<Button-1>", on_click)
                
                name_lbl = ctk.CTkLabel(
                    row, text=f"{icon}{name}", font=("Segoe UI", 12),
                    text_color=COLORS["text_primary"]
                )
                name_lbl.pack(side="left", padx=(16, 5), pady=4)
                name_lbl.bind("<Button-1>", on_click)
                name_lbl.bind("<Enter>", on_enter)
                
                count_lbl = ctk.CTkLabel(
                    row, text=f"{person.face_count}", font=("Segoe UI", 12),
                    text_color=COLORS["text_secondary"]
                )
                count_lbl.pack(side="right", padx=(5, 16), pady=4)
                count_lbl.bind("<Button-1>", on_click)
                count_lbl.bind("<Enter>", on_enter)
        
        for name in changes:
            self.highlight_person(name)
    
    def highlight_person(self, name_to_find):
        """Find and highlight a person in the list."""
        search = name_to_find.lower().strip()
        found_widget = None
        
        for row in self.winfo_children():
            children = row.winfo_children()
            if not children: continue
            
            name_lbl = children[0]
            if not isinstance(name_lbl, ctk.CTkLabel): continue
            
            txt = name_lbl.cget("text").lower()
            if txt.startswith("✓ "): txt = txt[2:]
            
            if search in txt:
                found_widget = row
                break
        
        if found_widget:
            orig_color = found_widget.cget("fg_color")
            flash_color = COLORS["accent"]
            
            def flash(step):
                try:
                    if not found_widget.winfo_exists():
                        return
                except Exception:
                    return
                
                if step > 5:
                    try:
                        found_widget.configure(fg_color=COLORS["bg_card"])
                    except Exception:
                        pass
                    return
                c = flash_color if step % 2 == 0 else COLORS["bg_card"]
                try:
                    found_widget.configure(fg_color=c)
                except Exception:
                    return
                self.after(200, lambda: flash(step + 1))
            
            flash(0)
