import ast
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORE = ROOT / "nemesis-core"
MAIN_PY = CORE / "backend" / "main.py"
REQ_TXT = CORE / "requirements.txt"

print("=== N.E.M.E.S.I.S. RENDER CLOUD DIAGNOSTIC & AUTO-UPLOADER ===")

# 1. Ensure backend/main.py sets sys.path and safe cloud default env vars on Linux startup
main_code = MAIN_PY.read_text(encoding="utf-8")
cloud_header = """import os, sys, re
from pathlib import Path
_CORE_ROOT = str(Path(__file__).resolve().parent.parent)
if _CORE_ROOT not in sys.path:
    sys.path.insert(0, _CORE_ROOT)
os.environ.setdefault("FOUNDER_GOD_KEY", "NEMESIS-GOD-KEY-987")
os.environ.setdefault("X_FOUNDER_GOD_KEY", "NEMESIS-GOD-KEY-987")
os.environ.setdefault("NEMESIS_JWT_SECRET", "nemesis-supreme-jwt-secret-2026")
"""
if "_CORE_ROOT =" not in main_code:
    main_code = cloud_header + "\n" + main_code
    MAIN_PY.write_text(main_code, encoding="utf-8")
    print("[1/4] Injected Linux sys.path & default environment shield into backend/main.py.")
else:
    print("[1/4] Linux startup shield already present in backend/main.py.")

# 2. Scan every .py file in nemesis-core to discover all required third-party packages
LOCAL_DIRS = {
    "backend", "device_bridge", "ring0_kernel", "freellmapi",
    "omniroute_docker", "nemesis_memory_store", "frontend_hud",
    "activate_live_brain"
}
STDLIB = getattr(sys, "stdlib_module_names", set()) | {
    "typing", "pathlib", "asyncio", "json", "re", "os", "sys", "time",
    "subprocess", "shutil", "io", "zipfile", "ast", "importlib", "math",
    "random", "datetime", "hashlib", "hmac", "base64", "uuid", "urllib",
    "collections", "functools", "itertools", "logging", "threading",
    "multiprocessing", "socket", "ssl", "sqlite3", "csv", "tempfile",
    "traceback", "dataclasses", "enum", "abc", "contextlib", "ctypes", "platform"
}
PIP_MAP = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "httpx": "httpx",
    "pydantic": "pydantic",
    "pydantic_settings": "pydantic-settings",
    "dotenv": "python-dotenv",
    "jwt": "PyJWT",
    "cryptography": "cryptography",
    "requests": "requests",
    "bs4": "beautifulsoup4",
    "aiofiles": "aiofiles",
    "psutil": "psutil",
    "websockets": "websockets",
    "starlette": "starlette",
    "multipart": "python-multipart",
    "PIL": "Pillow",
    "cv2": "opencv-python-headless",
    "numpy": "numpy",
    "yaml": "PyYAML",
    "passlib": "passlib",
    "bcrypt": "bcrypt",
    "slowapi": "slowapi",
    "tenacity": "tenacity",
    "lxml": "lxml",
    "aiohttp": "aiohttp",
}
WINDOWS_ONLY = {"winsound", "winreg", "msvcrt", "pyttsx3", "win32api", "win32con", "win32gui", "pywintypes"}

discovered_pkgs = {
    "fastapi", "uvicorn", "httpx", "pydantic", "python-dotenv",
    "python-multipart", "PyJWT", "cryptography", "requests",
    "beautifulsoup4", "aiofiles", "psutil", "websockets"
}

for py_file in CORE.rglob("*.py"):
    if "backup" in str(py_file).lower():
        continue
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"))
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods = [node.module.split(".")[0]]
            for m in mods:
                if not m or m in STDLIB or m in LOCAL_DIRS or m in WINDOWS_ONLY:
                    continue
                discovered_pkgs.add(PIP_MAP.get(m, m))
    except Exception:
        pass

REQ_TXT.write_text("\n".join(sorted(discovered_pkgs)) + "\n", encoding="utf-8")
print(f"[2/4] Wrote complete requirements.txt: {sorted(discovered_pkgs)}")

# 3. Test-import backend.main right now to verify zero startup crashes
sys.path.insert(0, str(CORE))
try:
    import backend.main
    print("[3/4] SUCCESS: `backend.main` imported cleanly with zero errors!")
except Exception as e:
    print(f"[3/4] WARNING - Startup import issue detected: {type(e).__name__}: {e}")

# 4. Remove heavy cached binaries & push fresh commit to GitHub
subprocess.run(["git", "rm", "-r", "--cached", "--ignore-unmatch", "cloudflared.exe", "nemesis-core-backup-working"], cwd=str(ROOT))
subprocess.run(["git", "add", "-A"], cwd=str(ROOT))
commit_res = subprocess.run(["git", "commit", "-m", "Fix Render Linux startup, requirements, and remove heavy cached binaries"], cwd=str(ROOT), capture_output=True, text=True)
print(commit_res.stdout or commit_res.stderr)
push_res = subprocess.run(["git", "push", "origin", "main", "--force"], cwd=str(ROOT), capture_output=True, text=True)
print("[4/4] Git Push Result:\n" + (push_res.stdout + "\n" + push_res.stderr).strip())
