"""GitHub API client with SQLite caching."""
import requests
from datetime import datetime, timedelta, timezone, date
from agent.config import load, github_token
from agent import database as db

API = "https://api.github.com"

def _h():
    token = github_token()
    h = {"Accept": "application/vnd.github.v3+json"}
    if token:
        h["Authorization"] = f"token {token}"
    return h

def get_repos(username: str) -> list[dict]:
    repos, page = [], 1
    while True:
        r = requests.get(f"{API}/users/{username}/repos", headers=_h(),
            params={"per_page": 100, "page": page, "sort": "updated"}, timeout=10)
        if r.status_code != 200:
            break
        batch = r.json()
        if not batch or isinstance(batch, dict):
            break
        repos.extend(batch)
        page += 1
    return repos

def get_commits(username: str, repo: str, since_days: int = 7) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
    try:
        r = requests.get(f"{API}/repos/{username}/{repo}/commits", headers=_h(),
            params={"author": username, "since": since, "per_page": 50}, timeout=10)
        if r.status_code in (409, 404):
            return []
        return r.json() if isinstance(r.json(), list) else []
    except Exception:
        return []

def get_commit_files(username: str, repo: str, sha: str) -> dict:
    try:
        r = requests.get(f"{API}/repos/{username}/{repo}/commits/{sha}",
            headers=_h(), timeout=10)
        data = r.json()
        files = [f["filename"] for f in data.get("files", [])]
        additions = sum(f.get("additions", 0) for f in data.get("files", []))
        deletions = sum(f.get("deletions", 0) for f in data.get("files", []))
        return {"files": files, "additions": additions, "deletions": deletions}
    except Exception:
        return {"files": [], "additions": 0, "deletions": 0}

def fetch_all_recent(since_days: int = 7, use_cache: bool = True) -> list[dict]:
    """Fetch all commits — returns cached if fresh, else fetches live."""
    if use_cache:
        cached = db.get_cached_commits(since_days)
        if cached:
            return cached

    cfg = load()
    username = cfg["github_username"]
    if not username:
        return []

    repos = get_repos(username)
    all_commits = []

    for repo in repos:
        name = repo["name"]
        commits = get_commits(username, name, since_days)
        for c in commits:
            entry = {
                "sha":      c["sha"][:7],
                "full_sha": c["sha"],
                "repo":     name,
                "message":  c["commit"]["message"].split("\n")[0],
                "date":     c["commit"]["author"]["date"][:10],
                "files":    [],
                "additions": 0,
                "deletions": 0,
            }
            all_commits.append(entry)

    all_commits.sort(key=lambda x: x["date"], reverse=True)
    if all_commits:
        db.cache_commits(all_commits)
    return all_commits

def get_file_stats(since_days: int = 7) -> dict:
    """Returns {filename: {count, additions, deletions, repo}}"""
    cfg = load()
    username = cfg["github_username"]
    if not username:
        return {}

    stats = {}
    repos = get_repos(username)
    for repo in repos:
        commits = get_commits(username, repo["name"], since_days)
        for c in commits[:8]:  # limit API calls
            detail = get_commit_files(username, repo["name"], c["sha"])
            for f in detail["files"]:
                if f not in stats:
                    stats[f] = {"count": 0, "additions": 0, "deletions": 0, "repo": repo["name"]}
                stats[f]["count"] += 1
                stats[f]["additions"] += detail["additions"]
                stats[f]["deletions"] += detail["deletions"]
    return stats

def get_local_staged_diff() -> str:
    """Get git diff --staged output from current directory."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "diff", "--staged", "--stat"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return ""

def get_local_staged_files() -> list[str]:
    import subprocess
    try:
        result = subprocess.run(
            ["git", "diff", "--staged", "--name-only"],
            capture_output=True, text=True, timeout=5
        )
        return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except Exception:
        return []
