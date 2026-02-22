import os
import sys
import time
import multiprocessing
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | MAIN | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def run_backend_worker():
    """Start the photo processing background worker."""
    logger.info("Starting Backend Worker...")
    
    # Add backend directory to path
    base_dir = Path(__file__).parent.resolve()
    backend_dir = base_dir / "backend"
    sys.path.insert(0, str(backend_dir))
    
    # Import and run worker main
    from app.worker import main as worker_main
    worker_main()

def run_frontend_server():
    """Start the FastAPI web server."""
    logger.info("Starting Frontend Server...")
    
    # Add frontend and backend directories to path
    base_dir = Path(__file__).parent.resolve()
    frontend_dir = base_dir / "frontend"
    backend_dir = base_dir / "backend"
    
    sys.path.insert(0, str(frontend_dir))
    sys.path.insert(0, str(backend_dir))
    
    # Import app from server module
    import uvicorn
    from server import app
    
    # Run uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
