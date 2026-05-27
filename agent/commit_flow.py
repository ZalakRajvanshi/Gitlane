"""
commit_flow.py — Full smart commit flow
- Auto-create GitHub repo for new projects
- Smart credential detection + auto-fix
- Auto .gitignore generation
- git add + commit + push
"""

import re
import json
import requests
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from agent import git_manager as gm, ai
from agent.config import load, save, github_token

console = Console()

# ── SENSITIVE PATTERNS ────────────────────────────────────────
SENSITIVE_PATTERNS = [
    (r'(?i)(api[_-]?key)\s*=\s*["\']([^"\']{8,})["\']',           "API_KEY"),
    (r'(?i)(secret[_-]?key|secret)\s*=\s*["\']([^"\']{8,})["\']', "SECRET_KEY"),
    (r'(?i)(password|passwd|pwd)\s*=\s*["\']([^"\']{4,})["\']',   "PASSWORD"),
    (r'(?i)(token)\s*=\s*["\']([^"\']{8,})["\']',                 "TOKEN"),
    (r'(?i)(access[_-]?key)\s*=\s*["\']([^"\']{8,})["\']',       "ACCESS_KEY"),
    (r'(sk-[A-Za-z0-9]{20,})',                                     "OPENAI_KEY"),
    (r'(gsk_[A-Za-z0-9]{20,})',                                    "GROQ_KEY"),
    (r'(ghp_[A-Za-z0-9]{20,})',                                    "GITHUB_TOKEN"),
    (r'(AIza[A-Za-z0-9_\-]{30,})',                                 "GOOGLE_KEY"),
]

BLOCKED_FILENAMES = {
    ".env", ".env.local", ".env.production", ".env.development",
    "credentials.json", "secrets.json", "serviceAccountKey.json",
    "private_key.pem", "id_rsa",
}

SKIP_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".mp4", ".zip",
                   ".exe", ".dll", ".pyc", ".db", ".sqlite", ".pem"}

# Default .gitignore content for new projects
DEFAULT_GITIGNORE = """.env
.env.local
.env.production
__pycache__/
*.pyc
*.pyo
.venv/
venv/
env/
node_modules/
.DS_Store
Thumbs.db
*.log
dist/
build/
.idea/
.vscode/
*.sqlite
*.db
credentials.json
secrets.json
serviceAccountKey.json
"""

# ── GITHUB API ────────────────────────────────────────────────

def create_github_repo(repo_name: str, private: bool = True) -> tuple[bool, str]:
    """Create a new GitHub repo via API. Returns (success, clone_url or error)."""
    token = github_token()
    if not token:
        return False, "No GITHUB_TOKEN in .env — needed to create repos."

    r = requests.post(
        "https://api.github.com/user/repos",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        },
        json={
            "name": repo_name,
            "private": private,
            "auto_init": False,
        },
        timeout=10
    )

    if r.status_code == 201:
        return True, r.json()["clone_url"]
    elif r.status_code == 422:
        return False, f"Repo '{repo_name}' already exists on GitHub."
    else:
        return False, f"GitHub API error {r.status_code}: {r.json().get('message', '')}"


def setup_remote_and_push(repo_path: str, clone_url: str) -> tuple[bool, str]:
    """Add remote origin and push."""
    gm._run(["git", "remote", "remove", "origin"], repo_path)  # remove if exists
    code, out, err = gm._run(["git", "remote", "add", "origin", clone_url], repo_path)
    if code != 0:
        return False, err

    # Push with upstream
    code, out, err = gm._run(["git", "push", "-u", "origin", "HEAD"], repo_path)
    if code == 0:
        return True, out
    return False, err or out

# ── GITIGNORE ─────────────────────────────────────────────────

def ensure_gitignore(repo_path: str) -> bool:
    """Create or update .gitignore with safe defaults."""
    gitignore = Path(repo_path) / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(DEFAULT_GITIGNORE, encoding="utf-8")
        return True  # newly created
    # Add any missing entries
    existing = gitignore.read_text(encoding="utf-8", errors="ignore")
    missing = []
    for line in DEFAULT_GITIGNORE.splitlines():
        if line and line not in existing:
            missing.append(line)
    if missing:
        with open(gitignore, "a", encoding="utf-8") as f:
            f.write("\n" + "\n".join(missing))
    return False

