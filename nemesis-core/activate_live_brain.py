import ast
import re
from pathlib import Path

CURRENT = Path(__file__).resolve().parent
BASE_DIR = CURRENT if (CURRENT / "backend").exists() else CURRENT / "nemesis-core"
MAIN_FILE = BASE_DIR / "backend" / "main.py"
BRAIN_FILE = BASE_DIR / "backend" / "commander" / "nemesis_brain.py"
HUD_PATH = BASE_DIR / "frontend_hud" / "index.html"

print("=== N.E.M.E.S.I.S. v3.5 â€” REAL FRIEND TELEMETRY SYNC & 2-WAY REMOTE EXECUTION ENGINE ===")

# ==============================================================================
# 1. UPGRADE backend/main.py: STORE FRIEND'S REAL CALLS, WHATSAPP & CONTACTS + QUEUE COMMANDS
# ==============================================================================
main_code = MAIN_FILE.read_text(encoding="utf-8")

main_code = re.sub(
    r"\n*# --- STRICT HOST ISOLATION, USB-TO-WIRELESS AUTO-BRIDGE & 2-WAY FRIEND RELAY ---.*$",
    "",
    main_code,
    flags=re.S,
)

friend_telemetry_backend = r'''

# --- STRICT HOST ISOLATION, USB-TO-WIRELESS AUTO-BRIDGE & 2-WAY FRIEND RELAY ---
import io
import re
import shutil
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

REMOTE_FRIEND_NODES: Dict[str, Dict[str, Any]] = {}
FRIEND_COMMAND_QUEUE: Dict[str, List[Dict[str, Any]]] = {}


def get_active_friend_node(uid: str) -> Optional[Dict[str, Any]]:
    clean_uid = (uid or "").lower().strip()
    node = REMOTE_FRIEND_NODES.get(clean_uid)
    if node and (time.time() - node.get("ts", 0)) < 35:
        return node
    return None


def queue_friend_command(uid: str, action: str, payload: Dict[str, Any]) -> None:
    clean_uid = (uid or "").lower().strip()
    q = FRIEND_COMMAND_QUEUE.setdefault(clean_uid, [])
    q.append({"action": action, "payload": payload, "ts": time.time()})


def _is_local_host_request(request: Request) -> bool:
    forwarded = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for")
    if forwarded:
        return False
    client_host = (request.client.host if request.client else "") or ""
    return client_host in ("127.0.0.1", "::1", "localhost")


def _get_working_adb_binary() -> str:
    here = Path(__file__).resolve().parent
    for cand in (
        here.parent / "platform-tools" / "adb.exe",
        here.parent.parent / "platform-tools" / "adb.exe",
        here.parent / "platform-tools" / "adb",
    ):
        if cand.exists():
            return str(cand)
    return shutil.which("adb") or "adb"


class RemoteNodeHeartbeat(BaseModel):
    user_id: str
    device_serial: str
    wireless_ip: Optional[str] = ""
    phone_model: Optional[str] = ""
    latest_missed_call: Optional[Dict[str, Any]] = None
    whatsapp_alerts: Optional[List[Dict[str, str]]] = None
    contacts: Optional[Dict[str, str]] = None


@app.get("/api/v1/bridge/adb-status")
async def get_live_adb_status(request: Request, user_id: str = "founder_peeyush"):
    is_host = _is_local_host_request(request)
    clean_uid = (user_id or "").lower().strip()

    # 1. Check if this user has an active Friend Bridge running (works for Anuj & remote friends!)
    node = get_active_friend_node(clean_uid)
    if node:
        dev_label = node.get("wireless_ip") or node.get("serial")
        model_lbl = f" ({node['phone_model']})" if node.get("phone_model") else ""
        return JSONResponse({
            "connected": True,
            "is_host_machine": False,
            "device_count": 1,
            "primary_device": f"{dev_label}{model_lbl}",
            "mode": "FRIEND_WIRELESS_BRIDGE",
        })

    # 2. If on Peeyush's localhost, check Peeyush's local ADB
    if is_host and clean_uid in ("founder_peeyush", "peeyush_sharma", "peeyush", "commander"):
        try:
            adb_bin = _get_working_adb_binary()
            proc = subprocess.run([adb_bin, "devices"], capture_output=True, text=True, timeout=5)
            lines = [
                l.strip()
                for l in proc.stdout.splitlines()[1:]
                if l.strip() and "\tdevice" in l
            ]
            if lines:
                wireless_dev = next((l.split()[0] for l in lines if ":" in l.split()[0]), lines[0].split()[0])
                return JSONResponse({
                    "connected": True,
                    "is_host_machine": True,
                    "device_count": len(lines),
                    "primary_device": wireless_dev,
                    "mode": "WIRELESS_ADB" if ":" in wireless_dev else "USB_ADB",
                })
        except Exception as exc:
            return JSONResponse({"connected": False, "is_host_machine": True, "error": str(exc)})
        return JSONResponse({"connected": False, "is_host_machine": True, "primary_device": None})

    return JSONResponse({
        "connected": False,
        "is_host_machine": False,
        "device_count": 0,
        "primary_device": None,
        "mode": "CLOUD_SIMULATION",
    })


@app.post("/api/v1/bridge/usb-to-wireless")
async def auto_link_usb_to_wireless(request: Request, user_id: str = "founder_peeyush"):
    clean_uid = (user_id or "").lower().strip()
    # If the remote friend already has their Bridge Kit running, confirm it's LIVE!
    friend_node = get_active_friend_node(clean_uid)
    if friend_node:
        dev_ip = friend_node.get("wireless_ip") or friend_node.get("serial")
        return JSONResponse({
            "connected": True,
            "target": dev_ip,
            "detail": f"âœ… Your Personal Phone Bridge ({dev_ip}) is LIVE and syncing your real calls, contacts, and WhatsApp with N.E.M.E.S.I.S.!",
        })

    if not _is_local_host_request(request):
        return JSONResponse({
            "connected": False,
            "detail": f"To link your phone from a remote laptop (User ID: '{clean_uid}'), click the red 'DOWNLOAD 1-CLICK LOCAL ADB BRIDGE KIT (.ZIP)' button below, extract it, and run start_device_bridge.bat!",
        })

    try:
        adb_bin = _get_working_adb_binary()
        subprocess.run([adb_bin, "start-server"], capture_output=True, text=True, timeout=6)
        dev_proc = subprocess.run([adb_bin, "devices"], capture_output=True, text=True, timeout=5)
        all_lines = [l.strip() for l in dev_proc.stdout.splitlines()[1:] if l.strip()]

        if not all_lines:
            return JSONResponse({
                "connected": False,
                "detail": "No phone detected yet. Plug your Android phone into your laptop with a USB cable and ensure 'USB Debugging' is ON in Developer Options.",
            })

        if any("unauthorized" in l.lower() for l in all_lines):
            return JSONResponse({
                "connected": False,
                "detail": "Phone detected on USB! Unlock your phone screen right now, check 'Always allow from this computer', and tap 'Allow'.",
            })

        online_serials = [l.split()[0] for l in all_lines if "\tdevice" in l]
        if not online_serials:
            return JSONResponse({"connected": False, "detail": "Phone is offline. Reconnect the USB cable and try again."})

        usb_serial = next((s for s in online_serials if ":" not in s), online_serials[0])
        if ":" in usb_serial:
            return JSONResponse({
                "connected": True,
                "target": usb_serial,
                "detail": f"âœ… Wireless ADB is already active at {usb_serial}! You can keep your USB cable unplugged.",
            })

        subprocess.run([adb_bin, "-s", usb_serial, "tcpip", "5555"], capture_output=True, text=True, timeout=7)
        time.sleep(1.8)

        phone_ip = ""
        for cmd in (["shell", "ip -f inet addr show wlan0"], ["shell", "ip route"]):
            ip_proc = subprocess.run([adb_bin, "-s", usb_serial] + cmd, capture_output=True, text=True, timeout=5)
            m_ip = re.search(r"(?:inet|src)\s+(\d+\.\d+\.\d+\.\d+)", ip_proc.stdout)
            if m_ip:
                phone_ip = m_ip.group(1)
                break

        if phone_ip:
            wireless_target = f"{phone_ip}:5555"
            c_proc = subprocess.run([adb_bin, "connect", wireless_target], capture_output=True, text=True, timeout=8)
            c_out = (c_proc.stdout + " " + c_proc.stderr).strip()
            if "connected" in c_out.lower():
                return JSONResponse({
                    "connected": True,
                    "target": wireless_target,
                    "detail": f"âœ… USB-to-Wireless Bridge established at {wireless_target}! You can now UNPLUG your USB cable.",
                })

        return JSONResponse({
            "connected": True,
            "target": usb_serial,
            "detail": f"âœ… Phone linked via USB ({usb_serial})!",
        })
    except Exception as exc:
        return JSONResponse({"connected": False, "detail": f"USB Bridge Error: {exc}"})


@app.post("/api/v1/bridge/remote-heartbeat")
async def register_remote_friend_node(hb: RemoteNodeHeartbeat):
    clean_uid = (hb.user_id or "friend").lower().strip()
    existing = REMOTE_FRIEND_NODES.get(clean_uid, {})
    merged_contacts = existing.get("contacts", {})
    if hb.contacts:
        merged_contacts.update(hb.contacts)

    REMOTE_FRIEND_NODES[clean_uid] = {
        "serial": hb.device_serial,
        "wireless_ip": hb.wireless_ip or hb.device_serial,
        "phone_model": hb.phone_model or existing.get("phone_model", ""),
        "latest_missed_call": hb.latest_missed_call if hb.latest_missed_call is not None else existing.get("latest_missed_call"),
        "whatsapp_alerts": hb.whatsapp_alerts if hb.whatsapp_alerts is not None else existing.get("whatsapp_alerts", []),
        "contacts": merged_contacts,
        "ts": time.time(),
    }
    pending = FRIEND_COMMAND_QUEUE.pop(clean_uid, [])
    return JSONResponse({"status": "OK", "commands": pending})


@app.get("/api/v1/bridge/download-kit")
async def download_device_bridge_kit(server_url: str = "http://localhost:8000", user_id: str = "friend_node"):
    readme_txt = f"""====================================================================
   N.E.M.E.S.I.S. v3.5 â€” 2-WAY TELEMETRY & HARDWARE BRIDGE KIT
====================================================================
Personal User ID    : {user_id}
Connected Cloud Core: {server_url}

WHAT THIS v3.5 BRIDGE DOES:
1. Automatically bridges your USB phone to Wireless ADB (Port 5555).
2. Syncs your real Missed Calls, Contacts & WhatsApp notifications
   exclusively to your personal profile ({user_id}).
3. Executes N.E.M.E.S.I.S. phone calls, WhatsApp replies, screen unlock,
   and music commands directly on YOUR phone!
====================================================================
"""
    bridge_py = f"""import json
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

SERVER_URL = "{server_url}".rstrip("/")
USER_ID = "{user_id}".lower().strip()
HERE = Path(__file__).resolve().parent
LOCAL_ADB = HERE / "platform-tools" / "adb.exe"

print("=================================================================")
print("  N.E.M.E.S.I.S. v3.5 â€” REAL-TIME TELEMETRY & HARDWARE BRIDGE")
print(f"  Personal Profile ID : {{USER_ID}}")
print(f"  Connected Web Core  : {{SERVER_URL}}")
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
    # 1. Latest Missed Call (sorted newest first)
    call_out = run_adb(dev, ["shell", 'content query --uri content://call_log/calls --projection number:name:type:date --sort "date DESC"'], timeout=6)
    missed = []
    for line in call_out.splitlines():
        m_t = re.search(r"\\btype=(\\d+)", line)
        if not m_t or m_t.group(1) not in ("3", "5"):
            continue
        m_d = re.search(r"\\bdate=(\\d+)", line)
        ts = int(m_d.group(1)) if m_d else 0
        m_num = re.search(r"\\bnumber=([^,\\s]+)", line)
        num = m_num.group(1).strip() if m_num else ""
        if not num or num.upper() == "NULL":
            continue
        m_name = re.search(r"\\bname=([^,]+)", line)
        name = m_name.group(1).strip() if m_name else ""
        if name.upper() == "NULL":
            name = ""
        missed.append({{"ts": ts, "number": num, "name": name}})
    missed.sort(key=lambda x: x["ts"], reverse=True)
    latest_call = None
    if missed:
        c = missed[0]
        t_str = time.strftime("%I:%M %p", time.localtime(c["ts"] / 1000.0)) if c["ts"] else "Recent"
        latest_call = {{
            "type": "missed_call",
            "sender": c["name"] or c["number"],
            "number": c["number"],
            "ts": c["ts"],
            "content": f"Latest Missed Call at {{t_str}} ({{c['number']}})",
        }}

    # 2. Unread WhatsApp Notifications
    wa_list = []
    notif_out = run_adb(dev, ["shell", "dumpsys notification --noredact"], timeout=6)
    if notif_out and "com.whatsapp" in notif_out:
        for blk in notif_out.split("NotificationRecord(")[1:]:
            if "com.whatsapp" not in blk:
                continue
            mt = re.search(r"android\\.title=(?:String\\s*\\()?([^\\n\\r\\)]+)", blk)
            mx = re.search(r"android\\.text=(?:String\\s*\\()?([^\\n\\r\\)]+)", blk)
            if mt and mx:
                sv, bv = mt.group(1).strip(), mx.group(1).strip()
                if sv.lower() not in ("whatsapp", "you", "backup in progress") and "new messages" not in bv.lower():
                    wa_list.append({{"sender": sv, "content": bv}})

    # 3. Contacts (synced once on startup)
    contacts_map = {{}}
    if include_contacts:
        c_out = run_adb(dev, ["shell", "content query --uri content://com.android.contacts/data/phones --projection display_name:data1"], timeout=8)
        for line in c_out.splitlines():
            mn = re.search(r"display_name=([^,]+)", line)
            mp = re.search(r"data1=([^\\s,]+)", line)
            if mn and mp:
                dn = mn.group(1).strip().lower()
                dg = re.sub(r"\\D", "", mp.group(1))
                if len(dg) >= 10:
                    contacts_map[dn] = f"91{{dg[-10:]}}"

    return model, latest_call, wa_list[-5:], contacts_map

def execute_remote_action(dev, cmd_obj, contacts_cache):
    act = cmd_obj.get("action")
    pay = cmd_obj.get("payload", {{}})
    print(f"\\n[âš¡ EXECUTING N.E.M.E.S.I.S. COMMAND ON YOUR PHONE]: {{act}} -> {{pay}}")

    if act == "unlock":
        run_adb(dev, ["shell", "input", "keyevent", "224"])
        run_adb(dev, ["shell", "input", "swipe", "500", "1600", "500", "400", "300"])
    elif act == "hangup":
        run_adb(dev, ["shell", "input", "keyevent", "KEYCODE_ENDCALL"])
    elif act == "play_song":
        q = urllib.parse.quote(pay.get("query", "Cyberpunk Synthwave"))
        run_adb(dev, ["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", f"https://www.youtube.com/results?search_query={{q}}"])
    elif act == "phone_call":
        target = pay.get("number") or ""
        msg = pay.get("message") or ""
        run_adb(dev, ["shell", "am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:+{{target}}"])
        time.sleep(2.5)
        run_adb(dev, ["shell", "cmd", "audio", "set-communication-device", "2"])
        if msg:
            time.sleep(6.5)
            clean_m = re.sub(r"[^a-zA-Z0-9,.?!\\s]", " ", msg.replace("'", "")).strip()
            ps_tts = f"Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Rate = 0; $s.Speak('Hello, I am Nemesis. {{clean_m}}')"
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_tts], timeout=20)
    elif act == "whatsapp_send":
        target = pay.get("number") or ""
        msg = pay.get("message") or ""
        enc = urllib.parse.quote(msg)
        run_adb(dev, ["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", f"https://api.whatsapp.com/send?phone={{target}}&text={{enc}}"])
        time.sleep(3.5)
        run_adb(dev, ["shell", "input", "keyevent", "22"])
        run_adb(dev, ["shell", "input", "keyevent", "66"])
        run_adb(dev, ["shell", "input", "tap", "995", "2165"])

wireless_target = ""
contacts_synced = False
local_contacts = {{}}

while True:
    try:
        out = subprocess.check_output([adb_exe, "devices"], text=True, timeout=5)
        if "unauthorized" in out.lower():
            print("[ACTION NEEDED] Unlock your phone screen and tap 'Allow USB Debugging'!")
        devs = [l.split()[0] for l in out.splitlines()[1:] if l.strip() and "\\tdevice" in l]
        if devs:
            usb_dev = next((d for d in devs if ":" not in d), None)
            if usb_dev and not wireless_target:
                print(f"[*] USB Phone detected ({{usb_dev}})! Bridging to Wireless ADB (Port 5555)...")
                subprocess.run([adb_exe, "-s", usb_dev, "tcpip", "5555"], capture_output=True, text=True, timeout=6)
                time.sleep(1.8)
                ip_out = run_adb(usb_dev, ["shell", "ip -f inet addr show wlan0"])
                m_ip = re.search(r"inet\\s+(\\d+\\.\\d+\\.\\d+\\.\\d+)", ip_out)
                if m_ip:
                    wireless_target = f"{{m_ip.group(1)}}:5555"
                    subprocess.run([adb_exe, "connect", wireless_target], capture_output=True, text=True, timeout=6)
                    print(f"[SUCCESS] Wireless ADB established at {{wireless_target}}! You can now unplug your USB cable.")

            active_dev = wireless_target if (wireless_target and wireless_target in devs) else devs[0]
            model, latest_call, wa_list, c_map = collect_telemetry(active_dev, include_contacts=(not contacts_synced))
            if c_map:
                local_contacts.update(c_map)
                contacts_synced = True

            hb_payload = {{
                "user_id": USER_ID,
                "device_serial": active_dev,
                "wireless_ip": active_dev,
                "phone_model": model,
                "latest_missed_call": latest_call,
                "whatsapp_alerts": wa_list,
                "contacts": c_map if c_map else None,
            }}
            req = urllib.request.Request(
                f"{{SERVER_URL}}/api/v1/bridge/remote-heartbeat",
                data=json.dumps(hb_payload).encode("utf-8"),
                headers={{"Content-Type": "application/json"}},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for cmd_obj in data.get("commands", []):
                    execute_remote_action(active_dev, cmd_obj, local_contacts)

            call_info = f" | Latest Missed Call: {{latest_call['sender']}}" if latest_call else ""
            print(f"[ONLINE & SYNCED] {{active_dev}} ({{model}}) -> Profile '{{USER_ID}}'{{call_info}}")
    except Exception as e:
        pass
    time.sleep(3)
"""
    start_bat = "@echo off\ntitle N.E.M.E.S.I.S. v3.5 Hardware Bridge\ncd /d \"%~dp0\"\npython nemesis_client_bridge.py\npause\n"
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("NEMESIS_Device_Bridge/README_FIRST.txt", readme_txt)
        zf.writestr("NEMESIS_Device_Bridge/nemesis_client_bridge.py", bridge_py)
        zf.writestr("NEMESIS_Device_Bridge/start_device_bridge.bat", start_bat)
    mem_zip.seek(0)
    return StreamingResponse(
        mem_zip,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="NEMESIS_Device_Bridge_Kit.zip"'},
    )
'''

