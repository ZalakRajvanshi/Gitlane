# run_hidden.pyw
# .pyw files run with pythonw.exe on Windows = NO console window at all
# Task Scheduler should call this file instead of main.py --notify

import sys
import os

# Load .env FIRST before any other imports — pythonw.exe has no working directory
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from dotenv import load_dotenv
load_dotenv(os.path.join(_HERE, ".env"), override=True)

from agent import database as db
from agent.config import load
from web.app import run_web

def send_windows_notification(title, message):
    """Send toast notification using PowerShell — no window."""
    import subprocess
    ps = f"""
Add-Type -AssemblyName System.Windows.Forms
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Information
$n.Visible = $true
$n.ShowBalloonTip(8000, "{title}", "{message}", [System.Windows.Forms.ToolTipIcon]::Info)
Start-Sleep -Seconds 3
$n.Dispose()
"""
    subprocess.Popen(
        ["powershell.exe", "-WindowStyle", "Hidden", "-NonInteractive", "-Command", ps],
        creationflags=subprocess.CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

def main():
    db.init_db()
    cfg = load()
    port = cfg.get("web_port", 7123)

    # Build notification message
    today = db.get_day()
    stats = db.get_stats()
    streak = stats["streak"]

    if today and today["status"] == "committed":
        title = "GitMind - Already committed today!"
        message = f"Streak: {streak} days - Dashboard opening..."
    elif today and today["status"] == "skipped":
        title = "GitMind - Skipped today"
        message = "Dashboard opening..."
    else:
        sprint = db.get_active_sprint()
        if sprint:
            title = "GitMind - Sprint Active"
            message = f"{sprint['goal'][:50]} - Check in now!"
        elif streak >= 3:
            title = f"GitMind - {streak} day streak!"
            message = "Don't break it - dashboard opening..."
        else:
            title = "GitMind - Daily Check-in"
            message = "Your digest is ready - opening dashboard..."

    # Start Flask in background thread
    t = threading.Thread(target=run_web, args=(port,), daemon=True)
    t.start()
    time.sleep(1.5)

    # Send notification
    send_windows_notification(title, message)

    # Open browser
    webbrowser.open(f"http://localhost:{port}")

    # Keep process alive silently (no window)
    try:
        while True:
            time.sleep(60)
    except Exception:
        pass

if __name__ == "__main__":
    main()
