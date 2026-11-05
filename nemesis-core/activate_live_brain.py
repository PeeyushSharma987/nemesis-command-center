from pathlib import Path

CURRENT = Path(__file__).resolve().parent
BASE_DIR = CURRENT if (CURRENT / "backend").exists() else CURRENT / "nemesis-core"
HUD_PATH = BASE_DIR / "frontend_hud" / "index.html"

print("=== N.E.M.E.S.I.S. COMMAND BAR BUTTON FIT & EXECUTE VISIBILITY FIX ===")

html = HUD_PATH.read_text(encoding="utf-8")

old_cmd_css = """    .command-bar {
      display: flex;
      gap: 8px;
      align-items: center;
      background: rgba(10, 14, 13, 0.94);
      border: 1px solid var(--forest-border);
      padding: 8px 10px;
      border-radius: 10px;
      box-shadow: 0 0 24px rgba(0, 0, 0, 0.85);
    }

    .command-bar button {
      flex: 0 0 auto;
      height: 40px;
      padding: 0 14px;
    }

    .command-bar input[type="text"] {
      flex: 1;
      height: 40px;"""

new_cmd_css = """    .command-bar {
      display: flex;
      gap: 6px;
      align-items: center;
      width: 100%;
      background: rgba(10, 14, 13, 0.94);
      border: 1px solid var(--forest-border);
      padding: 6px 8px;
      border-radius: 10px;
      box-shadow: 0 0 24px rgba(0, 0, 0, 0.85);
    }

    .command-bar button {
      flex: 0 0 auto;
      height: 38px;
      padding: 0 10px;
      font-size: 9.5px;
      letter-spacing: 0.05em;
      white-space: nowrap;
    }

    .command-bar input[type="text"] {
      flex: 1 1 0%;
      min-width: 0;
      width: 100%;
      height: 38px;"""

if old_cmd_css in html:
    html = html.replace(old_cmd_css, new_cmd_css)
    HUD_PATH.write_text(html, encoding="utf-8")
    print("[OK] Compacted CALL N.E.M.E.S.I.S. button and unlocked EXECUTE button visibility!")
else:
    print("[INFO] Command bar CSS already updated.")
    