main_code = main_code.rstrip() + "\n" + friend_telemetry_backend
ast.parse(main_code)
MAIN_FILE.write_text(main_code, encoding="utf-8")
print("[1/3] Upgraded backend/main.py with Real Friend Telemetry Sync & 2-Way Command Queue!")

# ==============================================================================
# 2. UPGRADE nemesis_brain.py: ROUTE CONNECTED FRIENDS TO THEIR OWN SYNCED PHONE!
# ==============================================================================
brain_code = BRAIN_FILE.read_text(encoding="utf-8")

# Add helper methods on NemesisSupremeCommander to access the friend's live telemetry & command queue
friend_brain_helpers = r'''    @staticmethod
    def _get_friend_node(uid: str) -> Optional[Dict[str, Any]]:
        try:
            from backend.main import get_active_friend_node
            return get_active_friend_node(uid)
        except Exception:
            return None

    @staticmethod
    def _queue_friend_cmd(uid: str, action: str, payload: Dict[str, Any]) -> None:
        try:
            from backend.main import queue_friend_command
            queue_friend_command(uid, action, payload)
        except Exception:
            pass

    @classmethod
    def _resolve_friend_number(cls, uid: str, name_or_num: str, friend_node: Dict[str, Any]) -> str:
        raw = (name_or_num or "").strip()
        digits = re.sub(r"\D", "", raw)
        if len(digits) >= 10:
            return f"91{digits[-10:]}"
        contacts = friend_node.get("contacts") or {}
        key = raw.lower()
        if key in contacts:
            return contacts[key]
        for k, v in contacts.items():
            if key in k or k in key:
                return v
        return digits or raw
'''

