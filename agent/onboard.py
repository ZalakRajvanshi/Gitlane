"""
Onboarding wizard — runs only once on first launch.
Friendly, non-technical, step-by-step.
"""
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import print as rprint
from agent import config as cfg
from agent.database import init_db, set_memory

console = Console()

def run():
    console.clear()
    console.print(Panel.fit(
        "[bold cyan]⚡ Welcome to Gitlane![/bold cyan]\n"
        "[dim]Your personal GitHub work assistant[/dim]\n\n"
        "Let's set you up in 2 minutes.\n"
        "[dim]You only need to do this once.[/dim]",
        border_style="cyan"
    ))

    settings = cfg.load()

    # Step 1 — GitHub username
    console.print("\n[bold]Step 1 of 3[/bold] — Your GitHub username")
    console.print("[dim]This is how Gitlane finds your repositories.[/dim]\n")
    username = Prompt.ask("  GitHub username", default=settings.get("github_username") or "")
    while not username.strip():
        console.print("[red]  Username can't be empty.[/red]")
        username = Prompt.ask("  GitHub username")
    settings["github_username"] = username.strip()

    # Step 2 — Groq API key
    console.print("\n[bold]Step 2 of 3[/bold] — Groq API Key (free)")
    console.print("[dim]Groq powers the AI. It's 100% free.[/dim]")
    console.print("  1. Go to [link=https://console.groq.com]https://console.groq.com[/link]")
    console.print("  2. Sign up → API Keys → Create Key")
    console.print("  3. Paste it below\n")

    import os
    from pathlib import Path
    env_path = cfg.BASE_DIR / ".env"
    existing_key = ""
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("GROQ_API_KEY="):
                existing_key = line.split("=", 1)[1].strip()

    if existing_key and existing_key != "your_groq_api_key_here":
        console.print("[green]  ✅ Groq key already set![/green]")
        groq_key = existing_key
    else:
        groq_key = Prompt.ask("  Groq API key", password=True)
        while not groq_key.strip():
            console.print("[red]  Key can't be empty.[/red]")
            groq_key = Prompt.ask("  Groq API key", password=True)

        # Save to .env
        env_lines = []
        if env_path.exists():
            env_lines = [l for l in env_path.read_text().splitlines() if not l.startswith("GROQ_API_KEY")]
        env_lines.append(f"GROQ_API_KEY={groq_key.strip()}")
        env_path.write_text("\n".join(env_lines) + "\n")
        console.print("[green]  ✅ Saved to .env[/green]")

    # Step 3 — GitHub token (optional)
    console.print("\n[bold]Step 3 of 3[/bold] — GitHub Token [dim](optional but recommended)[/dim]")
    console.print("[dim]Unlocks detailed file stats. Without it, only commit messages are tracked.[/dim]")

    want_token = Confirm.ask("  Add a GitHub token now?", default=False)
    if want_token:
        console.print("  Go to [link=https://github.com/settings/tokens]https://github.com/settings/tokens[/link]")
        console.print("  Create token → check [bold]repo[/bold] (read-only is fine)\n")
        gh_token = Prompt.ask("  GitHub token", password=True)
        if gh_token.strip():
            env_lines = []
            if env_path.exists():
                env_lines = [l for l in env_path.read_text().splitlines() if not l.startswith("GITHUB_TOKEN")]
            env_lines.append(f"GITHUB_TOKEN={gh_token.strip()}")
            env_path.write_text("\n".join(env_lines) + "\n")
            console.print("[green]  ✅ Saved![/green]")

    # Ask about their work context for memory
    console.print("\n[bold]One more thing[/bold] — what are you mainly working on? [dim](helps AI give better answers)[/dim]")
    context = Prompt.ask("  e.g. 'building a portfolio for job applications' or 'freelance projects'", default="")
    if context.strip():
        init_db()
        set_memory("work_context", context.strip())

    # Done
    settings["onboarded"] = True
    cfg.save(settings)

    console.print(Panel.fit(
        "[bold green]✅ All set![/bold green]\n\n"
        "Gitlane will now:\n"
        "  • Show your daily digest every morning\n"
        "  • Ask what you're committing today\n"
        "  • Track your streak and goals\n"
        "  • Answer questions about your work\n\n"
        "[dim]Starting now...[/dim]",
        border_style="green"
    ))

    import time
    time.sleep(1.5)
