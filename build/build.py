#!/usr/bin/env python3
"""
Unified build script for Portfolio Optimizer
Combines fixes from master branch with simplified configuration
"""

import os
import sys
import subprocess
from pathlib import Path
import shutil

# === Configuration ===
BASE_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = BASE_DIR.parent
ICON_PATH = BASE_DIR / "icon.png"
ENV_PATH = PROJECT_ROOT / ".env"
APP_NAME = "PortfolioOptimizer"
MAIN_SCRIPT = PROJECT_ROOT / "app.py"
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"
SPEC_DIR = BASE_DIR / "spec"

# PyInstaller base options
PYINSTALLER_BASE_OPTIONS = [
    "--onefile",
    "--clean",
    "--noconfirm",
    f"--distpath={DIST_DIR}",
    f"--workpath={BUILD_DIR}",
    f"--specpath={SPEC_DIR}",
    f"--name={APP_NAME}",
    "--optimize=2",
]

# Essential hidden imports that fixed the build issues
HIDDEN_IMPORTS = [
    # Core dependencies
    "multiprocessing",
    "concurrent.futures",
    "alpha_vantage",
    "dotenv",
    
    # Pandas multiprocessing fix
    "pandas._libs.tslibs.timedeltas",
    
    # Critical scipy imports that were causing ModuleNotFoundError
    "scipy._lib.messagestream",
    "scipy._cyutility",  # This was the key missing import
    "scipy.sparse.csgraph._validation",
    "scipy.sparse._matrix",
    "scipy.special._ufuncs_cxx",
    "scipy.linalg.cython_blas",
    "scipy.linalg.cython_lapack",
    "scipy.integrate",
    "scipy.integrate.quadrature",
    "scipy.integrate.odepack",
    "scipy.integrate._odepack",
    "scipy.integrate.quadpack",
    "scipy.integrate._quadpack",
    "scipy.integrate._ode",
    "scipy.integrate.vode",
    "scipy.integrate._dop",
    "scipy._lib._ccallback",
    
    # Optimization libraries
    "cvxpy",
    "pypfopt",
    "osqp",
    "scs",
    "ecos",
    "clarabel",
    
    # NumPy components
    "numpy",
    "numpy.core._multiarray_umath",
    "numpy.core._multiarray_tests",
    "numpy.random._pickle",
    "numpy.random._common",
    "numpy.random._bounded_integers",
    "numpy.random._mt19937",
    "numpy.random.bit_generator",
    "numpy.random._generator",
    "numpy.random._pcg64",
    "numpy.random._philox",
    "numpy.random._sfc64",
    "numpy.random.mtrand",
]

# Submodules to collect
COLLECT_SUBMODULES = [
    "scipy",
    "alpha_vantage",
    "cvxpy",
    "pypfopt",
]

# Data files to include
DATA_FILES = [
    (ENV_PATH, "."),  # Include .env file in root of bundle
]

# Optional: Runtime hooks if needed
RUNTIME_HOOKS = []
if (BASE_DIR / "runtime_hook.py").exists():
    RUNTIME_HOOKS.append(str(BASE_DIR / "runtime_hook.py"))

# Optional: Additional hooks directory
HOOKS_DIR = []
if any((BASE_DIR / f"hook-{lib}.py").exists() for lib in ["scipy", "cvxpy", "pypfopt"]):
    HOOKS_DIR.append(str(BASE_DIR))


def prepare_icon():
    """Prepare application icon if available"""
    if not ICON_PATH.exists():
        print(f"No icon found at {ICON_PATH}")
        return None
    
    try:
        from PIL import Image
        print(f"Preparing icon from {ICON_PATH}")
        
        # Create ICO file with multiple sizes
        ico_path = BASE_DIR / "app_icon.ico"
        img = Image.open(ICON_PATH)
        
        # Standard Windows icon sizes
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        
        # Create resized versions
        resized_images = []
        for size in sizes:
            resized = img.resize(size, Image.Resampling.LANCZOS)
            resized_images.append(resized)
        
        # Save as ICO
        resized_images[0].save(ico_path, format="ICO", sizes=sizes)
        print(f"Icon prepared: {ico_path}")
        return str(ico_path)
        
    except ImportError:
        print("PIL/Pillow not installed, skipping icon preparation")
        return None
    except Exception as e:
        print(f"Error preparing icon: {e}")
        return None


