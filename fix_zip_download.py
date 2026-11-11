import ast
import io
import re
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORE = ROOT / "nemesis-core"
MAIN_PY = CORE / "backend" / "main.py"

main_txt = MAIN_PY.read_text(encoding="utf-8")

# 1. Bypass the middleware completely for binary file downloads
main_txt = main_txt.replace(
    "async def nemesis_ai_and_vision_interceptor(request: Request, call_next):\n    body_bytes = await request.body()",
    "async def nemesis_ai_and_vision_interceptor(request: Request, call_next):\n    if '/download-kit' in request.url.path:\n        return await call_next(request)\n    body_bytes = await request.body()",
)

# 2. Remove any existing /api/v1/bridge/download-kit function definitions so there are zero duplicates
main_txt = re.sub(
    r"@app\.get\(\"/api/v1/bridge/download-kit\"\)\s*async def download_device_bridge_kit.*?(?=\n@app\.|\n# --- LIVE AI & VISION FALLBACK INTERCEPTOR ---|\Z)",
    "",
    main_txt,
    flags=re.S,
)

# 3. Append a rock-solid raw-string ZIP builder using atomic Response bytes
safe_download_route = r'''

@app.get("/api/v1/bridge/download-kit")
async def download_device_bridge_kit(server_url: str = "http://localhost:8000", user_id: str = "friend_node"):
    from fastapi.responses import Response
    clean_server = (server_url or "http://localhost:8000").rstrip("/")
    clean_uid = re.sub(r"[^a-z0-9_]", "_", (user_id or "friend_node").lower().strip()) or "friend_node"

    readme_txt = (
        "====================================================================\r\n"
        "   N.E.M.E.S.I.S. v3.5 - 2-WAY TELEMETRY & HARDWARE BRIDGE KIT\r\n"
        "====================================================================\r\n"
        f"Personal User ID    : {clean_uid}\r\n"
        f"Connected Cloud Core: {clean_server}\r\n\r\n"
        "HOW TO USE:\r\n"
        "1. Right-click this ZIP file and click 'Extract All...'.\r\n"
        "2. Plug your Android phone into your laptop via USB cable\r\n"
        "   (ensure USB Debugging is ON in Developer Options).\r\n"
        "3. Double-click start_device_bridge.bat inside the extracted folder.\r\n"
        "====================================================================\r\n"
    )

    bridge_py_template = r"""import json
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

SERVER_URL = "__SERVER_URL__"
USER_ID = "__USER_ID__"
HERE = Path(__file__).resolve().parent
LOCAL_ADB = HERE / "platform-tools" / "adb.exe"

print("=================================================================")
print("  N.E.M.E.S.I.S. v3.5 - REAL-TIME TELEMETRY & HARDWARE BRIDGE")
print("  Personal Profile ID : " + USER_ID)
print("  Connected Web Core  : " + SERVER_URL)
print("=================================================================")

def ensure_adb():
    if LOCAL_ADB.exists():
        return str(LOCAL_ADB)
    sys_adb = shutil.which("adb")
    if sys_adb:
        return sys_adb
    print("[1/3] Downloading official Google Android Platform-Tools...")
    zip_path = HERE / "platform-tools.zip"
    urllib.request.urlretrieve("https://dl.google.com/android/repository/platform-tools-latest-windows.zip", str(zip_path))
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(HERE)
    try:
        zip_path.unlink()
    except Exception:
        pass
    return str(LOCAL_ADB)

adb_exe = ensure_adb()
subprocess.run([adb_exe, "start-server"])

def run_adb(dev, args, timeout=6):
    try:
        p = subprocess.run([adb_exe, "-s", dev] + args, capture_output=True, text=True, errors="ignore", timeout=timeout)
        return (p.stdout or "").strip()
    except Exception:
        return ""

def collect_telemetry(dev, include_contacts=False):
    model = run_adb(dev, ["shell", "getprop", "ro.product.model"], timeout=4)
    call_out = run_adb(dev, ["shell", 'content query --uri content://call_log/calls --projection number:name:type:date --sort "date DESC"'], timeout=6)
    missed = []
    for line in call_out.splitlines():
        m_t = re.search(r"\btype=(\d+)", line)
        if not m_t or m_t.group(1) not in ("3", "5"):
            continue
        m_d = re.search(r"\bdate=(\d+)", line)
        ts = int(m_d.group(1)) if m_d else 0
        m_num = re.search(r"\bnumber=([^,\s]+)", line)
        num = m_num.group(1).strip() if m_num else ""
        if not num or num.upper() == "NULL":
            continue
        m_name = re.search(r"\bname=([^,]+)", line)
        name = m_name.group(1).strip() if m_name else ""
        if name.upper() == "NULL":
            name = ""
        missed.append({"ts": ts, "number": num, "name": name})
    missed.sort(key=lambda x: x["ts"], reverse=True)
    latest_call = None
    if missed:
        c = missed[0]
        t_str = time.strftime("%I:%M %p", time.localtime(c["ts"] / 1000.0)) if c["ts"] else "Recent"
        latest_call = {
            "type": "missed_call",
            "sender": c["name"] or c["number"],
            "number": c["number"],
            "ts": c["ts"],
            "content": "Latest Missed Call at " + t_str + " (" + c["number"] + ")",
        }

    wa_list = []
    notif_out = run_adb(dev, ["shell", "dumpsys notification --noredact"], timeout=6)
    if notif_out and "com.whatsapp" in notif_out:
        for blk in notif_out.split("NotificationRecord(")[1:]:
            if "com.whatsapp" not in blk:
                continue
            mt = re.search(r"android\.title=(?:String\s*\()?([^\n\r\)]+)", blk)
            mx = re.search(r"android\.text=(?:String\s*\()?([^\n\r\)]+)", blk)
            if mt and mx:
                sv, bv = mt.group(1).strip(), mx.group(1).strip()
                if sv.lower() not in ("whatsapp", "you", "backup in progress") and "new messages" not in bv.lower():
                    wa_list.append({"sender": sv, "content": bv})

    contacts_map = {}
    if include_contacts:
        c_out = run_adb(dev, ["shell", "content query --uri content://com.android.contacts/data/phones --projection display_name:data1"], timeout=8)
        for line in c_out.splitlines():
            mn = re.search(r"display_name=([^,]+)", line)
            mp = re.search(r"data1=([^\s,]+)", line)
            if mn and mp:
                dn = mn.group(1).strip().lower()
                dg = re.sub(r"\D", "", mp.group(1))
                if len(dg) >= 10:
                    contacts_map[dn] = "91" + dg[-10:]

    return model, latest_call, wa_list[-5:], contacts_map

def execute_remote_action(dev, cmd_obj):
    act = cmd_obj.get("action")
    pay = cmd_obj.get("payload", {})
    print("\n[EXECUTING N.E.M.E.S.I.S. COMMAND ON YOUR PHONE]: " + str(act) + " -> " + str(pay))

    if act == "unlock":
        run_adb(dev, ["shell", "input", "keyevent", "224"])
        run_adb(dev, ["shell", "input", "swipe", "500", "1600", "500", "400", "300"])
    elif act == "hangup":
        run_adb(dev, ["shell", "input", "keyevent", "KEYCODE_ENDCALL"])
    elif act == "play_song":
        q = urllib.parse.quote(pay.get("query", "Cyberpunk Synthwave"))
        run_adb(dev, ["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", "https://www.youtube.com/results?search_query=" + q])
    elif act == "phone_call":
        target = pay.get("number") or ""
        msg = pay.get("message") or ""
        run_adb(dev, ["shell", "am", "start", "-a", "android.intent.action.CALL", "-d", "tel:+" + target])
        time.sleep(2.5)
        run_adb(dev, ["shell", "cmd", "audio", "set-communication-device", "2"])
        if msg:
            time.sleep(6.5)
            clean_m = re.sub(r"[^a-zA-Z0-9,.?!\s]", " ", msg.replace("'", "")).strip()
            ps_tts = "Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Rate = 0; $s.Speak('Hello, I am Nemesis. " + clean_m + "')"
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_tts], timeout=20)
    elif act == "whatsapp_send":
        target = pay.get("number") or ""
        msg = pay.get("message") or ""
        enc = urllib.parse.quote(msg)
        run_adb(dev, ["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", "https://api.whatsapp.com/send?phone=" + target + "&text=" + enc])
        time.sleep(3.5)
        run_adb(dev, ["shell", "input", "keyevent", "22"])
        run_adb(dev, ["shell", "input", "keyevent", "66"])
        run_adb(dev, ["shell", "input", "tap", "995", "2165"])

wireless_target = ""
contacts_synced = False

while True:
    try:
        out = subprocess.check_output([adb_exe, "devices"], text=True, timeout=5)
        if "unauthorized" in out.lower():
            print("[ACTION NEEDED] Unlock your phone screen and tap 'Allow USB Debugging'!")
        devs = [l.split()[0] for l in out.splitlines()[1:] if l.strip() and "\tdevice" in l]
        if devs:
            usb_dev = next((d for d in devs if ":" not in d), None)
            if usb_dev and not wireless_target:
                print("[*] USB Phone detected (" + usb_dev + ")! Bridging to Wireless ADB (Port 5555)...")
                subprocess.run([adb_exe, "-s", usb_dev, "tcpip", "5555"], capture_output=True, text=True, timeout=6)
                time.sleep(1.8)
                ip_out = run_adb(usb_dev, ["shell", "ip -f inet addr show wlan0"])
                m_ip = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", ip_out)
                if m_ip:
                    wireless_target = m_ip.group(1) + ":5555"
                    subprocess.run([adb_exe, "connect", wireless_target], capture_output=True, text=True, timeout=6)
                    print("[SUCCESS] Wireless ADB established at " + wireless_target + "! You can now unplug your USB cable.")

            active_dev = wireless_target if (wireless_target and wireless_target in devs) else devs[0]
            model, latest_call, wa_list, c_map = collect_telemetry(active_dev, include_contacts=(not contacts_synced))
            if c_map:
                contacts_synced = True

            hb_payload = {
                "user_id": USER_ID,
                "device_serial": active_dev,
                "wireless_ip": active_dev,
                "phone_model": model,
                "latest_missed_call": latest_call,
                "whatsapp_alerts": wa_list,
                "contacts": c_map if c_map else None,
            }
            req = urllib.request.Request(
                SERVER_URL + "/api/v1/bridge/remote-heartbeat",
                data=json.dumps(hb_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for cmd_obj in data.get("commands", []):
                    execute_remote_action(active_dev, cmd_obj)

            call_info = (" | Latest Missed Call: " + latest_call["sender"]) if latest_call else ""
            print("[ONLINE & SYNCED] " + active_dev + " (" + model + ") -> Profile '" + USER_ID + "'" + call_info)
    except Exception:
        pass
    time.sleep(3)
"""

    bridge_py = bridge_py_template.replace("__SERVER_URL__", clean_server).replace("__USER_ID__", clean_uid)
    start_bat = "@echo off\r\ntitle N.E.M.E.S.I.S. v3.5 Hardware Bridge\r\ncd /d \"%~dp0\"\r\npython nemesis_client_bridge.py\r\npause\r\n"

    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("NEMESIS_Device_Bridge/README_FIRST.txt", readme_txt.encode("utf-8"))
        zf.writestr("NEMESIS_Device_Bridge/nemesis_client_bridge.py", bridge_py.encode("utf-8"))
        zf.writestr("NEMESIS_Device_Bridge/start_device_bridge.bat", start_bat.encode("utf-8"))

    zip_bytes = mem_zip.getvalue()
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="NEMESIS_Device_Bridge_Kit.zip"',
            "Content-Length": str(len(zip_bytes)),
            "Cache-Control": "no-store",
        },
    )
'''