# ── CREDENTIAL SCANNER ────────────────────────────────────────

def _scan_file_lines(filepath: Path) -> list[dict]:
    if filepath.suffix.lower() in SKIP_EXTENSIONS:
        return []
    findings = []
    try:
        lines = filepath.read_text(encoding="utf-8", errors="ignore").splitlines()
        for i, line in enumerate(lines, 1):
            for pattern, env_key in SENSITIVE_PATTERNS:
                match = re.search(pattern, line)
                if match:
                    groups = match.groups()
                    value = groups[-1] if groups else match.group(0)
                    if value.lower() in ("your_key_here", "xxx", "***", "", "none", "null", "true", "false"):
                        continue
                    findings.append({
                        "line_num":   i,
                        "line":       line.strip(),
                        "env_key":    env_key,
                        "value":      value,
                        "full_match": match.group(0),
                    })
                    break
    except Exception:
        pass
    return findings


def _autofix_file(filepath: Path, findings: list[dict], env_path: Path):
    content     = filepath.read_text(encoding="utf-8", errors="ignore")
    env_content = env_path.read_text(encoding="utf-8", errors="ignore") if env_path.exists() else ""
    fixed_keys  = []

    for f in findings:
        env_key    = f["env_key"]
        value      = f["value"]
        full_match = f["full_match"]

        # Make key unique
        base_key = env_key
        counter  = 1
        while f"{env_key}={value}" not in env_content and env_key in env_content:
            env_key = f"{base_key}_{counter}"
            counter += 1

        # Replace value with os.getenv()
        new_line = re.sub(
            r'["\'][^"\']*' + re.escape(value) + r'[^"\']*["\']',
            f'os.getenv("{env_key}")',
            full_match
        )
        if new_line == full_match:
            new_line = full_match.replace(f'"{value}"', f'os.getenv("{env_key}")')
            new_line = new_line.replace(f"'{value}'", f'os.getenv("{env_key}")')

        content = content.replace(full_match, new_line, 1)

        if env_key not in env_content:
            env_content += f"\n{env_key}={value}"

        fixed_keys.append(env_key)

    if fixed_keys and "import os" not in content:
        content = "import os\n" + content

    filepath.write_text(content, encoding="utf-8")
    env_path.write_text(env_content.lstrip("\n"), encoding="utf-8")
    return fixed_keys

# ── REPO PICKER ───────────────────────────────────────────────

def _pick_repo(repos: list[dict]) -> dict | None:
    if not repos:
        console.print("[red]  No git repositories found.[/red]")
        return None
    if len(repos) == 1:
        console.print(f"  [dim]Found:[/dim] [cyan]{repos[0]['name']}[/cyan]")
        return repos[0]

    console.print("\n  [bold]Which repo?[/bold]")
    table = Table(show_header=False, border_style="dim", padding=(0, 2))
    table.add_column("Num", style="cyan", width=4)
    table.add_column("Repo")
    for i, r in enumerate(repos, 1):
        has_remote = gm.has_remote(r["path"])
        tag = "[green]GitHub[/green]" if has_remote else "[yellow]local only[/yellow]"
        table.add_row(str(i), f"{r['name']}  {tag}")
    console.print(table)

    choice = Prompt.ask(f"  [cyan]>[/cyan] Pick (1-{len(repos)})")
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(repos):
            return repos[idx]
    except ValueError:
        pass
    console.print("[red]  Invalid.[/red]")
    return None


def _get_or_set_projects_folder() -> str | None:
    cfg = load()
    folder = cfg.get("projects_folder", "")
    if folder and Path(folder).exists():
        return folder

    console.print("\n  [bold]Where are your projects stored?[/bold]")
    console.print("  [dim]Example: C:\\Users\\zalak\\OneDrive\\Desktop\\Projects[/dim]\n")
    folder = Prompt.ask("  [cyan]>[/cyan] Projects folder").strip().strip('"')

    if not Path(folder).exists():
        console.print(f"[red]  Not found: {folder}[/red]")
        return None

    cfg["projects_folder"] = folder
    save(cfg)
    return folder


