import ast
import io
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORE = ROOT / "nemesis-core"
MAIN_PY = CORE / "backend" / "main.py"

NEW_BRIDGE_TEMPLATE = r"""import getpass
import json
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
PIN_CACHE_FILE = HERE / ".phone_pin_cache"

print("=================================================================")
print("  N.E.M.E.S.I.S. v3.6 - ZERO-RESET TELEMETRY & PIN UNLOCK BRIDGE")
print("  Personal Profile ID : " + USER_ID)
print("  Connected Web Core  : " + SERVER_URL)
print("=================================================================")

PHONE_PIN = ""
if PIN_CACHE_FILE.exists():
    PHONE_PIN = PIN_CACHE_FILE.read_text(encoding="utf-8", errors="ignore").strip()

user_pin_input = input("[SETUP] Enter your phone lockscreen PIN/Password for Auto-Unlock (or press Enter to keep saved): ").strip()
if user_pin_input:
    PHONE_PIN = user_pin_input
    try:
        PIN_CACHE_FILE.write_text(PHONE_PIN, encoding="utf-8")
    except Exception:
        pass

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

def unlock_phone_screen(dev):
    run_adb(dev, ["shell", "input", "keyevent", "224"])
    time.sleep(0.4)
    run_adb(dev, ["shell", "wm", "dismiss-keyguard"])
    run_adb(dev, ["shell", "input", "swipe", "600", "2000", "600", "400", "300"])
    if PHONE_PIN:
        time.sleep(0.9)
        run_adb(dev, ["shell", "input", "text", PHONE_PIN])
        time.sleep(0.2)
        run_adb(dev, ["shell", "input", "keyevent", "66"])

def collect_telemetry(dev, include_contacts=False, contacts_store=None):
    if contacts_store is None:
        contacts_store = {}
    model = run_adb(dev, ["shell", "getprop", "ro.product.model"], timeout=4)
    call_out = run_adb(dev, ["shell", 'content query --uri content://call_log/calls --projection number:name:type:date --sort "date DESC"'], timeout=6)
    missed = []
    for line in call_out.splitlines():
        m_num = re.search(r"\bnumber=([^,\s]+)", line)
        num = m_num.group(1).strip() if m_num else ""
        m_name = re.search(r"\bname=([^,]+)", line)
        name = m_name.group(1).strip() if m_name else ""
        if name.upper() == "NULL":
            name = ""
        if name and num and num.upper() != "NULL":
            dg = re.sub(r"\D", "", num)
            if len(dg) >= 10:
                contacts_store[name.lower()] = "91" + dg[-10:]
        m_t = re.search(r"\btype=(\d+)", line)
        if not m_t or m_t.group(1) not in ("3", "5"):
            continue
        if not num or num.upper() == "NULL":
            continue
        m_d = re.search(r"\bdate=(\d+)", line)
        ts = int(m_d.group(1)) if m_d else 0
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

    if include_contacts:
        c_out = run_adb(dev, ["shell", "content query --uri content://com.android.contacts/data/phones --projection display_name:data1"], timeout=8)
        for line in c_out.splitlines():
            mn = re.search(r"display_name=([^,]+)", line)
            mp = re.search(r"data1=([^\s,]+)", line)
            if mn and mp:
                dn = mn.group(1).strip().lower()
                dg = re.sub(r"\D", "", mp.group(1))
                if len(dg) >= 10:
                    contacts_store[dn] = "91" + dg[-10:]

    return model, latest_call, wa_list[-5:], contacts_store

def resolve_number_on_phone(dev, raw_target, contacts_store):
    raw_str = (raw_target or "").strip()
    digits = re.sub(r"\D", "", raw_str)
    if len(digits) >= 10:
        return "+91" + digits[-10:]
    key = raw_str.lower()
    if key in contacts_store:
        return "+" + contacts_store[key].lstrip("+")
    for k, v in contacts_store.items():
        if key and (key in k or k in key):
            return "+" + v.lstrip("+")
    return digits or raw_str

def execute_remote_action(dev, cmd_obj, contacts_store):
    act = cmd_obj.get("action")
    pay = cmd_obj.get("payload", {})
    print("\n[EXECUTING N.E.M.E.S.I.S. COMMAND ON YOUR PHONE]: " + str(act) + " -> " + str(pay))

    if act == "unlock":
        unlock_phone_screen(dev)
    elif act == "hangup":
        run_adb(dev, ["shell", "input", "keyevent", "KEYCODE_ENDCALL"])
    elif act == "play_song":
        unlock_phone_screen(dev)
        q = urllib.parse.quote(pay.get("query", "Cyberpunk Synthwave"))
        run_adb(dev, ["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", "https://www.youtube.com/results?search_query=" + q])
    elif act == "phone_call":
        unlock_phone_screen(dev)
        time.sleep(0.5)
        dial_num = resolve_number_on_phone(dev, pay.get("number") or "", contacts_store)
        msg = pay.get("message") or ""
        print("[DIALING NUMBER]: " + str(dial_num))
        run_adb(dev, ["shell", "am", "start", "-a", "android.intent.action.CALL", "-d", "tel:" + dial_num])
        time.sleep(2.5)
        run_adb(dev, ["shell", "cmd", "audio", "set-communication-device", "2"])
        if msg:
            time.sleep(6.5)
            clean_m = re.sub(r"[^a-zA-Z0-9,.?!\s]", " ", msg.replace("'", "")).strip()
            ps_tts = "Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Rate = 0; $s.Speak('Hello, I am Nemesis. " + clean_m + "')"
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_tts], timeout=20)
    elif act == "whatsapp_send":
        unlock_phone_screen(dev)
        dial_num = resolve_number_on_phone(dev, pay.get("number") or "", contacts_store).lstrip("+")
        msg = pay.get("message") or ""
        enc = urllib.parse.quote(msg)
        run_adb(dev, ["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", "https://api.whatsapp.com/send?phone=" + dial_num + "&text=" + enc])
        time.sleep(3.5)
        run_adb(dev, ["shell", "input", "keyevent", "22"])
        run_adb(dev, ["shell", "input", "keyevent", "66"])
        run_adb(dev, ["shell", "input", "tap", "995", "2165"])

wireless_target = ""
contacts_synced = False
tcpip_attempted = set()
contacts_cache = {}

while True:
    try:
        out = subprocess.check_output([adb_exe, "devices"], text=True, timeout=5)
        if "unauthorized" in out.lower():
            print("[ACTION NEEDED] Unlock your phone screen and tap 'Allow USB Debugging'!")
        devs = [l.split()[0] for l in out.splitlines()[1:] if l.strip() and "\tdevice" in l]
        if devs:
            usb_dev = next((d for d in devs if ":" not in d), None)
            # ONLY attempt USB-to-Wireless tcpip 5555 ONCE per device so Windows File Explorer NEVER loops!
            if usb_dev and not wireless_target and (usb_dev not in tcpip_attempted):
                tcpip_attempted.add(usb_dev)
                print("[*] Attempting one-time Wireless ADB bridge for " + usb_dev + "...")
                ip_found = ""
                for iface_cmd in (["shell", "ip -f inet addr show wlan0"], ["shell", "ip route"]):
                    ip_out = run_adb(usb_dev, iface_cmd)
                    m_ip = re.search(r"(?:inet|src)\s+(\d+\.\d+\.\d+\.\d+)", ip_out)
                    if m_ip and not m_ip.group(1).startswith("127."):
                        ip_found = m_ip.group(1)
                        break
                if ip_found:
                    subprocess.run([adb_exe, "-s", usb_dev, "tcpip", "5555"], capture_output=True, text=True, timeout=6)
                    time.sleep(2.0)
                    cand_target = ip_found + ":5555"
                    c_out = subprocess.run([adb_exe, "connect", cand_target], capture_output=True, text=True, timeout=6)
                    if "connected" in (c_out.stdout + c_out.stderr).lower():
                        wireless_target = cand_target
                        print("[SUCCESS] Wireless ADB established at " + wireless_target + "! You can unplug USB.")
                    else:
                        print("[INFO] Using stable direct USB ADB connection (" + usb_dev + ").")
                else:
                    print("[INFO] Phone Wi-Fi not on local LAN; using stable direct USB ADB (" + usb_dev + ").")

            active_dev = wireless_target if (wireless_target and wireless_target in devs) else devs[0]
            model, latest_call, wa_list, contacts_cache = collect_telemetry(
                active_dev,
                include_contacts=(not contacts_synced),
                contacts_store=contacts_cache,
            )
            if contacts_cache:
                contacts_synced = True

            hb_payload = {
                "user_id": USER_ID,
                "device_serial": active_dev,
                "wireless_ip": active_dev,
                "phone_model": model,
                "latest_missed_call": latest_call,
                "whatsapp_alerts": wa_list,
                "contacts": contacts_cache if contacts_cache else None,
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
                    execute_remote_action(active_dev, cmd_obj, contacts_cache)

            call_info = (" | Latest Missed Call: " + latest_call["sender"]) if latest_call else ""
            print("[ONLINE & SYNCED] " + active_dev + " (" + model + ") -> Profile '" + USER_ID + "'" + call_info)
    except Exception:
        pass
    time.sleep(3)
"""

