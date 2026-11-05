from typing import Optional
from device_bridge.android_swarm_adb import AndroidSwarmBridge


async def execute_learned_skill(prompt: str, lower: str) -> Optional[str]:
    """Dynamically self-mutated skills written by the Ouroboros Engine."""
    devices = await AndroidSwarmBridge.list_connected_phones()
    dev = devices[0]

    if "battery status" in lower or "phone health" in lower:
        out = AndroidSwarmBridge._run_adb_sync(dev, ['shell', 'dumpsys battery'])
        if not out:
            return "Failed to retrieve battery status via ADB."
        
        level = "Unknown"
        temp = "Unknown"
        status = "Unknown"
        charging = "Unknown"
        
        for line in out.splitlines():
            line_str = line.strip()
            if line_str.startswith("level:"):
                level = line_str.split(":", 1)[1].strip()
            elif line_str.startswith("temperature:"):
                raw_temp = line_str.split(":", 1)[1].strip()
                try:
                    temp_c = float(raw_temp) / 10.0
                    temp = f"{temp_c}°C"
                except ValueError:
                    temp = raw_temp
            elif line_str.startswith("status:"):
                status_code = line_str.split(":", 1)[1].strip()
                status_map = {
                    "1": "Unknown",
                    "2": "Charging",
                    "3": "Discharging",
                    "4": "Not charging",
                    "5": "Full"
                }
                status = status_map.get(status_code, f"Code {status_code}")
            elif line_str.startswith("ac powered:") or line_str.startswith("usb powered:") or line_str.startswith("wireless powered:"):
                if "true" in line_str.lower():
                    charging = line_str.split(":", 1)[0].replace("powered", "").strip().upper()

        return f"Battery Diagnostic Summary:\n- Level: {level}%\n- Temperature: {temp}\n- Status: {status}\n- Power Source: {charging}"

    # --- OUROBOROS_INJECTION_MARKER ---
    return None