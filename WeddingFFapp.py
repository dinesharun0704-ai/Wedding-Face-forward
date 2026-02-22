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

