# build.py
import os
import sys
from pathlib import Path

# Configuration
BASE_DIR = Path(__file__).parent.resolve()
ICON_PATH = str(BASE_DIR / "icon.png")  # Path to your application icon
print(ICON_PATH)
ENV_PATH = str(BASE_DIR / ".env")  # Path to your environment file
APP_NAME = "PortfolioOptimizer"
MAIN_SCRIPT = "../app.py"
TEMP_DIR = "build_temp"

# PyInstaller options
PYINSTALLER_OPTIONS = [
    "--onefile",  # Create single executable
    "--clean",  # Clean build artifacts
    f"--workpath={TEMP_DIR}/pyinstaller",
    f"--distpath=dist",
    f"--name={APP_NAME}",
    "--optimize=2",
    "--hidden-import=scipy._lib.messagestream",
    "--hidden-import=scipy.sparse.csgraph._validation",
    "--hidden-import=scipy.sparse._matrix",
    "--hidden-import=scipy.special._ufuncs_cxx",
    "--hidden-import=scipy.linalg.cython_blas",
    "--hidden-import=scipy.linalg.cython_lapack",
    "--hidden-import=scipy.integrate",
    "--hidden-import=scipy.integrate.quadrature",
    "--hidden-import=scipy.integrate.odepack",
    "--hidden-import=scipy.integrate._odepack",
    "--hidden-import=scipy.integrate.quadpack",
    "--hidden-import=scipy.integrate._quadpack",
    "--hidden-import=scipy.integrate._ode",
    "--hidden-import=scipy.integrate.vode",
    "--hidden-import=scipy.integrate._dop",
    "--hidden-import=scipy._lib._ccallback",
    "--hidden-import=scipy._cyutility",
    "--collect-submodules=scipy",
    f"--add-data={BASE_DIR.parent / '.env'}{os.pathsep}.",  # Include .env
]

# Resize icon and convert to ICO format (if needed)
def prepare_icon(input_path, output_path):
    """Resize icon to appropriate sizes and save as ICO format"""
    print(f"Preparing icon: {input_path} -> {output_path}")
    from PIL import Image
    
    original = Image.open(input_path)
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    resized_images = []
    
    for size in sizes:
        resize_img = original.resize(size, Image.LANCZOS)
        resized_images.append(resize_img)
    
    resized_images[0].save(output_path, format="ICO", sizes=[s for s in sizes])
    print("Icon resizing complete")

if __name__ == "__main__":
    print("Starting build process...")
    
    # 1. Handle icon preparation
    if not Path(ICON_PATH).exists():
        user_icon = input("No icon found at configured path. Enter path to source icon (or press Enter to skip): ").strip()
        if not user_icon:
            print("Skipping icon setup")
        else:
            ICON_PATH = user_icon

    if Path(ICON_PATH).exists():
        prepare_icon(ICON_PATH, BASE_DIR / "app_icon.ico")
        PYINSTALLER_OPTIONS.append(f"--icon={BASE_DIR}/app_icon.ico")
    
    # 2. Ensure .env exists
    if not Path(ENV_PATH).exists():
        print(f"Warning: .env file not found at {ENV_PATH}")
    
    # 4. Run PyInstaller
    print("Running PyInstaller...")
    from PyInstaller import __main__ as pyi_main
    pyi_main.run([*PYINSTALLER_OPTIONS, str(BASE_DIR / MAIN_SCRIPT)])
    
    # 5. Cleanup (optional)
    # Add cleanup logic here if needed
    
    print(f"\nBuild complete! Executable is in: {BASE_DIR}/dist")