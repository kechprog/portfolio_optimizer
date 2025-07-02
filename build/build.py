# build.py
import os
import sys
import subprocess
from pathlib import Path

# === Configuration ===
BASE_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = BASE_DIR.parent  # Go up one level to project root
ICON_PATH = str(BASE_DIR / "icon.png")  # Path to your application icon
print(ICON_PATH)
ENV_PATH = str(PROJECT_ROOT / ".env")  # Path to your environment file
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
    f"--add-data={ENV_PATH}{os.pathsep}.",  # Include .env
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
        print(f"ERROR: .env file not found at {ENV_PATH}")
        print("The .env file is required for the application to work properly.")
        print("Please create the .env file with your Alpha Vantage API key before building.")
        sys.exit(1)
    else:
        print(f"Found .env file at {ENV_PATH}")
    
    # 3. Run PyInstaller
    print("Running PyInstaller...")
    from PyInstaller import __main__ as pyi_main
    pyi_main.run([*PYINSTALLER_OPTIONS, str(BASE_DIR / MAIN_SCRIPT)])
    
    # 4. Cleanup (optional)
    # Add cleanup logic here if needed
    
    print(f"\nBuild complete! Executable is in: {BASE_DIR}/dist")