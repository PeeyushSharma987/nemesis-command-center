import os, sys, re
from pathlib import Path
_CORE_ROOT = str(Path(__file__).resolve().parent.parent)
if _CORE_ROOT not in sys.path:
    sys.path.insert(0, _CORE_ROOT)
os.environ.setdefault("FOUNDER_GOD_KEY", "NEMESIS-GOD-KEY-987")
os.environ.setdefault("X_FOUNDER_GOD_KEY", "NEMESIS-GOD-KEY-987")
os.environ.setdefault("NEMESIS_JWT_SECRET", "nemesis-supreme-jwt-secret-2026")

import re
import os
from pathlib import Path
from typing import Any, Dict

from fastapi import Depends, FastAPI, Request, Response, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from backend.auth.security_vault import SafeCommandInput, SecurityVault
from backend.commander.live_eye_stream import LiveCameraEyeController
from backend.commander.nemesis_brain import CommanderCommand, NemesisSupremeCommander
from backend.memory.digital_twin_and_ledger import MistakeEntry
from backend.paypal_engine.paypal_mcp_agent import PayPalAgentActionRequest, PayPalAutonomousAgent
from backend.paypal_engine.saas_billing_webhook import CreateSubscriptionRequest, PayPalSaaSEngine
from backend.self_mutate.ast_indexer import ASTCodebaseIndexer
from backend.self_mutate.ouroboros_engine import OuroborosSelfMutator, SelfMutateRequest
from device_bridge.android_swarm_adb import AndroidSwarmBridge
from device_bridge.pc_daemon import PSwarmDaemon
from ring0_kernel.founder_guard import verify_founder_god_key
from ring0_kernel.security_auditor_19pt import NineteenPointAuditor

IS_DEBUG = os.getenv("DEBUG", "False").lower() == "true"
BACKEND_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_ROOT.parent
HUD_HTML_PATH = PROJECT_ROOT / "frontend_hud" / "index.html"

app = FastAPI(
    title="N.E.M.E.S.I.S. Supreme Commander Core",
    version="2.0.0",
    debug=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Founder-God-Key", "PAYPAL-TRANSMISSION-SIG"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


app.add_middleware(SecurityHeadersMiddleware)

nemesis_commander = NemesisSupremeCommander()
live_eye_controller = LiveCameraEyeController()
paypal_saas = PayPalSaaSEngine()
paypal_agent = PayPalAutonomousAgent()
ouroboros_mutator = OuroborosSelfMutator(BACKEND_ROOT)


class SwarmActionRequest(BaseModel):
    action: str  # "unlock_screen" | "unlock_all_phones" | "play_favorite_song"
    youtube_url: str = "https://youtu.be/MJyKN-8UncM?si=EpXJxKEED99A7ftR"


@app.get("/", response_class=HTMLResponse)
async def serve_3d_hud() -> HTMLResponse:
    return HTMLResponse(content=HUD_HTML_PATH.read_text(encoding="utf-8"))


@app.get("/health")
async def health_check() -> Dict[str, object]:
    audit = NineteenPointAuditor.audit_directory(BACKEND_ROOT)
    return {
        "commander": "N.E.M.E.S.I.S.",
        "status": "ONLINE",
        "zero_php_verified": True,
        "debug_mode": IS_DEBUG,
        "security_audit": audit,
    }


@app.post("/api/v1/swarm/execute")
async def execute_hardware_swarm(req: SwarmActionRequest) -> Dict[str, Any]:
    if req.action == "unlock_screen":
        pc_state = PSwarmDaemon.set_hud_lock_state(locked=False)
        return {
            "status": "SUCCESS",
            "pc_state": pc_state,
            "nemesis_speech": "Screen unlocked. Try not to stare at the orange core like an amateur.",
        }
    if req.action == "unlock_all_phones":
        pc_state = PSwarmDaemon.set_hud_lock_state(locked=False)
        swarm_res = await AndroidSwarmBridge.unlock_all_devices()
        return {
            "status": "SUCCESS",
            "pc_state": pc_state,
            "swarm": swarm_res,
            "nemesis_speech": f"Checking... One, two, three. All {swarm_res['count']} mobile devices unlocked.",
        }
    if req.action == "play_favorite_song":
        swarm_res = await AndroidSwarmBridge.play_song_across_swarm(req.youtube_url)
        return {
            "status": "SUCCESS",
            "swarm": swarm_res,
            "nemesis_speech": "Playing your track across all three mobile devices in sync.",
        }
    return {"status": "UNKNOWN_ACTION", "nemesis_speech": "Invalid hardware swarm directive."}


@app.post("/api/v1/commander/execute")
async def execute_nemesis_command(cmd: CommanderCommand) -> Dict[str, Any]:
    return await nemesis_commander.execute_command(cmd)


@app.post("/api/v1/commander/record-mistake")
async def log_mistake_rule(entry: MistakeEntry) -> Dict[str, Any]:
    return nemesis_commander.memory.record_mistake(entry)


@app.websocket("/ws/live-eye/{session_id}")
async def live_camera_websocket(websocket: WebSocket, session_id: str) -> None:
    await live_eye_controller.handle_live_session(websocket, session_id)


@app.post("/api/v1/paypal/create-subscription")
async def create_paypal_subscription(req: CreateSubscriptionRequest) -> Dict[str, Any]:
    return await paypal_saas.create_subscription_checkout(req)


@app.post("/webhooks/paypal")
async def paypal_webhook_listener(request: Request) -> Dict[str, Any]:
    return await paypal_saas.handle_verified_webhook(request)


@app.post("/api/v1/paypal/agent-action")
async def execute_paypal_agent_tool(req: PayPalAgentActionRequest) -> Dict[str, Any]:
    return await paypal_agent.execute_financial_action(req)


@app.get("/api/v1/admin/codebase-map", dependencies=[Depends(verify_founder_god_key)])
async def get_self_indexed_codebase() -> Dict[str, Any]:
    return ASTCodebaseIndexer.index_ring1_codebase(BACKEND_ROOT)


@app.post("/api/v1/admin/self-mutate", dependencies=[Depends(verify_founder_god_key)])
async def trigger_self_mutation(req: SelfMutateRequest) -> Dict[str, Any]:
    return await ouroboros_mutator.mutate_codebase(req)


@app.post("/api/v1/verify-idor-command")
async def verify_protected_command(
    payload: SafeCommandInput,
    current_user: Dict[str, str] = Depends(SecurityVault.get_current_user),
) -> Dict[str, str]:
    SecurityVault.enforce_anti_idor(current_user["user_id"], payload.resource_owner_id)
    return {"status": "authorized", "user_id": current_user["user_id"], "clean_prompt": payload.prompt}


@app.post("/api/v1/admin/ring0-status", dependencies=[Depends(verify_founder_god_key)])
async def founder_only_route() -> Dict[str, str]:
    return {"status": "Founder God-Mode Verified. Ring-0 Kernel Intact."}


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

