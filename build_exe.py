import os
import subprocess
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from src import __version__  # noqa: E402

# Module names as the interpreter imports them. "opencv-python" was listed
# before, which is the distribution name; PyInstaller silently ignores it.
HIDDEN_IMPORTS = (
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtSvg",
    "cv2",
    "numpy",
    "PIL.Image",
    "pynput.keyboard",
    "pynput.keyboard._win32",
    "pynput.mouse._win32",
)

EXCLUDES = ("tkinter", "matplotlib", "scipy", "pytest")


def build(one_dir: bool = False) -> int:
    layout = "--onedir" if one_dir else "--onefile"
    print(f"Starting PyInstaller build for AutoDraw {__version__} ({layout})...")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        layout,
        "--windowed",
        "--name=AutoDraw",
        "--clean",
        f"--distpath={os.path.join(PROJECT_DIR, 'dist')}",
        f"--workpath={os.path.join(PROJECT_DIR, 'build')}",
        f"--specpath={PROJECT_DIR}",
    ]
    cmd += [f"--hidden-import={name}" for name in HIDDEN_IMPORTS]
    cmd += [f"--exclude-module={name}" for name in EXCLUDES]

    icon_path = os.path.join(PROJECT_DIR, "assets", "autodraw.ico")
    if os.path.exists(icon_path):
        cmd.append(f"--icon={icon_path}")

    cmd.append(os.path.join(PROJECT_DIR, "main.py"))

    result = subprocess.run(cmd, cwd=PROJECT_DIR)

    if result.returncode != 0:
        print("\n" + "=" * 42)
        print(f" ERROR: PyInstaller build failed (exit {result.returncode}).")
        print("=" * 42 + "\n")
        return result.returncode

    # Resolve against the project directory, not the current working directory.
    dist = os.path.join(PROJECT_DIR, "dist")
    exe_path = os.path.join(dist, "AutoDraw", "AutoDraw.exe") if one_dir else os.path.join(dist, "AutoDraw.exe")
    size_mb = os.path.getsize(exe_path) / (1024 * 1024) if os.path.exists(exe_path) else 0.0

    print("\n" + "=" * 42)
    print(f" SUCCESS! AutoDraw {__version__} executable created at:")
    print(f" {exe_path}  ({size_mb:.1f} MB)")
    if not one_dir:
        # --onefile unpacks the whole bundle to %TEMP% on every launch, which
        # costs several seconds with PySide6 and OpenCV inside.
        print(" Tip: build with 'pasta' (--onedir) for much faster startup.")
    print("=" * 42 + "\n")
    return 0


if __name__ == "__main__":
    # "pasta" / "onedir" / "--onedir" all select the faster folder layout.
    requested = {arg.lower().lstrip("-") for arg in sys.argv[1:]}
    sys.exit(build(one_dir=bool(requested & {"pasta", "onedir", "dir"})))
