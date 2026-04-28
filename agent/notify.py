"""
Sends a Windows notification at scheduled time.
Clicking it opens the browser dashboard automatically.
"""
import subprocess
import threading
import time
from agent import database as db


def _open_browser(port: int = 7123):
    """Start Flask and open browser."""
    import webbrowser
    from web.app import run_web
    t = threading.Thread(target=run_web, args=(port,), daemon=True)
    t.start()
    time.sleep(1.5)
    webbrowser.open(f"http://localhost:{port}")
    # Minimize the PowerShell window to taskbar
    import ctypes
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 6)
    # Keep running until user closes terminal
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        pass


def send_and_open(title: str, message: str, port: int = 7123):
    """Send Windows toast notification then open browser dashboard."""

    # Windows PowerShell toast notification
    ps_cmd = f"""
Add-Type -AssemblyName System.Windows.Forms
$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = [System.Drawing.SystemIcons]::Information
$notify.Visible = $true
$notify.ShowBalloonTip(8000, "{title}", "{message}", [System.Windows.Forms.ToolTipIcon]::Info)
Start-Sleep -Seconds 2
$notify.Dispose()
"""
    try:
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-Command", ps_cmd],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
    except Exception:
        pass

    # Open browser dashboard
    _open_browser(port)


def boot_notification():
    """Called at scheduled time — shows notification + opens dashboard."""
    today = db.get_day()
    stats = db.get_stats()
    streak = stats["streak"]

    if today and today["status"] == "committed":
        title = "GitMind ✅ Already committed today!"
        message = f"Streak: {streak} days 🔥 — Dashboard opening..."
    elif today and today["status"] == "skipped":
        title = "GitMind ⏭️ Skipped today"
        message = "Dashboard opening — change your mind anytime."
    else:
        sprint = db.get_active_sprint()
        if sprint:
            title = "GitMind ⚡ Sprint Active"
            message = f"{sprint['goal'][:50]} — Check in now!"
        elif streak >= 3:
            title = f"GitMind 🔥 {streak}-day streak!"
            message = "Don't break it — dashboard opening..."
        else:
            title = "GitMind ⚡ Daily Check-in Time"
            message = "Your digest is ready — opening dashboard..."

    send_and_open(title, message)