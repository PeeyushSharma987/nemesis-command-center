import subprocess
import urllib.request
import zipfile
from pathlib import Path

CURRENT = Path(__file__).resolve().parent
BASE_DIR = CURRENT if (CURRENT / "backend").exists() else CURRENT / "nemesis-core"
TOOLS_ZIP = BASE_DIR / "platform-tools.zip"
ADB_EXE = BASE_DIR / "platform-tools" / "adb.exe"

# 1. Download official Google Android Platform Tools if not already present
if not ADB_EXE.exists():
    print("[1/3] Downloading official Google ADB Platform Tools (~12 MB)...")
    url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
    urllib.request.urlretrieve(url, TOOLS_ZIP)
    print("[2/3] Extracting adb.exe into nemesis-core/platform-tools/...")
    with zipfile.ZipFile(TOOLS_ZIP, "r") as zf:
        zf.extractall(BASE_DIR)
    TOOLS_ZIP.unlink(missing_ok=True)
else:
    print("[1/3] adb.exe already installed in nemesis-core/platform-tools/!")

# 2. Update android_swarm_adb.py so N.E.M.E.S.I.S. uses this exact adb.exe path automatically
print("[3/3] Linking N.E.M.E.S.I.S. Hardware Swarm Bridge to local adb.exe...")
(BASE_DIR / "device_bridge" / "android_swarm_adb.py").write_text(
    '''import asyncio
import shutil
from pathlib import Path
from typing import Any, Dict, List

LOCAL_ADB = Path(__file__).resolve().parents[1] / "platform-tools" / "adb.exe"


class AndroidSwarmBridge:
    """Executes parallel hardware commands across connected Android phones via local ADB."""

    @staticmethod
    def get_adb_path() -> str:
        if LOCAL_ADB.exists():
            return str(LOCAL_ADB)
        return shutil.which("adb") or ""

    @classmethod
    async def list_connected_phones(cls) -> List[str]:
        adb_bin = cls.get_adb_path()
        if not adb_bin:
            return ["SIMULATED_PHONE_1", "SIMULATED_PHONE_2", "SIMULATED_PHONE_3"]
        proc = await asyncio.create_subprocess_exec(
            adb_bin, "devices", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        lines = stdout.decode("utf-8", errors="ignore").strip().splitlines()[1:]
        devices = [line.split()[0] for line in lines if "device" in line and not line.startswith("*")]
        return devices or ["SIMULATED_PHONE_1", "SIMULATED_PHONE_2", "SIMULATED_PHONE_3"]

    @classmethod
    async def _run_adb_on_device(cls, serial: str, args: List[str]) -> str:
        adb_bin = cls.get_adb_path()
        if serial.startswith("SIMULATED_") or not adb_bin:
            await asyncio.sleep(0.15)
            return f"{serial}: simulated {' '.join(args)}"
        cmd = [adb_bin, "-s", serial] + args
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        return (stdout or stderr).decode("utf-8", errors="ignore").strip()

    @classmethod
    async def unlock_all_devices(cls, pin_code: str = "") -> Dict[str, Any]:
        devices = await cls.list_connected_phones()
        tasks = []
        for dev in devices:
            tasks.append(cls._run_adb_on_device(dev, ["shell", "input", "keyevent", "224"]))
            tasks.append(cls._run_adb_on_device(dev, ["shell", "input", "swipe", "500", "1500", "500", "400"]))
            if pin_code:
                tasks.append(cls._run_adb_on_device(dev, ["shell", "input", "text", pin_code]))
                tasks.append(cls._run_adb_on_device(dev, ["shell", "input", "keyevent", "66"]))
        await asyncio.gather(*tasks)
        return {
            "action": "UNLOCK_ALL_MOBILE_DEVICES",
            "devices_unlocked": devices,
            "count": len(devices),
            "status": "ALL_DEVICES_UNLOCKED",
        }

    @classmethod
    async def play_song_across_swarm(cls, youtube_url: str) -> Dict[str, Any]:
        devices = await cls.list_connected_phones()
        tasks = [
            cls._run_adb_on_device(
                dev, ["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", youtube_url]
            )
            for dev in devices
        ]
        await asyncio.gather(*tasks)
        return {
            "action": "SYNC_MEDIA_SWARM",
            "devices_synced": devices,
            "media_url": youtube_url,
            "status": "PLAYING_ON_ALL_DEVICES",
        }
''',
    encoding="utf-8",
)

print("\n--- CHECKING CONNECTED ANDROID PHONES ---")
subprocess.run([str(ADB_EXE), "devices"], check=False)
print("\nDone! Plug in your phone with USB Debugging enabled and tap 'Allow' on your phone screen.")