if "def _get_friend_node" not in brain_code:
    brain_code = brain_code.replace(
        "    @staticmethod\n    def _clean_spoken_text",
        friend_brain_helpers + "\n    @staticmethod\n    def _clean_spoken_text",
    )

# Replace the Sentinel Scan block so connected friends get THEIR OWN real latest missed call & WhatsApp alerts!
old_sentinel_route = re.search(
    r"        # --- SENTINEL POLLING ROUTE.*?return \{\"commander\": \"N\.E\.M\.E\.S\.I\.S\.\", \"status\": \"NO_ALERT\", \"has_alert\": False\}",
    brain_code,
    flags=re.S,
)

new_sentinel_route = '''        # --- SENTINEL POLLING ROUTE (LOCAL HOST, LIVE FRIEND BRIDGE, OR DEMO FALLBACK) ---
        friend_node = self._get_friend_node(uid)
        if raw_prompt == "__SENTINEL_SCAN__":
            # CASE A: Remote Friend has their Personal Bridge Kit running -> use THEIR real phone's latest missed call!
            if friend_node:
                f_call = friend_node.get("latest_missed_call")
                f_wa = friend_node.get("whatsapp_alerts") or []
                if f_call and (force_scan or f_call.get("ts", 0) > int((time.time() - 90) * 1000)):
                    sender = f_call.get("sender", "Unknown Caller")
                    spoken_briefing = f"{active_user_name}, you have a missed call on your linked phone from {sender}. What should I tell them?"
                    return {
                        "commander": "N.E.M.E.S.I.S.",
                        "status": "ALERT_TRIGGERED",
                        "has_alert": True,
                        "alert": f_call,
                        "remote_called": False,
                        "nemesis_response": spoken_briefing,
                    }
                if f_wa and force_scan:
                    last_w = f_wa[-1]
                    spoken_briefing = f"{active_user_name}, unread WhatsApp on your phone from {last_w['sender']} saying {last_w['content']}. How should I reply?"
                    return {
                        "commander": "N.E.M.E.S.I.S.",
                        "status": "ALERT_TRIGGERED",
                        "has_alert": True,
                        "alert": {"type": "whatsapp", "sender": last_w["sender"], "content": last_w["content"]},
                        "remote_called": False,
                        "nemesis_response": spoken_briefing,
                    }
                return {"commander": "N.E.M.E.S.I.S.", "status": "NO_ALERT", "has_alert": False}

            # CASE B: Peeyush on Localhost -> scan Peeyush's local ADB phone
            if not is_remote_visitor:
                scan_res = await AndroidSwarmBridge.scan_priority_alerts(force_latest=force_scan)
                if scan_res.get("has_alert"):
                    alert = scan_res["alert"]
                    sender = re.sub(r"\\s*\\(\\d+\\s*messages?\\)", "", alert["sender"]).strip()
                    alert["sender"] = sender
                    if alert["type"] == "missed_call":
                        spoken_briefing = f"{active_user_name}, you have a missed call from {sender}. What should I tell them?"
                    else:
                        spoken_briefing = f"{active_user_name}, WhatsApp message from {sender} saying {alert['content']}. How should I reply?"
                    return {
                        "commander": "N.E.M.E.S.I.S.",
                        "status": "ALERT_TRIGGERED",
                        "has_alert": True,
                        "alert": alert,
                        "remote_called": bool(scan_res.get("remote_called", False)),
                        "second_phone": scan_res.get("second_phone", ""),
                        "nemesis_response": spoken_briefing,
                    }
                return {"commander": "N.E.M.E.S.I.S.", "status": "NO_ALERT", "has_alert": False}

            # CASE C: Unlinked PayPal Reviewer (No Bridge Running) -> Demo Simulation
            if force_scan:
                demo_alert = {
                    "type": "missed_call",
                    "sender": "VIP Hackathon Coordinator",
                    "content": "Simulated Demo Alert (Run the Local Bridge Kit to scan your real phone's call log!)",
                }
                spoken_briefing = (
                    f"{active_user_name}, simulation alert! You have a missed call from VIP Hackathon Coordinator. "
                    "What message should I deliver?"
                )
                return {
                    "commander": "N.E.M.E.S.I.S.",
                    "status": "ALERT_TRIGGERED",
                    "has_alert": True,
                    "alert": demo_alert,
                    "remote_called": False,
                    "nemesis_response": spoken_briefing,
                }
            return {"commander": "N.E.M.E.S.I.S.", "status": "NO_ALERT", "has_alert": False}'''

