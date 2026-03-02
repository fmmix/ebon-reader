from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent
FRONTEND_BIN_DIR = BACKEND_DIR.parent / "frontend" / "src-tauri" / "binaries"
ENTRYPOINT = BACKEND_DIR / "sidecar_main.py"
PYINSTALLER_NAME = "ebon_backend"
WINDOWS_TARGET_NAME = "ebon_backend-x86_64-pc-windows-msvc.exe"


def build_sidecar() -> int:
    if not ENTRYPOINT.exists():
        print(f"ERROR: Missing sidecar entrypoint: {ENTRYPOINT}")
        return 1

    for stale_path in (
        BACKEND_DIR / "build",
        BACKEND_DIR / "dist",
        BACKEND_DIR / "sidecar_main.spec",
    ):
        if stale_path.is_dir():
            shutil.rmtree(stale_path)
        elif stale_path.exists():
            stale_path.unlink()

    print("Building backend sidecar with PyInstaller...")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--clean",
            "--noconfirm",
            "--onefile",
            "--noconsole",
            "--name",
            PYINSTALLER_NAME,
            str(ENTRYPOINT),
        ],
        cwd=BACKEND_DIR,
        check=False,
    )
    if result.returncode != 0:
        print("ERROR: PyInstaller build failed.")
        return result.returncode

    built_binary = BACKEND_DIR / "dist" / f"{PYINSTALLER_NAME}.exe"
    if not built_binary.exists():
        print(f"ERROR: Built binary not found: {built_binary}")
        return 1

    FRONTEND_BIN_DIR.mkdir(parents=True, exist_ok=True)
    destination = FRONTEND_BIN_DIR / WINDOWS_TARGET_NAME
    shutil.copy2(built_binary, destination)

    print(f"SUCCESS: Sidecar binary copied to: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(build_sidecar())
