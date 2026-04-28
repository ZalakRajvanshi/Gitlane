#!/usr/bin/env python3
"""
GitMind -- entrypoint
Usage:
  python main.py            -> startup mode (default, runs on terminal open)
  python main.py --cli      -> interactive menu only
  python main.py --web      -> open browser dashboard
  python main.py --notify   -> send boot notification only (for Task Scheduler)
  python main.py ask "..."  -> one-shot question
"""
import sys
import os
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
        console.print(Panel(answer, title="[bold]GitMind[/bold]", border_style="cyan"))

    # Default: normal terminal UI, NO browser, NO notification
    else:
        from agent.tui import run_startup, run_menu
        run_startup()
        run_menu()

if __name__ == "__main__":
    main()