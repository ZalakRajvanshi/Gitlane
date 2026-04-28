"""
git_manager.py — Git operations helper
- Finds repos 2 levels deep (catches nested repos)
- Staged file detection
- Credential scanning
- commit/push helpers
"""

import os
import re
import subprocess
from pathlib import Path

BLOCKED_FILENAMES = {
    ".env", ".env.local", ".env.production", ".env.development",
    "secrets.json", "credentials.json", "config.secret.json",
    "serviceAccountKey.json", "firebase-adminsdk.json",
    "private_key.pem", "id_rsa", "id_rsa.pub",
}

BLOCKED_PATTERNS = [
    r"(?i)(api[_-]?key|apikey)\s*=\s*['\"]?[A-Za-z0-9_\-]{10,}",
    r"(?i)(secret[_-]?key|secret)\s*=\s*['\"]?[A-Za-z0-9_\-]{10,}",
    r"(?i)(password|passwd|pwd)\s*=\s*['\"]?.{4,}",
    r"(?i)(token)\s*=\s*['\"]?[A-Za-z0-9_\-\.]{10,}",
    r"sk-[A-Za-z0-9]{20,}",
    r"gsk_[A-Za-z0-9]{20,}",
    r"ghp_[A-Za-z0-9]{20,}",
    r"AIza[A-Za-z0-9_\-]{30,}",
]

SKIP_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".mp4", ".zip",
                   ".exe", ".dll", ".pyc", ".db", ".sqlite"}


def _run(cmd: list, cwd: str) -> tuple:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def find_git_repos(root_folder: str) -> list[dict]:
    """Scan folder for git repos — goes 2 levels deep."""
    root  = Path(root_folder)
    repos = []
    seen  = set()

    def add(path: Path):
        p = str(path.resolve())
        if p not in seen:
            seen.add(p)
            repos.append({"name": path.name, "path": str(path)})

    if not root.exists():
        return repos

    # Root itself
    if (root / ".git").exists():
        add(root)

    # One level deep
    try:
        for item in root.iterdir():
            if not item.is_dir():
                continue
            if item.name.startswith("."):
                continue
            if (item / ".git").exists():
                add(item)
            else:
                # Two levels deep
                try:
                    for sub in item.iterdir():
                        if sub.is_dir() and (sub / ".git").exists():
                            add(sub)
                except PermissionError:
                    pass
    except PermissionError:
        pass

    return repos


def get_staged_files(repo_path: str) -> list[str]:
    code, out, _ = _run(["git", "diff", "--staged", "--name-only"], repo_path)
    if code != 0 or not out:
        return []
    return [f.strip() for f in out.splitlines() if f.strip()]


def get_unstaged_changes(repo_path: str) -> list[str]:
    _, out, _ = _run(["git", "status", "--short"], repo_path)
    files = []
    for line in out.splitlines():
        line = line.strip()
        if line:
            files.append(line[2:].strip())
    return files


def get_staged_diff(repo_path: str) -> str:
    _, out, _ = _run(["git", "diff", "--staged", "--stat"], repo_path)
    return out[:600] if out else ""


def scan_for_credentials(repo_path: str, files: list[str]) -> list[str]:
    warnings = []
    repo = Path(repo_path)
    for fname in files:
        fpath = repo / fname
        for blocked in BLOCKED_FILENAMES:
            if blocked.startswith("*"):
                if fname.endswith(blocked[1:]):
                    warnings.append(f"🚨 BLOCKED FILE: {fname}")
            elif Path(fname).name == blocked:
                warnings.append(f"🚨 BLOCKED FILE: {fname} — likely contains secrets")
        if Path(fname).suffix.lower() in SKIP_EXTENSIONS:
            continue
        try:
            if not fpath.exists():
                continue
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            for pattern in BLOCKED_PATTERNS:
                if re.search(pattern, content):
                    warnings.append(f"🚨 SENSITIVE DATA in {fname}")
                    break
        except Exception:
            pass
    return warnings


def stage_all(repo_path: str) -> tuple:
    code, out, err = _run(["git", "add", "-A"], repo_path)
    return code == 0, err or out


def commit(repo_path: str, message: str) -> tuple:
    code, out, err = _run(["git", "commit", "-m", message], repo_path)
    if code == 0:
        return True, out
    return False, err or out


def push(repo_path: str) -> tuple:
    code, out, err = _run(["git", "push"], repo_path)
    if code == 0:
        return True, out or "Pushed"
    code2, out2, err2 = _run(["git", "push", "--set-upstream", "origin", "HEAD"], repo_path)
    if code2 == 0:
        return True, out2 or "Pushed"
    return False, err2 or err or "Push failed"


def get_current_branch(repo_path: str) -> str:
    _, out, _ = _run(["git", "branch", "--show-current"], repo_path)
    return out or "main"


def has_remote(repo_path: str) -> bool:
    _, out, _ = _run(["git", "remote"], repo_path)
    return bool(out.strip())


def get_local_staged_diff() -> str:
    try:
        r = subprocess.run(["git", "diff", "--staged", "--stat"],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip()
    except Exception:
        return ""


def get_local_staged_files() -> list[str]:
    try:
        r = subprocess.run(["git", "diff", "--staged", "--name-only"],
                           capture_output=True, text=True, timeout=5)
        return [f.strip() for f in r.stdout.strip().split("\n") if f.strip()]
    except Exception:
        return []