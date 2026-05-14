"""
Terminal UI — rich, colorful, beginner-friendly.
This is what people see every time they open terminal.
"""
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from rich import print as rprint
from datetime import date, datetime
import time

from agent import database as db, ai, github_client as gh
from agent.config import load

console = Console()

# ── HELPERS ───────────────────────────────────────────────────

def _spinner(msg: str):
    return Progress(SpinnerColumn(), TextColumn(f"[cyan]{msg}[/cyan]"), transient=True)

def _calendar_panel(n: int = 28) -> Panel:
    days = db.get_calendar(n)
    icons = {"committed": "🟢", "skipped": "⭕", "pending": "🟡", "no_data": "⬜"}
    rows = []
    week = []
    for d in days:
        week.append(icons.get(d["status"], "⬜"))
        if len(week) == 7:
            rows.append("  " + "  ".join(week))
            week = []
    if week:
        rows.append("  " + "  ".join(week))

    stats = db.get_stats()
    legend = "\n  🟢 Committed  ⭕ Skipped  🟡 Pending  ⬜ No data"
    streak_line = f"\n  🔥 [bold yellow]{stats['streak']} day streak[/bold yellow]  |  ✅ {stats['committed']} committed  |  ⏭️  {stats['skipped']} skipped"

    content = "\n".join(rows) + legend + streak_line
    return Panel(content, title="[bold]📅 Activity[/bold]", border_style="dim")

def _stats_row(commits: list[dict], file_stats: dict) -> None:
    cfg = load()
    sprint = db.get_active_sprint()
    stats  = db.get_stats()
    repos  = list(set(c["repo"] for c in commits))

    table = Table.grid(padding=(0, 3))
    table.add_column(justify="center")
    table.add_column(justify="center")
    table.add_column(justify="center")
    table.add_column(justify="center")

    table.add_row(
        f"[bold cyan]{len(commits)}[/bold cyan]\n[dim]commits this week[/dim]",
        f"[bold yellow]{stats['streak']}[/bold yellow]\n[dim]day streak[/dim]",
        f"[bold green]{len(repos)}[/bold green]\n[dim]active repos[/dim]",
        f"[bold magenta]{sum(s['count'] for s in file_stats.values())}[/bold magenta]\n[dim]files changed[/dim]",
    )
    console.print(Panel(table, border_style="dim"))

    if sprint:
        end = sprint["end_date"]
        days_left = (date.fromisoformat(end) - date.today()).days
        console.print(Panel(
            f"[bold]🏃 Sprint:[/bold] {sprint['goal']}\n[dim]Ends {end} ({days_left} days left)[/dim]",
            border_style="yellow"
        ))

_SIGNAL_STYLE = {
    "on_track": ("green",  "On track"),
    "drifting": ("yellow", "Drifting"),
    "overdue":  ("red",    "Overdue"),
}

def _show_goals(commits: list[dict] | None = None):
    goals = db.get_active_goals()
    if not goals:
        return
    from agent import insights
    enriched = insights.goals_with_progress(goals, commits or [])

    table = Table(show_header=True, header_style="bold", border_style="dim")
    table.add_column("Repo", style="cyan")
    table.add_column("Goal")
    table.add_column("Status")
    table.add_column("Deadline", style="yellow")
    for g in enriched:
        days_left = g["days_left"]
        color, label = _SIGNAL_STYLE.get(g["signal"], ("green", "On track"))
        status = f"[{color}]● {label}[/{color}]\n[dim]{g['reason']}[/dim]"
        dl_color = "red" if days_left <= 3 else "yellow" if days_left <= 7 else "green"
        table.add_row(
            g["repo"], g["description"], status,
            f"[{dl_color}]{g['deadline']} ({days_left}d)[/{dl_color}]"
        )
    console.print(Panel(table, title="[bold]🎯 Active Goals[/bold]", border_style="dim"))

# ── COMMIT CHECK-IN ────────────────────────────────────────────

