import webbrowser
from typing import Any, Dict


class PSwarmDaemon:
    """Controls the primary workstation HUD lock state and local media playback."""

    _screen_locked: bool = True

    @classmethod
    def set_hud_lock_state(cls, locked: bool) -> Dict[str, Any]:
        cls._screen_locked = locked
        return {
            "pc_hud_state": "SYSTEM_LOCKED_BLUE" if locked else "SYSTEM_UNLOCKED_ORANGE",
            "core_color": "#00d4ff" if locked else "#ff6a00",
            "unlocked": not locked,
        }

    @classmethod
    def launch_local_media(cls, url: str, open_browser: bool = False) -> Dict[str, Any]:
        if open_browser:
            webbrowser.open(url)
        return {"pc_media_launched": url, "browser_triggered": open_browser}