if old_sentinel_route:
    brain_code = brain_code[:old_sentinel_route.start()] + new_sentinel_route + brain_code[old_sentinel_route.end():]

# Upgrade remote visitor hardware actions so if `friend_node` is active, it queues real commands to their laptop bridge!
brain_code = brain_code.replace(
    'if is_remote_visitor:\n                sim_txt = f"Called {target_sender} on speakerphone and delivered {active_user_name}\'s message: \'{reply_body}\'."',
    '''if is_remote_visitor:
                if friend_node:
                    num = self._resolve_friend_number(uid, active_alert.get("number") or target_sender, friend_node)
                    act_type = "phone_call" if ("call" in lower or active_alert.get("type") == "missed_call") else "whatsapp_send"
                    self._queue_friend_cmd(uid, act_type, {"number": num, "message": reply_body})
                    sim_txt = f"Dispatched live {act_type} to {target_sender} ({num}) on {active_user_name}'s linked phone ({friend_node.get('wireless_ip')}): '{reply_body}'."
                else:
                    sim_txt = f"[Cloud Simulation]: Called {target_sender} and delivered {active_user_name}'s message: '{reply_body}'."''',
)

brain_code = brain_code.replace(
    '''                if is_remote_visitor:
                    sim_msg = (
                        f"Dialing {target_contact} (+91) on speakerphone for {active_user_name}"
                        + (f" and speaking after 9s: 'Hello, I am Nemesis, {active_user_name}'s assistant. {spoken_msg}'" if spoken_msg else ".")
                    )''',
    '''                if is_remote_visitor:
                    if friend_node:
                        num = self._resolve_friend_number(uid, target_contact, friend_node)
                        self._queue_friend_cmd(uid, "phone_call", {"number": num, "message": spoken_msg or ""})
                        sim_msg = f"ðŸ“² Dialing {target_contact} (+{num}) directly on {active_user_name}'s linked phone ({friend_node.get('wireless_ip')})" + (f" and speaking: '{spoken_msg}'" if spoken_msg else "!")
                    else:
                        sim_msg = f"[Cloud Simulation]: Dialing {target_contact} on speakerphone for {active_user_name}."''',
)