if "# --- LIVE AI & VISION FALLBACK INTERCEPTOR ---" in main_txt:
    main_txt = main_txt.replace(
        "# --- LIVE AI & VISION FALLBACK INTERCEPTOR ---",
        safe_download_route.strip() + "\n\n\n# --- LIVE AI & VISION FALLBACK INTERCEPTOR ---",
    )
else:
    main_txt = main_txt.rstrip() + "\n" + safe_download_route

ast.parse(main_txt)
MAIN_PY.write_text(main_txt, encoding="utf-8")
print("[1/3] Replaced /api/v1/bridge/download-kit with atomic byte Response and zero f-string braces.")

# 4. Self-test the endpoint right now using FastAPI TestClient / asyncio
import asyncio
import sys
sys.path.insert(0, str(CORE))
from backend.main import download_device_bridge_kit

resp = asyncio.run(download_device_bridge_kit("https://nemesis-command-center.onrender.com", "peeyush_sharma"))
with zipfile.ZipFile(io.BytesIO(resp.body), "r") as zf:
    bad_file = zf.testzip()
    names = zf.namelist()
    assert bad_file is None and len(names) == 3, "ZIP test failed!"
print(f"[2/3] ZIP ARCHIVE SELF-TEST PASSED ({len(resp.body)} bytes, files: {names})")

subprocess.run(["git", "add", "-A"], cwd=str(ROOT))
subprocess.run(["git", "commit", "-m", "Fix download-kit ZIP archive response bytes and bypass middleware"], cwd=str(ROOT))
push_out = subprocess.run(["git", "push", "origin", "main"], cwd=str(ROOT), capture_output=True, text=True)
print("[3/3] Git Push Output:\n" + (push_out.stdout + "\n" + push_out.stderr).strip())