def check_prerequisites():
    """Check that all prerequisites are met"""
    errors = []
    
    # Check .env file
    if not ENV_PATH.exists():
        errors.append(f"ERROR: .env file not found at {ENV_PATH}")
        errors.append("The .env file with ALPHA_KEY is required for the application.")
        errors.append("Please create the .env file before building.")
    else:
        print(f"✓ Found .env file at {ENV_PATH}")
    
    # Check main script
    if not MAIN_SCRIPT.exists():
        errors.append(f"ERROR: Main script not found at {MAIN_SCRIPT}")
    else:
        print(f"✓ Found main script at {MAIN_SCRIPT}")
    
    # Check PyInstaller
    try:
        import PyInstaller
        print(f"✓ PyInstaller version {PyInstaller.__version__} installed")
    except ImportError:
        errors.append("ERROR: PyInstaller not installed. Run: pip install pyinstaller")
    
    return errors


def build_command():
    """Build the complete PyInstaller command"""
    cmd = PYINSTALLER_BASE_OPTIONS.copy()
    
    # Add hidden imports
    for hidden in HIDDEN_IMPORTS:
        cmd.append(f"--hidden-import={hidden}")
    
    # Add collect-submodules
    for module in COLLECT_SUBMODULES:
        cmd.append(f"--collect-submodules={module}")
    
    # Add data files
    for src, dst in DATA_FILES:
        if Path(src).exists():
            cmd.append(f"--add-data={src}{os.pathsep}{dst}")
    
    # Add runtime hooks
    for hook in RUNTIME_HOOKS:
        cmd.append(f"--runtime-hook={hook}")
    
    # Add hooks directory
    for hooks_dir in HOOKS_DIR:
        cmd.append(f"--additional-hooks-dir={hooks_dir}")
    
    # Add icon if available
    icon_path = prepare_icon()
    if icon_path:
        cmd.append(f"--icon={icon_path}")
    
    # Add main script
    cmd.append(str(MAIN_SCRIPT))
    
    return cmd


def clean_build_artifacts():
    """Clean up build artifacts"""
    print("\nCleaning build artifacts...")
    
    # Remove build directories
    for dir_path in [BUILD_DIR, SPEC_DIR]:
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"Removed {dir_path}")
    
    # Remove generated files
    for file_path in [BASE_DIR / "app_icon.ico"]:
        if file_path.exists():
            file_path.unlink()
            print(f"Removed {file_path}")


def main():
    """Main build process"""
    print("=" * 60)
    print("Portfolio Optimizer Build Script")
    print("=" * 60)
    
    # Check prerequisites
    errors = check_prerequisites()
    if errors:
        print("\nBuild cannot continue due to errors:")
        for error in errors:
            print(f"  {error}")
        sys.exit(1)
    
    # Clean previous builds
    if "--clean-all" in sys.argv:
        clean_build_artifacts()
        if DIST_DIR.exists():
            shutil.rmtree(DIST_DIR)
            print(f"Removed {DIST_DIR}")
    
    # Build PyInstaller command
    pyinstaller_cmd = build_command()
    
    # Show build configuration
    print("\nBuild Configuration:")
    print(f"  App Name: {APP_NAME}")
    print(f"  Main Script: {MAIN_SCRIPT}")
    print(f"  Output Directory: {DIST_DIR}")
    print(f"  Hidden Imports: {len(HIDDEN_IMPORTS)}")
    print(f"  Collected Submodules: {len(COLLECT_SUBMODULES)}")
    
    # Run PyInstaller
    print("\n" + "=" * 60)
    print("Running PyInstaller...")
    print("=" * 60)
    
    try:
        from PyInstaller.__main__ import run
        run(pyinstaller_cmd)
        
        # Check if build was successful
        exe_path = DIST_DIR / f"{APP_NAME}.exe" if sys.platform == "win32" else DIST_DIR / APP_NAME
        if exe_path.exists():
            print("\n" + "=" * 60)
            print("BUILD SUCCESSFUL!")
            print(f"Executable created: {exe_path}")
            print(f"Size: {exe_path.stat().st_size / 1024 / 1024:.2f} MB")
            print("=" * 60)
        else:
            print("\nERROR: Build completed but executable not found!")
            sys.exit(1)
            
    except Exception as e:
        print(f"\nBUILD FAILED: {e}")
        sys.exit(1)
    
    # Optional: Test the executable
    if "--test" in sys.argv and exe_path.exists():
        print("\nTesting executable...")
        try:
            result = subprocess.run([str(exe_path), "--version"], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=10)
            if result.returncode == 0:
                print("✓ Executable runs successfully")
            else:
                print(f"✗ Executable returned error code {result.returncode}")
                if result.stderr:
                    print(f"Error: {result.stderr}")
        except Exception as e:
            print(f"✗ Failed to test executable: {e}")


if __name__ == "__main__":
    main()