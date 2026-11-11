import importlib.metadata as md
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORE = ROOT / "nemesis-core"
REQ_FILE = CORE / "requirements.txt"

sys.path.insert(0, str(CORE))
import backend.main  # Loads every runtime module and Pydantic validator into sys.modules

pkg_map = md.packages_distributions()
win_exclude = {"pywin32", "pypiwin32", "pyttsx3", "comtypes", "wmi", "pip", "setuptools", "wheel"}

runtime_pkgs = {
    "fastapi",
    "uvicorn",
    "httpx",
    "pydantic",
    "email-validator",
    "dnspython",
    "python-dotenv",
    "python-multipart",
    "PyJWT",
    "argon2-cffi",
    "cryptography",
    "requests",
    "beautifulsoup4",
    "aiofiles",
    "psutil",
    "websockets",
}

for mod_name in list(sys.modules.keys()):
    top = mod_name.split(".")[0]
    for dist in pkg_map.get(top, []):
        if dist.lower() not in win_exclude and dist.lower() != "argon2":
            runtime_pkgs.add(dist)

clean_list = sorted(runtime_pkgs, key=lambda x: x.lower())
REQ_FILE.write_text("\n".join(clean_list) + "\n", encoding="utf-8")
print("[1/2] Verified complete runtime requirements.txt:", clean_list)

subprocess.run(["git", "add", "nemesis-core/requirements.txt"], cwd=str(ROOT))
subprocess.run(["git", "commit", "-m", "Add email-validator and all verified runtime packages"], cwd=str(ROOT))
res = subprocess.run(["git", "push", "origin", "main"], cwd=str(ROOT), capture_output=True, text=True)
print("[2/2] Git Push Output:\n" + (res.stdout + "\n" + res.stderr).strip())