def commit_checkin(commits: list[dict], file_stats: dict):
    console.print(Rule("[bold cyan]📌 Daily Commit Check-in[/bold cyan]"))
    console.print("\n[bold]What are you planning to work on or commit today?[/bold]")
    console.print("[dim]Press Enter with nothing to skip today — no pressure![/dim]\n")

    repos = list(set(c["repo"] for c in commits))
    if repos:
        console.print(f"[dim]Your repos: {', '.join(repos[:6])}[/dim]\n")

    try:
        user_input = Prompt.ask("  [cyan]>[/cyan] You").strip()
    except (EOFError, KeyboardInterrupt):
        user_input = ""

    if not user_input:
        db.upsert_day("skipped")
        console.print("\n[yellow]  ⏭️  Marked as skip for today. Rest is productive too![/yellow]")
        console.print(_calendar_panel())
        return

    # Which repo?
    mentioned = [r for r in repos if r.lower() in user_input.lower()]
    if not mentioned and repos:
        console.print(f"\n[dim]Which repo? ({' / '.join(repos[:6])})[/dim]")
        repo_input = Prompt.ask("  [cyan]>[/cyan] Repo", default=repos[0] if repos else "")
        mentioned = [repo_input]

    # Generate commit message using staged diff if available
    with _spinner("Generating commit message..."):
        diff   = gh.get_local_staged_diff()
        staged = gh.get_local_staged_files()
        files  = staged if staged else [user_input]
        msg    = ai.generate_commit_message(files, diff or user_input)

    console.print(f"\n[bold green]💡 Suggested commit message:[/bold green]")
    console.print(Panel(f"[bold]{msg}[/bold]", border_style="green"))

    choice = Prompt.ask("  Use this? [Y/n/edit]", default="y").strip().lower()
    if choice == "n":
        console.print("[dim]  OK — commit manually whenever you're ready.[/dim]")
    elif choice.startswith("e"):
        msg = Prompt.ask("  Your message").strip() or msg

    db.upsert_day("committed", commit_msg=msg, repos=mentioned)
    console.print(f"\n[bold green]  ✅ Logged![/bold green] [dim]\"{msg}\"[/dim]")
    console.print(_calendar_panel())

    # Run git commit?
    if Confirm.ask("\n  Run `git commit` now?", default=False):
        import subprocess
        r = subprocess.run(["git", "commit", "-m", msg], capture_output=True, text=True)
        if r.returncode == 0:
            console.print(f"[green]  ✅ Committed! {r.stdout.strip()}[/green]")
        else:
            console.print(f"[yellow]  ⚠️  {r.stderr.strip() or 'Make sure you have staged files.'}[/yellow]")

# ── FULL STARTUP DIGEST ────────────────────────────────────────

def run_startup():
    console.clear()
    now = datetime.now().strftime("%A, %B %d — %I:%M %p")
    console.print(Panel.fit(
        f"[bold cyan]⚡ GitMind[/bold cyan]  [dim]{now}[/dim]",
        border_style="cyan"
    ))

    # Already checked in?
    today = db.get_day()
    if today and today["status"] in ("committed", "skipped"):
        console.print(f"\n[green]  ✅ Already checked in today ({today['status'].upper()}).[/green]")
        console.print(_calendar_panel())
        console.print(f"\n[dim]  Type 'gitmind --cli' for interactive mode or 'gitmind --web' for browser dashboard.[/dim]\n")
        return

    # Fetch data
    commits, file_stats = [], {}
    with _spinner("Fetching your GitHub activity..."):
        try:
            commits    = gh.fetch_all_recent(since_days=7)
            file_stats = gh.get_file_stats(since_days=7)
        except Exception as e:
            console.print(f"[yellow]  ⚠️  GitHub fetch error: {e}[/yellow]")

    # Stats row
    _stats_row(commits, file_stats)
    _show_goals(commits)

    # AI summary
    if commits:
        with _spinner("Generating your weekly summary..."):
            summary = ai.summarize_week(commits, file_stats)
        console.print(Panel(summary, title="[bold]📋 This Week[/bold]", border_style="cyan"))

        with _spinner("Thinking about your next tasks..."):
            suggestions = ai.suggest_next_tasks(commits, file_stats)
        console.print(Panel(suggestions, title="[bold]🎯 Suggested Next[/bold]", border_style="magenta"))

        # Blocker detection
        all_repos = [r["name"] for r in gh.get_repos(load()["github_username"])]
        with _spinner("Checking for stalled repos..."):
            blockers = ai.detect_blockers(commits, all_repos)
        if blockers:
            console.print(Panel(blockers, title="[bold yellow]⚠️  Stalled Repos[/bold yellow]", border_style="yellow"))

        # Update AI memory quietly
        ai.update_memory_from_session(commits, file_stats)

    # Commit check-in
    commit_checkin(commits, file_stats)

    # Footer
    console.print(f"\n[dim]  Commands: [cyan]gitmind[/cyan] (menu) · [cyan]gitmind --web[/cyan] (browser dashboard) · [cyan]gitmind ask \"...\"[/cyan][/dim]\n")

# ── INTERACTIVE MENU ───────────────────────────────────────────

MENU = """
  [bold cyan]What do you want to do?[/bold cyan]

  [bold]1[/bold]  Ask a question about my work
  [bold]2[/bold]  See activity calendar
  [bold]3[/bold]  Generate a commit message
  [bold]4[/bold]  Start / view sprint
  [bold]5[/bold]  Add a goal
  [bold]6[/bold]  View goals
  [bold]7[/bold]  See suggested next tasks
  [bold]8[/bold]  Productivity analysis
  [bold]9[/bold]  Open browser dashboard
  [bold]0[/bold]  Exit

"""

