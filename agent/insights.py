"""
Coach logic — derived signals from git activity.
Pure functions, no I/O — safe to call from web, terminal, or the extension.
"""
import re
from datetime import date

_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "into", "your",
    "you", "are", "was", "will", "have", "has", "had", "but", "not", "all",
    "can", "out", "use", "using", "add", "added", "update", "updated", "fix",
    "fixed", "make", "made", "new", "via", "now", "get", "set", "run",
    "should", "would", "could", "want", "need", "more", "than", "then",
    "when", "what", "which", "while", "also", "just", "like", "some",
}


def _keywords(text: str) -> set[str]:
    """Extract meaningful lowercase keywords from a string."""
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if len(w) > 3 and w not in _STOPWORDS}


def goal_progress(goal: dict, commits: list[dict]) -> dict:
    """
    Match a goal against recent commits and derive an on-track / drifting signal.

    goal:    dict with repo, description, deadline, created_at
    commits: list of {repo, message, date} (date as 'YYYY-MM-DD')

    Returns the goal dict enriched with: signal, reason, progress,
    repo_commits, matched_commits, days_left, days_elapsed.
    """
    today = date.today()

    created_str = (goal.get("created_at") or "")[:10]
    try:
        created_d = date.fromisoformat(created_str) if created_str else today
    except ValueError:
        created_d = today

    try:
        deadline_d = date.fromisoformat(goal.get("deadline", ""))
    except ValueError:
        deadline_d = today

    days_elapsed = max(1, (today - created_d).days)
    days_left    = (deadline_d - today).days

    repo = (goal.get("repo") or "").strip().lower()
    kws  = _keywords(goal.get("description", ""))

    repo_commits = [
        c for c in commits
        if (c.get("repo", "") or "").strip().lower() == repo
        and (c.get("date", "") or "") >= created_str
    ] if created_str else [
        c for c in commits
        if (c.get("repo", "") or "").strip().lower() == repo
    ]

    matched = [c for c in repo_commits if kws & _keywords(c.get("message", ""))]

    # ── Derive the signal + a human-readable reason ──────────────
    if days_left < 0:
        signal = "overdue"
        reason = f"{abs(days_left)}d past deadline"
    elif not repo_commits:
        if days_elapsed >= 2:
            signal = "drifting"
            reason = f"no commits in {goal.get('repo','')} since you set this"
        else:
            signal = "on_track"
            reason = "just started"
    elif matched:
        signal = "on_track"
        reason = f"{len(matched)} commit{'' if len(matched)==1 else 's'} match this goal"
    else:
        if days_left <= 2:
            signal = "drifting"
            reason = f"active in {goal.get('repo','')} but nothing on this goal yet"
        else:
            signal = "on_track"
            reason = f"{len(repo_commits)} commit{'' if len(repo_commits)==1 else 's'} in {goal.get('repo','')}"

    # Soft progress estimate — weighted toward goal-matched commits.
    progress = min(100, len(matched) * 25 + min(len(repo_commits), 4) * 10)

    return {
        **goal,
        "signal":          signal,
        "reason":          reason,
        "progress":        progress,
        "repo_commits":    len(repo_commits),
        "matched_commits": len(matched),
        "days_left":       days_left,
        "days_elapsed":    days_elapsed,
    }


def goals_with_progress(goals: list[dict], commits: list[dict]) -> list[dict]:
    """Enrich a list of goals with progress signals."""
    return [goal_progress(g, commits) for g in goals]
