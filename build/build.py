#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Configuration
BASE_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = BASE_DIR.parent
ICON_PATH = BASE_DIR / "icon.png"
ENV_PATH = PROJECT_ROOT / ".env"
APP_NAME = "PortfolioOptimizer"
MAIN_SCRIPT = str(PROJECT_ROOT / "app.py")

# Check prerequisites
if not ENV_PATH.exists():
    print(f"ERROR: .env file not found at {ENV_PATH}")
    sys.exit(1)

# Build command
cmd = [
    "pyinstaller",
    "--onefile",
    "--clean",
    "--noconfirm",
    f"--name={APP_NAME}",
    f"--add-data={ENV_PATH}{os.pathsep}.",
    f"--additional-hooks-dir={BASE_DIR}",  # Use our custom hooks
    
    # Collect all scipy binary files
    "--collect-binaries=scipy",
    
    # Critical scipy imports
    "--hidden-import=scipy._lib.messagestream",
    "--hidden-import=scipy._cyutility",
    "--hidden-import=scipy.sparse._csparsetools",
    "--hidden-import=scipy.sparse._sparsetools",
    
    # Collect all scipy submodules
    "--collect-all=scipy",
    
    # Other dependencies
    "--hidden-import=multiprocessing",
    "--hidden-import=concurrent.futures",
    "--hidden-import=alpha_vantage",
    "--hidden-import=dotenv",
    "--hidden-import=pandas._libs.tslibs.timedeltas",
    "--collect-submodules=alpha_vantage",
    
    # Optimization libraries
    "--hidden-import=cvxpy",
    "--hidden-import=pypfopt",
    "--hidden-import=osqp",
    "--hidden-import=scs",
    "--hidden-import=ecos",
    "--hidden-import=clarabel",
    "--collect-submodules=cvxpy",
    "--collect-submodules=pypfopt",
    
    # NumPy
    "--collect-binaries=numpy",
    
    # Main script
    MAIN_SCRIPT
]

# Add icon if available
if ICON_PATH.exists():
    cmd.insert(-1, f"--icon={ICON_PATH}")

# Run PyInstaller
print(f"Building {APP_NAME}...")
import subprocess
result = subprocess.run(cmd)
sys.exit(result.returncode)