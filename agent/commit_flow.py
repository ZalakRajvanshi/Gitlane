"""
commit_flow.py
Drop this in: agent/commit_flow.py

Full commit flow:
- Finds all git repos in projects folder
- Smart credential detection with line-level fix
- Auto moves secrets to .env + replaces with os.getenv()
- git add + commit + push
"""

import re
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from agent import git_manager as gm, ai
from agent.config import load, save

console = Console()

# Patterns that detect sensitive values with their line content
SENSITIVE_PATTERNS = [
    (r'(?i)(api[_-]?key)\s*=\s*["\']([^"\']{8,})["\']',       "API_KEY"),
    (r'(?i)(secret[_-]?key|secret)\s*=\s*["\']([^"\']{8,})["\']', "SECRET_KEY"),
    (r'(?i)(password|passwd|pwd)\s*=\s*["\']([^"\']{4,})["\']',   "PASSWORD"),
    (r'(?i)(token)\s*=\s*["\']([^"\']{8,})["\']',              "TOKEN"),
    (r'(?i)(access[_-]?key)\s*=\s*["\']([^"\']{8,})["\']',    "ACCESS_KEY"),
    (r'(sk-[A-Za-z0-9]{20,})',                                  "OPENAI_KEY"),
    (r'(gsk_[A-Za-z0-9]{20,})',                                 "GROQ_KEY"),
    (r'(ghp_[A-Za-z0-9]{20,})',                                 "GITHUB_TOKEN"),
    (r'(AIza[A-Za-z0-9_\-]{30,})',                              "GOOGLE_KEY"),
]

BLOCKED_FILENAMES = {
    ".env", ".env.local", ".env.production",
    "credentials.json", "secrets.json", "serviceAccountKey.json",
    "private_key.pem", "id_rsa",
}

SKIP_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".mp4", ".zip",
                   ".exe", ".dll", ".pyc", ".db", ".sqlite"}


def _scan_file_lines(filepath: Path) -> list[dict]:
    """
    Scan a file line by line for sensitive values.
    Returns list of {line_num, line, env_key, value, pattern}
    """
    if filepath.suffix.lower() in SKIP_EXTENSIONS:
        return []
    findings = []
    try:
        lines = filepath.read_text(encoding="utf-8", errors="ignore").splitlines()
        for i, line in enumerate(lines, 1):
            for pattern, env_key in SENSITIVE_PATTERNS:
                match = re.search(pattern, line)
                if match:
                    # Extract the actual value
                    groups = match.groups()
                    value = groups[-1] if groups else match.group(0)
                    # Skip if it looks like a placeholder
                    if value.lower() in ("your_key_here", "xxx", "***", "", "none", "null"):
                        continue
                    findings.append({
                        "line_num": i,
                        "line":     line.strip(),
                        "env_key":  env_key,
                        "value":    value,
                        "pattern":  pattern,
                        "full_match": match.group(0),
                    })
                    break  # one finding per line
    except Exception:
        pass
    return findings


def _autofix_file(filepath: Path, findings: list[dict], env_path: Path):
    """
    For each finding:
    1. Replace value in source file with os.getenv("KEY")
    2. Add KEY=value to .env
    3. Add import os if not present
    """
    content = filepath.read_text(encoding="utf-8", errors="ignore")

    # Read existing .env
    env_content = env_path.read_text(encoding="utf-8", errors="ignore") if env_path.exists() else ""

    fixed_keys = []

    for f in findings:
        env_key  = f["env_key"]
        value    = f["value"]
        full_match = f["full_match"]

        # Make env_key unique if already exists
        base_key = env_key
        counter  = 1
        while env_key in env_content:
            # Check if same value already set
            if f'{env_key}={value}' in env_content or f'{env_key}="{value}"' in env_content:
                break
            env_key = f"{base_key}_{counter}"
            counter += 1

        # Replace in source file — swap the value with os.getenv()
        # Try to replace the whole assignment
        new_line = re.sub(
            f'["\'][^"\']*{re.escape(value)}[^"\']*["\']',
            f'os.getenv("{env_key}")',
            full_match
        )
        if new_line == full_match:
            # Fallback: replace just the value
            new_line = full_match.replace(f'"{value}"', f'os.getenv("{env_key}")')
            new_line = new_line.replace(f"'{value}'", f'os.getenv("{env_key}")')

        content = content.replace(full_match, new_line, 1)

        # Add to .env if not already there
        if env_key not in env_content:
            env_content += f"\n{env_key}={value}"

        fixed_keys.append(env_key)

    # Add `import os` at top if not present
    if fixed_keys and "import os" not in content:
        content = "import os\n" + content

    # Write back
    filepath.write_text(content, encoding="utf-8")
    env_path.write_text(env_content.lstrip("\n"), encoding="utf-8")

    return fixed_keys