brain_code = brain_code.replace(
    '''            if is_remote_visitor:
                sim_wa = f"WhatsApp message dispatched to {recipient} on behalf of {active_user_name}: '{msg_body}'."''',
    '''            if is_remote_visitor:
                if friend_node:
                    num = self._resolve_friend_number(uid, recipient or "", friend_node)
                    self._queue_friend_cmd(uid, "whatsapp_send", {"number": num, "message": msg_body})
                    sim_wa = f"ðŸ“² Dispatched live WhatsApp message to {recipient} (+{num}) on {active_user_name}'s linked phone ({friend_node.get('wireless_ip')}): '{msg_body}'."
                else:
                    sim_wa = f"[Cloud Simulation]: WhatsApp message dispatched to {recipient} for {active_user_name}: '{msg_body}'."''',
)

brain_code = brain_code.replace(
    '''        if ("read" in lower or "check" in lower or "open" in lower) and ("whatsapp" in lower or "messages" in lower):
            if is_remote_visitor:
                reply_text = (
                    f"{active_user_name}, I scanned your synced WhatsApp feed: 1) Hackathon Team: 'Deployment link is live and tested!' "
                    "2) Mom: 'Let me know when you finish your project review.' Say 'Send a WhatsApp message to Mom saying...' to reply."
                )''',
    '''        if ("read" in lower or "check" in lower or "open" in lower) and ("whatsapp" in lower or "messages" in lower):
            if is_remote_visitor:
                if friend_node:
                    f_wa = friend_node.get("whatsapp_alerts") or []
                    if f_wa:
                        items = "; ".join([f"{w['sender']}: '{w['content']}'" for w in f_wa[-4:]])
                        reply_text = f"{active_user_name}, here are the live unread WhatsApp messages from your linked phone ({friend_node.get('wireless_ip')}): {items}"
                    else:
                        reply_text = f"{active_user_name}, your linked phone ({friend_node.get('wireless_ip')}) currently has zero unread WhatsApp notifications."
                else:
                    reply_text = (
                        f"{active_user_name}, [Simulation Mode]: 1) Hackathon Team: 'Deployment link is live!' "
                        "(Run your downloaded Bridge Kit to read real WhatsApp messages from your phone)."
                    )''',
)