# 1. Update backend/main.py with the v3.6 bridge template
main_txt = MAIN_PY.read_text(encoding="utf-8")
old_tpl = re.search(r'bridge_py_template = r""".*?"""', main_txt, flags=re.S)
if old_tpl:
    main_txt = main_txt[:old_tpl.start()] + 'bridge_py_template = r"""' + NEW_BRIDGE_TEMPLATE + '"""' + main_txt[old_tpl.end():]
    ast.parse(main_txt)
    MAIN_PY.write_text(main_txt, encoding="utf-8")
    print("[1/3] Updated /api/v1/bridge/download-kit in backend/main.py with v3.6 Zero-Reset & PIN-Unlock Bridge!")

# 2. Directly update any extracted bridge scripts inside Downloads so Peeyush doesn't even have to re-download
downloads_dir = Path(os.path.expanduser("~")) / "Downloads"
updated_local = 0
if downloads_dir.exists():
    for py_Bridge in downloads_dir.rglob("nemesis_client_bridge.py"):
        try:
            cur_txt = py_Bridge.read_text(encoding="utf-8", errors="ignore")
            m_srv = re.search(r'SERVER_URL\s*=\s*"([^"]+)"', cur_txt)
            m_uid = re.search(r'USER_ID\s*=\s*"([^"]+)"', cur_txt)
            srv_val = m_srv.group(1) if m_srv else "https://nemesis-command-center.onrender.com"
            uid_val = m_uid.group(1) if m_uid else "peeyush_sharma"
            patched = NEW_BRIDGE_TEMPLATE.replace("__SERVER_URL__", srv_val).replace("__USER_ID__", uid_val)
            py_Bridge.write_text(patched, encoding="utf-8")
            updated_local += 1
            print(f"[2/3] Auto-updated extracted bridge script at: {py_Bridge}")
        except Exception:
            pass

if updated_local == 0:
    print("[2/3] No existing nemesis_client_bridge.py found in Downloads (download fresh from the web modal).")

# 3. Push to GitHub / Render
subprocess.run(["git", "add", "-A"], cwd=str(ROOT))
subprocess.run(["git", "commit", "-m", "Fix USB tcpip reset loop, add PIN unlock and contact call resolution"], cwd=str(ROOT))
push_out = subprocess.run(["git", "push", "origin", "main"], cwd=str(ROOT), capture_output=True, text=True)
print("[3/3] Git Push Output:\n" + (push_out.stdout + "\n" + push_out.stderr).strip())
