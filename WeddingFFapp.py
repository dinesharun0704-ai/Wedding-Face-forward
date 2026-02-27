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

