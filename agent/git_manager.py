"""
git_manager.py
Drop this in: gitmind_v2/agent/git_manager.py

Handles:
- Scanning a projects folder for git repos
- Detecting sensitive/credential files before commit
- Auto git add + commit + push
"""

import os
import re
import subprocess
from pathlib import Path

# ── SENSITIVE FILE / CONTENT PATTERNS ─────────────────────────

BLOCKED_FILENAMES = {
    ".env", ".env.local", ".env.production", ".env.development",
    "secrets.json", "credentials.json", "config.secret.json",
    "serviceAccountKey.json", "firebase-adminsdk.json",
    "private_key.pem", "id_rsa", "id_rsa.pub", "*.p12", "*.pfx",
}

BLOCKED_PATTERNS = [
    r"(?i)(api[_-]?key|apikey)\s*=\s*['\"]?[A-Za-z0-9_\-]{10,}",
    r"(?i)(secret[_-]?key|secret)\s*=\s*['\"]?[A-Za-z0-9_\-]{10,}",
    r"(?i)(password|passwd|pwd)\s*=\s*['\"]?.{4,}",
    r"(?i)(token)\s*=\s*['\"]?[A-Za-z0-9_\-\.]{10,}",
    r"(?i)(aws_access_key_id|aws_secret)\s*=\s*['\"]?[A-Za-z0-9+/]{10,}",
    r"sk-[A-Za-z0-9]{20,}",           # OpenAI keys
    r"gsk_[A-Za-z0-9]{20,}",          # Groq keys
    r"ghp_[A-Za-z0-9]{20,}",          # GitHub tokens
    r"AIza[A-Za-z0-9_\-]{30,}",       # Google API keys
]

SKIP_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".mp4", ".zip", ".exe", ".dll", ".pyc"}


def _run(cmd: list, cwd: str) -> tuple[int, str, str]:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def find_git_repos(root_folder: str) -> list[dict]:
    """Scan a folder and return all git repos found inside."""
    root = Path(root_folder)
    repos = []
    if not root.exists():
        return repos
    # Check root itself
    if (root / ".git").exists():
        repos.append({"name": root.name, "path": str(root)})
    # Check one level deep
    for item in root.iterdir():
        if item.is_dir() and (item / ".git").exists():
            repos.append({"name": item.name, "path": str(item)})
    return repos


def get_staged_files(repo_path: str) -> list[str]:
    """Get list of staged files in a repo."""
    code, out, _ = _run(["git", "diff", "--staged", "--name-only"], repo_path)
    if code != 0 or not out:
        return []
    return [f.strip() for f in out.splitlines() if f.strip()]


def get_unstaged_changes(repo_path: str) -> list[str]:
    """Get list of changed but unstaged files."""
    code, out, _ = _run(["git", "status", "--short"], repo_path)
    files = []
    for line in out.splitlines():
        line = line.strip()
        if line:
            files.append(line[2:].strip())
    return files


def get_staged_diff(repo_path: str) -> str:
    """Get diff summary of staged files."""
    _, out, _ = _run(["git", "diff", "--staged", "--stat"], repo_path)
    return out[:600] if out else ""


def scan_for_credentials(repo_path: str, files: list[str]) -> list[str]:
    """
    Scan files for sensitive data.
    Returns list of warnings. Empty = safe to commit.
    """
    warnings = []
    repo = Path(repo_path)

    for fname in files:
        fpath = repo / fname

        # Check blocked filenames
        for blocked in BLOCKED_FILENAMES:
            if blocked.startswith("*"):
                if fname.endswith(blocked[1:]):
                    warnings.append(f"🚨 BLOCKED FILE: {fname} (matches {blocked})")
            elif Path(fname).name == blocked:
                warnings.append(f"🚨 BLOCKED FILE: {fname} — likely contains secrets")

        # Skip binary files
        if Path(fname).suffix.lower() in SKIP_EXTENSIONS:
            continue

        # Check file content
        try:
            if not fpath.exists():
                continue
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            for pattern in BLOCKED_PATTERNS:
                match = re.search(pattern, content)
                if match:
                    warnings.append(
                        f"🚨 SENSITIVE DATA in {fname}: looks like a credential/key/password"
                    )
                    break
        except Exception:
            pass

    return warnings


def stage_all(repo_path: str) -> tuple[bool, str]:
    """Run git add -A to stage all changes."""
    code, out, err = _run(["git", "add", "-A"], repo_path)
    return code == 0, err or out


def commit(repo_path: str, message: str) -> tuple[bool, str]:
    """Run git commit."""
    code, out, err = _run(["git", "commit", "-m", message], repo_path)
    if code == 0:
        return True, out
    return False, err or out


def push(repo_path: str) -> tuple[bool, str]:
    """Run git push."""
    code, out, err = _run(["git", "push"], repo_path)
    if code == 0:
        return True, out or "Pushed successfully"
    # Try push with upstream set
    code2, out2, err2 = _run(["git", "push", "--set-upstream", "origin", "HEAD"], repo_path)
    if code2 == 0:
        return True, out2 or "Pushed (upstream set)"
    return False, err2 or err or "Push failed"


def get_current_branch(repo_path: str) -> str:
    _, out, _ = _run(["git", "branch", "--show-current"], repo_path)
    return out or "main"


def has_remote(repo_path: str) -> bool:
    _, out, _ = _run(["git", "remote"], repo_path)
    return bool(out.strip())
