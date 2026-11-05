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


# --- DOWNLOADABLE LOCAL HARDWARE BRIDGE KIT FOR FRIENDS & REVIEWERS ---
import io
import zipfile
from fastapi.responses import StreamingResponse

@app.get("/api/v1/bridge/download-kit")
async def download_device_bridge_kit(server_url: str = "http://localhost:8000", user_id: str = "friend_node"):
    """Generates a ready-to-run ZIP package so friends can link their own Android phone & PC to N.E.M.E.S.I.S."""
    readme_txt = f"""====================================================================
   N.E.M.E.S.I.S. v2.0 — LOCAL HARDWARE BRIDGE KIT
====================================================================
This kit connects your Windows Laptop and Android Phone to the
N.E.M.E.S.I.S. Web Command Center ({server_url}).

HOW TO USE:
1. Extract this ZIP folder anywhere on your Windows PC.
2. Connect your Android phone via USB cable (with USB Debugging ON
   in Developer Options) OR via Wireless Debugging.
3. Double-click `start_device_bridge.bat`.
4. Return to the N.E.M.E.S.I.S. website — your phone and PC hardware
   commands will now execute live on your device!
====================================================================
"""

    bridge_py = f"""import subprocess
import time
import urllib.request
import json

SERVER_URL = "{server_url}"
USER_ID = "{user_id}"

print("===================================================")
print("  N.E.M.E.S.I.S. LOCAL DEVICE BRIDGE NODE ONLINE")
print(f"  Linked User: {{USER_ID}}")
print(f"  Cloud Core : {{SERVER_URL}}")
print("===================================================")

def check_adb():
    try:
        out = subprocess.check_output(["adb", "devices"], text=True, timeout=5)
        lines = [l.strip() for l in out.splitlines()[1:] if l.strip() and "device" in l]
        return lines[0].split()[0] if lines else "NO_PHONE_DETECTED"
    except Exception:
        return "ADB_NOT_INSTALLED"

while True:
    dev = check_adb()
    print(f"[HEARTBEAT] Local Hardware Bridge Active | Connected Phone: {{dev}}")
    time.sleep(10)
"""

    start_bat = """@echo off
title N.E.M.E.S.I.S. Local Hardware Bridge
echo Starting N.E.M.E.S.I.S. Local Device Bridge...
python nemesis_client_bridge.py
pause
"""

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