def _pick_repo(repos: list[dict]) -> dict | None:
    if not repos:
        console.print("[red]  No git repositories found.[/red]")
        return None
    if len(repos) == 1:
        console.print(f"  [dim]Repo:[/dim] [cyan]{repos[0]['name']}[/cyan]")
        return repos[0]

    console.print("\n  [bold]Which repo?[/bold]")
    table = Table(show_header=False, border_style="dim", padding=(0, 2))
    table.add_column("Num", style="cyan", width=4)
    table.add_column("Repo")
    table.add_column("Path", style="dim")
    for i, r in enumerate(repos, 1):
        table.add_row(str(i), r["name"], r["path"])
    console.print(table)

    choice = Prompt.ask(f"  [cyan]>[/cyan] Pick (1-{len(repos)})")
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(repos):
            return repos[idx]
    except ValueError:
        pass
    console.print("[red]  Invalid choice.[/red]")
    return None


def _get_or_set_projects_folder() -> str | None:
    cfg = load()
    folder = cfg.get("projects_folder", "")
    if folder and Path(folder).exists():
        return folder

    console.print("\n  [bold]Where are your projects stored?[/bold]")
    console.print("  [dim]Example: C:\\Users\\zalak\\OneDrive\\Desktop\\Projects[/dim]\n")
    folder = Prompt.ask("  [cyan]>[/cyan] Projects folder path").strip().strip('"')

    if not Path(folder).exists():
        console.print(f"[red]  Folder not found: {folder}[/red]")
        return None

    cfg["projects_folder"] = folder
    save(cfg)
    console.print(f"[green]  Saved![/green]")
    return folder