def run_menu():
    cfg = load()
    commits, file_stats = [], {}

    # Lazy-load context
    loaded = [False]
    def _ctx():
        if not loaded[0]:
            with _spinner("Loading your data..."):
                try:
                    commits.extend(gh.fetch_all_recent(7))
                    file_stats.update(gh.get_file_stats(7))
                except Exception:
                    pass
            loaded[0] = True
        return commits, file_stats

    console.print(Panel.fit("[bold cyan]⚡ GitMind[/bold cyan]", border_style="cyan"))

    while True:
        console.print(MENU)
        try:
            choice = Prompt.ask("  [cyan]>[/cyan] Choose").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice == "0":
            console.print("\n[dim]  👋 Goodbye! Keep shipping.[/dim]\n")
            break

        elif choice == "1":
            c, fs = _ctx()
            question = Prompt.ask("\n  [cyan]>[/cyan] Ask anything")
            if question.strip():
                with _spinner("Thinking..."):
                    answer = ai.answer_question(question, c, fs)
                console.print(Panel(answer, title="[bold]🤖 Answer[/bold]", border_style="cyan"))

        elif choice == "2":
            console.print(_calendar_panel(35))
            cal = db.get_calendar(14)
            with _spinner("Analyzing your patterns..."):
                insight = ai.analyze_productivity(cal)
            console.print(Panel(insight, title="[bold]💡 Pattern Insight[/bold]", border_style="dim"))

        elif choice == "3":
             from agent.commit_flow import run_commit_flow
             run_commit_flow()

        elif choice == "4":
            sprint = db.get_active_sprint()
            if sprint:
                days_left = (date.fromisoformat(sprint["end_date"]) - date.today()).days
                status_str = f"[red]Ended {abs(days_left)} days ago[/red]" if days_left < 0 else f"{days_left} days left"
                console.print(Panel(
                    f"[bold]Goal:[/bold] {sprint['goal']}\n"
                    f"[bold]Ends:[/bold] {sprint['end_date']} ({status_str})",
                    title="[bold]🏃 Active Sprint[/bold]", border_style="yellow"
                ))
                try:
                    close = Confirm.ask("  Close this sprint and generate retro?", default=days_left <= 0)
                except (EOFError, KeyboardInterrupt):
                    close = False
                if close:
                    c, _ = _ctx()
                    with _spinner("Writing retrospective..."):
                        retro = ai.generate_sprint_retro(sprint, c)
                    db.close_sprint(sprint["id"], retro)
                    console.print(Panel(retro, title="[bold]📝 Sprint Retro[/bold]", border_style="green"))
            else:
                goal = Prompt.ask("\n  [cyan]>[/cyan] Sprint goal")
                days = Prompt.ask("  How many days?", default="7")
                if goal.strip():
                    try:
                        sid = db.create_sprint(goal.strip(), int(days))
                    except ValueError:
                        sid = db.create_sprint(goal.strip(), 7)
                    console.print(f"[green]  ✅ Sprint started! ID #{sid}[/green]")

        elif choice == "5":
            c, _ = _ctx()
            repos = list(set(cm["repo"] for cm in c)) or ["unknown"]
            console.print(f"[dim]  Your repos: {', '.join(repos[:6])}[/dim]")
            repo  = Prompt.ask("  [cyan]>[/cyan] Repo")
            desc  = Prompt.ask("  [cyan]>[/cyan] Goal description")
            dead  = Prompt.ask("  [cyan]>[/cyan] Deadline (YYYY-MM-DD)")
            if desc.strip() and dead.strip():
                db.add_goal(repo, desc, dead)
                console.print("[green]  ✅ Goal added![/green]")

        elif choice == "6":
            c, _ = _ctx()
            _show_goals(c)

        elif choice == "7":
            c, fs = _ctx()
            with _spinner("Thinking..."):
                suggestions = ai.suggest_next_tasks(c, fs)
            console.print(Panel(suggestions, title="[bold]🎯 Next Tasks[/bold]", border_style="magenta"))

        elif choice == "8":
            cal = db.get_calendar(21)
            with _spinner("Analyzing..."):
                insight = ai.analyze_productivity(cal)
            console.print(Panel(insight, title="[bold]📊 Productivity Analysis[/bold]", border_style="cyan"))

        elif choice == "9":
            import webbrowser, threading
            from web.app import run_web
            port = cfg.get("web_port", 7123)
            console.print(f"[cyan]  🌐 Opening dashboard at http://localhost:{port}[/cyan]")
            t = threading.Thread(target=run_web, args=(port,), daemon=True)
            t.start()
            time.sleep(1.2)
            webbrowser.open(f"http://localhost:{port}")
            Prompt.ask("\n  [dim]Press Enter to return to menu[/dim]")

        else:
            console.print("[dim]  Unknown option. Try 1-9 or 0 to exit.[/dim]")
