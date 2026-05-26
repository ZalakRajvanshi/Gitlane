#!/usr/bin/env python3
"""
Gitlane -- entrypoint
Usage:
  python main.py            -> startup mode (default, runs on terminal open)
  python main.py --cli      -> interactive menu only
  python main.py --web      -> open browser dashboard
  python main.py --notify   -> send boot notification only (for Task Scheduler)
  python main.py commit     -> smart commit from any project folder
  python main.py ask "..."  -> one-shot question
"""
import sys
import os

# Force UTF-8 output on Windows to support emojis
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import database as db
from agent.config import load, save

def main():
    db.init_db()
    cfg = load()

    args = sys.argv[1:]

    # First-time onboarding
    if not cfg.get("onboarded") or not cfg.get("github_username"):
        from agent.onboard import run as onboard
        onboard()
        cfg = load()

    # --schedule HH:MM — (re)create the daily Windows scheduled task at the given
    # local time, with "synchronize across time zones" enabled so the trigger
    # always fires at the same wall-clock time regardless of TZ changes.
    if "--schedule" in args:
        from rich.console import Console
        c = Console()
        idx = args.index("--schedule")
        when = args[idx + 1] if idx + 1 < len(args) else "18:00"
        try:
            hh, mm = [int(x) for x in when.split(":")]
            assert 0 <= hh < 24 and 0 <= mm < 60
        except Exception:
            c.print(f"[red]  Invalid time '{when}'. Use HH:MM (e.g. 18:00 for 6 PM).[/red]")
            return
        if sys.platform != "win32":
            c.print("[yellow]  --schedule only supported on Windows.[/yellow]")
            return
        import subprocess
        here = os.path.dirname(os.path.abspath(__file__))
        venv_py = os.path.join(here, ".venv", "Scripts", "python.exe")
        py = venv_py if os.path.exists(venv_py) else sys.executable
        ps = f"""
$task = 'Gitlane_Daily'
$action = New-ScheduledTaskAction -Execute '{py}' -Argument '"{os.path.join(here,'main.py')}" --notify' -WorkingDirectory '{here}'
$trigger = New-ScheduledTaskTrigger -Daily -At ([datetime]::ParseExact('{hh:02d}:{mm:02d}','HH:mm',$null))
$trigger.StartBoundary = ([datetime]::Today.AddHours({hh}).AddMinutes({mm})).ToString('s')
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -WakeToRun
Unregister-ScheduledTask -TaskName $task -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger -Settings $settings -RunLevel Limited -Force | Out-Null
$next = (Get-ScheduledTaskInfo -TaskName $task).NextRunTime
Write-Host ('Scheduled. Next run: ' + $next)
"""
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
        if r.returncode == 0:
            c.print(f"[green]  ✅ Scheduled daily at {hh:02d}:{mm:02d} local time.[/green]")
            c.print(f"[dim]  {r.stdout.strip()}[/dim]")
        else:
            c.print(f"[red]  Failed: {r.stderr.strip() or r.stdout.strip()}[/red]")
            c.print("[dim]  Try running PowerShell as your user (not admin) and retry.[/dim]")
        return

    # --notify: ONLY send notification + open browser (for Task Scheduler)
    if "--notify" in args:
        from agent.notify import boot_notification
        boot_notification()

    # --web: open browser dashboard only
    elif "--web" in args:
        import webbrowser, threading, time
        from web.app import run_web
        from rich.console import Console
        port = cfg.get("web_port", 7123)
        Console().print(f"[cyan]  Dashboard -> http://localhost:{port}[/cyan]  (Ctrl+C to stop)")
        t = threading.Thread(target=run_web, args=(port,), daemon=False)
        t.start()
        time.sleep(0.8)
        webbrowser.open(f"http://localhost:{port}")
        try:
            t.join()
        except KeyboardInterrupt:
            print("\n  Goodbye!")

    # --cli: interactive menu only
    elif "--cli" in args:
        from agent.tui import run_menu
        run_menu()

    # commit: run commit flow directly
    elif args and args[0] == "commit":
        from agent.commit_flow import run_commit_flow
        run_commit_flow()

    # ask "question": one-shot question
    elif args and args[0] == "ask":
        question = " ".join(args[1:])
        if not question:
            print('Usage: python main.py ask "your question"')
            return
        from agent import github_client as gh, ai
        from rich.console import Console
        from rich.panel import Panel
        console = Console()
        with console.status("[cyan]Thinking...[/cyan]"):
            commits    = gh.fetch_all_recent(7)
            file_stats = gh.get_file_stats(7)
            answer     = ai.answer_question(question, commits, file_stats)
        console.print(Panel(answer, title="[bold]Gitlane[/bold]", border_style="cyan"))

    # Default: normal terminal UI, NO browser, NO notification
    else:
        from agent.tui import run_startup, run_menu
        run_startup()
        run_menu()

if __name__ == "__main__":
    main()