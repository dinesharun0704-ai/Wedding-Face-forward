import sys
import os
import subprocess
import threading
import time

BASE_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(FRONTEND_DIR))