def _cwd_repo() -> dict | None:
    """If the current working directory is in a git repo, return it as a
    {name, path} dict. Walks up to 3 parents so 'gitlane commit' inside a
    nested subfolder still works without asking 'which repo'."""
    import os
    cwd = Path(os.getcwd())
    for p in [cwd] + list(cwd.parents)[:3]:
        if (p / ".git").exists():
            resolved = p.resolve()
            return {"name": resolved.name, "path": str(resolved)}
    return None

# ── MAIN FLOW ─────────────────────────────────────────────────

def run_commit_flow():
    console.print()

    # Fast path: if the user already cd'd into a git repo, just use it.
    # No projects-folder picker, no list. This is the common case.
    repo = _cwd_repo()
    if repo:
        console.print(f"  [dim]Current folder:[/dim] [cyan]{repo['name']}[/cyan]")
    else:
        folder = _get_or_set_projects_folder()
        if not folder:
            return

        import os
        repos = gm.find_git_repos(folder, cwd=os.getcwd())
        if not repos:
            console.print(f"[yellow]  No git repos found in {folder}[/yellow]")
            cfg = load()
            cfg.pop("projects_folder", None)
            save(cfg)
            return

        repo = _pick_repo(repos)
        if not repo:
            return

    repo_path = repo["path"]
    repo_name = repo["name"]
    env_path  = Path(repo_path) / ".env"

    # ── Auto-create .gitignore if missing ─────────────────────
    created = ensure_gitignore(repo_path)
    if created:
        console.print(f"[green]  ✅ Created .gitignore with safe defaults[/green]")

    # ── Show status ───────────────────────────────────────────
    unstaged = gm.get_unstaged_changes(repo_path)
    console.print(f"\n  [bold]Repo:[/bold] [cyan]{repo_name}[/cyan]  "
                  f"Branch: [yellow]{gm.get_current_branch(repo_path)}[/yellow]  "
                  f"GitHub: {'[green]connected[/green]' if gm.has_remote(repo_path) else '[yellow]not connected[/yellow]'}")

    if not unstaged:
        console.print("[yellow]  No changes to commit.[/yellow]")
        return

    console.print(f"\n  [dim]Changed files ({len(unstaged)}):[/dim]")
    for f in unstaged[:8]:
        console.print(f"    · {f}")
    if len(unstaged) > 8:
        console.print(f"    [dim]... and {len(unstaged)-8} more[/dim]")

    # ── Stage ─────────────────────────────────────────────────
    stage_choice = Prompt.ask("\n  Stage all changes? [Y/n]", default="y").strip().lower()
    if stage_choice == "n":
        return
    ok, msg = gm.stage_all(repo_path)
    if not ok:
        console.print(f"[red]  git add failed: {msg}[/red]")
        return

    staged = gm.get_staged_files(repo_path)
    if not staged:
        console.print("[yellow]  Nothing staged.[/yellow]")
        return

    # ── Smart credential scan ─────────────────────────────────
    console.print("\n  [dim]Scanning for sensitive data...[/dim]")

    all_findings  = {}
    blocked_files = []

    for fname in staged:
        fpath = Path(repo_path) / fname
        if Path(fname).name in BLOCKED_FILENAMES:
            blocked_files.append(fname)
            continue
        findings = _scan_file_lines(fpath)
        if findings:
            all_findings[fname] = findings

    # Block entire sensitive files
    if blocked_files:
        console.print(Panel(
            "\n".join(f"🚨 {f}" for f in blocked_files),
            title="[bold red]⛔ These files must never go to GitHub[/bold red]",
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
        console.print(f"[green]  ✅ Auto-added to .gitignore + unstaged[/green]")

    # Smart fix for files with sensitive lines
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
            "  Auto-fix: move secrets to .env + replace with os.getenv()?",
            default=True
        )

        if autofix:
            gitignore = Path(repo_path) / ".gitignore"
            existing  = gitignore.read_text(encoding="utf-8", errors="ignore") if gitignore.exists() else ""
            if ".env" not in existing:
                with open(gitignore, "a", encoding="utf-8") as gf:
                    gf.write("\n.env\n")

            for fname, findings in all_findings.items():
                fpath    = Path(repo_path) / fname
                fixed    = _autofix_file(fpath, findings, env_path)
                console.print(f"[green]  ✅ {fname} — {', '.join(fixed)} moved to .env[/green]")

            gm.stage_all(repo_path)
            gm._run(["git", "reset", "HEAD", ".env"], repo_path)
            console.print("[cyan]  Continuing with clean files...[/cyan]")
        else:
            for fname in all_findings:
                gm._run(["git", "reset", "HEAD", fname], repo_path)
            console.print("[yellow]  Flagged files removed. Fix manually and retry.[/yellow]")
            return

    # Final staged check
    staged = gm.get_staged_files(repo_path)
    if not staged:
        console.print("[yellow]  Nothing left to commit.[/yellow]")
        return

    console.print(f"\n  [green]{len(staged)} file(s) ready to commit[/green]")

    # ── Describe + generate commit message ────────────────────
    console.print(f"\n  [bold]What did you change?[/bold] [dim](brief description)[/dim]")
    description = Prompt.ask("  [cyan]>[/cyan] You").strip()
    if not description:
        description = f"update {', '.join(staged[:3])}"

    diff = gm.get_staged_diff(repo_path)
    with console.status("[cyan]  Generating commit message...[/cyan]"):
        msg = ai.generate_commit_message(staged, diff or description)

    console.print(Panel(f"[bold]{msg}[/bold]", title="[bold green]💡 Commit Message[/bold green]", border_style="green"))

    edit = Prompt.ask("  Use this? [Y/n/edit]", default="y").strip().lower()
    if edit == "n":
        return
    elif edit.startswith("e"):
        msg = Prompt.ask("  Your message").strip() or msg

    # ── Commit ────────────────────────────────────────────────
    ok, out = gm.commit(repo_path, msg)
    if not ok:
        console.print(f"[red]  Commit failed: {out}[/red]")
        return
    console.print(f"[green]  ✅ Committed![/green]")

    # ── Push / Create GitHub repo ─────────────────────────────
    do_push = Confirm.ask("  Push to GitHub?", default=True)
    if not do_push:
        return

    if gm.has_remote(repo_path):
        # Normal push
        with console.status("[cyan]  Pushing...[/cyan]"):
            ok, out = gm.push(repo_path)
        if ok:
            console.print(f"[bold green]  🚀 Pushed to GitHub![/bold green]")
        else:
            console.print(f"[red]  Push failed: {out}[/red]")
    else:
        # No remote — offer to create GitHub repo
        console.print(f"\n  [yellow]This project has no GitHub repo yet.[/yellow]")
        create = Confirm.ask("  Create a new GitHub repo now?", default=True)

        if not create:
            console.print("[dim]  Skipped. Add a remote manually with: git remote add origin <url>[/dim]")
            return

        # Repo name
        suggested = repo_name.lower().replace(" ", "-").replace("_", "-")
        name = Prompt.ask("  [cyan]>[/cyan] Repo name", default=suggested).strip()

        # Private or public
        visibility = Prompt.ask("  Private or public?", choices=["private", "public"], default="private")
        private = visibility == "private"

        with console.status("[cyan]  Creating GitHub repo...[/cyan]"):
            ok, result = create_github_repo(name, private)

        if not ok:
            console.print(f"[red]  Failed: {result}[/red]")
            console.print("[dim]  Make sure your GITHUB_TOKEN has 'repo' scope at github.com/settings/tokens[/dim]")
            return

        clone_url = result
        console.print(f"[green]  ✅ GitHub repo created: github.com/{load()['github_username']}/{name}[/green]")

        with console.status("[cyan]  Pushing...[/cyan]"):
            ok, out = setup_remote_and_push(repo_path, clone_url)

        if ok:
            console.print(f"[bold green]  🚀 Pushed! Your project is now on GitHub.[/bold green]")
            console.print(f"  [dim]https://github.com/{load()['github_username']}/{name}[/dim]")
        else:
            console.print(f"[red]  Push failed: {out}[/red]")