def run_commit_flow():
    """Full smart commit flow."""
    console.print()

    # Get projects folder
    folder = _get_or_set_projects_folder()
    if not folder:
        return

    # Find repos
    repos = gm.find_git_repos(folder)
    if not repos:
        console.print(f"[yellow]  No git repos found in {folder}[/yellow]")
        cfg = load()
        cfg.pop("projects_folder", None)
        save(cfg)
        return

    # Pick repo
    repo = _pick_repo(repos)
    if not repo:
        return

    repo_path = repo["path"]
    repo_name = repo["name"]
    env_path  = Path(repo_path) / ".env"

    # Show status
    unstaged = gm.get_unstaged_changes(repo_path)
    console.print(f"\n  [bold]Repo:[/bold] [cyan]{repo_name}[/cyan]")
    console.print(f"  Branch: [yellow]{gm.get_current_branch(repo_path)}[/yellow]")

    if unstaged:
        console.print(f"\n  [dim]Changed files ({len(unstaged)}):[/dim]")
        for f in unstaged[:8]:
            console.print(f"    [dim]·[/dim] {f}")
        if len(unstaged) > 8:
            console.print(f"    [dim]... and {len(unstaged)-8} more[/dim]")

    # Stage files
    if unstaged:
        stage_choice = Prompt.ask("\n  Stage all changes? [Y/n]", default="y").strip().lower()
        if stage_choice == "n":
            console.print("[dim]  Nothing staged.[/dim]")
            return
        ok, msg = gm.stage_all(repo_path)
        if not ok:
            console.print(f"[red]  git add failed: {msg}[/red]")
            return

    # Get staged files
    staged = gm.get_staged_files(repo_path)
    if not staged:
        console.print("[yellow]  Nothing staged to commit.[/yellow]")
        return

    console.print(f"\n  [green]Staged {len(staged)} file(s)[/green]")

    # ── SMART CREDENTIAL SCAN ─────────────────────────────────
    console.print("  [dim]Scanning for sensitive data...[/dim]")

    all_findings = {}  # {filename: [findings]}
    blocked_files = []  # entire file blocked (e.g. .env itself)

    for fname in staged:
        fpath = Path(repo_path) / fname

        # Check blocked filenames first
        if Path(fname).name in BLOCKED_FILENAMES:
            blocked_files.append(fname)
            continue

        findings = _scan_file_lines(fpath)
        if findings:
            all_findings[fname] = findings

    # Handle fully blocked files (.env etc)
    if blocked_files:
        console.print(Panel(
            "\n".join(f"🚨 {f}" for f in blocked_files) +
            "\n\n[bold]These files should never be on GitHub.[/bold]",
            title="[bold red]⛔ Blocked Files[/bold red]",
            border_style="red"
        ))
        gitignore = Path(repo_path) / ".gitignore"
        existing  = gitignore.read_text(encoding="utf-8", errors="ignore") if gitignore.exists() else ""
        with open(gitignore, "a", encoding="utf-8") as gf:
            for fname in blocked_files:
                base = Path(fname).name
                if base not in existing:
                    gf.write(f"\n{base}")
        for fname in blocked_files:
            gm._run(["git", "reset", "HEAD", fname], repo_path)
        console.print(f"[green]  ✅ Auto-added to .gitignore + unstaged: {', '.join(blocked_files)}[/green]")

    # Handle files with sensitive lines
    if all_findings:
        console.print()
        for fname, findings in all_findings.items():
            console.print(Panel(
                "\n".join(
                    f"  Line {f['line_num']}: [dim]{f['line'][:80]}[/dim]\n"
                    f"  [yellow]→ Will move to .env as {f['env_key']}[/yellow]"
                    for f in findings
                ),
                title=f"[bold yellow]⚠️  Sensitive data in {fname}[/bold yellow]",
                border_style="yellow"
            ))

        autofix = Confirm.ask(
            "\n  Auto-fix: move secrets to .env + replace with os.getenv() in your files?",
            default=True
        )

        if autofix:
            # Ensure .env is in .gitignore
            gitignore = Path(repo_path) / ".gitignore"
            existing  = gitignore.read_text(encoding="utf-8", errors="ignore") if gitignore.exists() else ""
            if ".env" not in existing:
                with open(gitignore, "a", encoding="utf-8") as gf:
                    gf.write("\n.env\n")
                console.print("[green]  ✅ .env added to .gitignore[/green]")

            for fname, findings in all_findings.items():
                fpath     = Path(repo_path) / fname
                fixed     = _autofix_file(fpath, findings, env_path)
                console.print(f"[green]  ✅ {fname} — moved {', '.join(fixed)} to .env + replaced with os.getenv()[/green]")

            # Re-stage fixed files (they changed)
            gm.stage_all(repo_path)
            # Make sure .env is NOT staged
            gm._run(["git", "reset", "HEAD", ".env"], repo_path)

            console.print("[cyan]  Continuing with clean, safe files...[/cyan]")
        else:
            # User said no — unstage flagged files
            for fname in all_findings:
                gm._run(["git", "reset", "HEAD", fname], repo_path)
            console.print("[yellow]  Flagged files removed from staging. Fix them manually and try again.[/yellow]")
            return

    # Final staged list
    staged = gm.get_staged_files(repo_path)
    if not staged:
        console.print("[yellow]  Nothing left to commit.[/yellow]")
        return

    # Describe changes
    console.print(f"\n  [bold]Briefly describe what you changed:[/bold]")
    description = Prompt.ask("  [cyan]>[/cyan] You").strip()
    if not description:
        description = f"update {', '.join(staged[:3])}"

    # Generate commit message
    diff = gm.get_staged_diff(repo_path)
    with console.status("[cyan]  Generating commit message...[/cyan]"):
        msg = ai.generate_commit_message(staged, diff or description)

    console.print(Panel(f"[bold]{msg}[/bold]", title="[bold green]💡 Commit Message[/bold green]", border_style="green"))

    edit = Prompt.ask("  Use this? [Y/n/edit]", default="y").strip().lower()
    if edit == "n":
        console.print("[dim]  Cancelled.[/dim]")
        return
    elif edit.startswith("e"):
        msg = Prompt.ask("  Your message").strip() or msg

    # Commit
    ok, out = gm.commit(repo_path, msg)
    if not ok:
        console.print(f"[red]  Commit failed: {out}[/red]")
        return
    console.print(f"[green]  ✅ Committed![/green] [dim]{out.splitlines()[0] if out else ''}[/dim]")

    # Push
    if not gm.has_remote(repo_path):
        console.print("[yellow]  No remote set — skipping push.[/yellow]")
        return

    do_push = Confirm.ask("  Push to GitHub now?", default=True)
    if do_push:
        with console.status("[cyan]  Pushing...[/cyan]"):
            ok, out = gm.push(repo_path)
        if ok:
            console.print(f"[bold green]  Pushed to GitHub![/bold green]")
        else:
            console.print(f"[red]  Push failed: {out}[/red]")
            console.print("[dim]  Try: git push  manually in your project folder.[/dim]")
            