import subprocess
import sys
import os
import shutil

def build():
    print("Starting PyInstaller build for AutoDraw V2...")

    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name=AutoDraw",
        "--clean",
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=PySide6.QtSvg",
        "--hidden-import=opencv-python",
        "--hidden-import=pynput.keyboard",
        "main.py"
    ]

    result = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
    if result.returncode == 0:
        exe_path = os.path.abspath("dist/AutoDraw.exe")
        print("\n==========================================")
        print(f" SUCCESS! AutoDraw V2 Executable created at:")
        print(f" {exe_path}")
        print("==========================================\n")
    else:
        print("\n==========================================")
        print(" ERROR: PyInstaller build failed.")
        print("==========================================\n")

if __name__ == "__main__":
    build()