brain_code = brain_code.replace(
    '''            else:
                out_txt = f"Swarm Bridge authenticated for {active_user_name}. All 3 nodes unlocked and synchronized."''',
    '''            else:
                if friend_node:
                    self._queue_friend_cmd(uid, "unlock", {})
                    out_txt = f"ðŸ”“ Physically unlocked {active_user_name}'s linked Android phone ({friend_node.get('wireless_ip')}) via Wireless ADB Bridge!"
                else:
                    out_txt = f"Swarm Bridge authenticated for {active_user_name}. All 3 virtual nodes unlocked."''',
)

brain_code = brain_code.replace(
    '''            else:
                out_txt = f"Streaming {active_user_name}'s track ('{chosen_song}') across all 3 Swarm Nodes."''',
    '''            else:
                if friend_node:
                    self._queue_friend_cmd(uid, "play_song", {"query": chosen_song})
                    out_txt = f"ðŸŽµ Launching '{chosen_song}' directly on {active_user_name}'s linked phone ({friend_node.get('wireless_ip')}) & browser!"
                else:
                    out_txt = f"Streaming {active_user_name}'s track ('{chosen_song}') across Swarm Nodes."''',
)

ast.parse(brain_code)
BRAIN_FILE.write_text(brain_code, encoding="utf-8")
print("[2/3] Upgraded nemesis_brain.py: Connected friends now use their REAL phone data & execute live commands!")

# ==============================================================================
# 3. FIX frontend_hud/index.html: PASS user_id TO USB-TO-WIRELESS BUTTON
# ==============================================================================
html = HUD_PATH.read_text(encoding="utf-8")

html = html.replace(
    "const res = await fetch('/api/v1/bridge/usb-to-wireless', { method: 'POST' });",
    "const uid = (window.nemesisUserProfile && window.nemesisUserProfile.name || 'founder_peeyush').toLowerCase().replace(/[^a-z0-9]/g, '_');\n          const res = await fetch(`/api/v1/bridge/usb-to-wireless?user_id=${encodeURIComponent(uid)}`, { method: 'POST' });",
)

HUD_PATH.write_text(html, encoding="utf-8")
print("[3/3] Updated frontend_hud/index.html so the green Step 2 button verifies a friend's live bridge!")

