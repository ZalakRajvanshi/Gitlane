"""All AI/LLM calls — Groq with persistent memory context."""
from groq import Groq
from agent.config import groq_key, load
from agent import database as db

def _client():
    return Groq(api_key=groq_key())

def _chat(system: str, user: str, max_tokens: int = 1024) -> str:
    cfg = load()
    model = cfg.get("groq_model", "llama3-70b-8192")
    try:
        key = groq_key()  # call outside inner try so errors surface clearly
        client = Groq(api_key=key)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            max_tokens=max_tokens,
            temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️  AI error: {e}"

def _memory_context() -> str:
    mem = db.get_all_memory()
    if not mem:
        return ""
    lines = [f"  {k}: {v}" for k, v in mem.items()]
    return "Known context about this developer:\n" + "\n".join(lines)

def _commits_str(commits: list[dict], n: int = 25) -> str:
    return "\n".join(
        f"  [{c['repo']}] {c['message']}  ({c['date']})"
        for c in commits[:n]
    ) or "  No commits found."

def _files_str(file_stats: dict, n: int = 10) -> str:
    top = sorted(file_stats.items(), key=lambda x: x[1]["count"], reverse=True)[:n]
    return "\n".join(
        f"  {f} — changed {s['count']}x (+{s['additions']}/-{s['deletions']} lines) [{s['repo']}]"
        for f, s in top
    ) or "  No file data."

def _base_system() -> str:
    cfg = load()
    username = cfg.get("github_username", "the developer")
    mem = _memory_context()
    return f"""You are GitMind, a personal GitHub work assistant for @{username}.
You help developers track their work, stay focused, and grow.
Be friendly, concise, and specific. Use plain text. Avoid jargon.
Never say "I don't have access" — work with what you know.
{mem}"""

# ── PUBLIC FUNCTIONS ───────────────────────────────────────────

def summarize_week(commits: list[dict], file_stats: dict) -> str:
    return _chat(
        _base_system(),
        f"""Summarize this developer's work from the past 7 days in 150 words.
Cover: what they built, which projects got focus, any patterns.
End with one specific encouragement.

COMMITS:
{_commits_str(commits)}

TOP CHANGED FILES:
{_files_str(file_stats)}"""
    )

def suggest_next_tasks(commits: list[dict], file_stats: dict) -> str:
    sprint = db.get_active_sprint()
    goals  = db.get_active_goals()
    sprint_ctx = f"\nCurrent sprint goal: {sprint['goal']}" if sprint else ""
    goals_ctx  = "\nActive goals:\n" + "\n".join(f"  - {g['description']} (due {g['deadline']})" for g in goals) if goals else ""

    return _chat(
        _base_system(),
        f"""Suggest 5 specific next tasks based on recent work.
Be concrete — name actual files, features, or fixes.
Number them 1-5. Keep each under 15 words.
{sprint_ctx}{goals_ctx}

RECENT COMMITS:
{_commits_str(commits, 20)}

HOT FILES:
{_files_str(file_stats, 8)}"""
    )

def generate_commit_message(staged_files: list[str], diff: str = "") -> str:
    files_str = "\n".join(f"  {f}" for f in staged_files)
    return _chat(
        "You write conventional git commit messages. Format: type(scope): description. Under 72 chars. Return ONLY the message.",
        f"""Staged files:
{files_str}

Diff summary:
{diff[:800] if diff else 'Not available'}

Write one commit message.""",
        max_tokens=80
    )

def answer_question(question: str, commits: list[dict], file_stats: dict) -> str:
    repos = list(set(c["repo"] for c in commits))
    return _chat(
        _base_system(),
        f"""Answer this question about the developer's work.
Be specific and helpful. Max 200 words.

ACTIVE REPOS: {', '.join(repos)}
RECENT COMMITS:
{_commits_str(commits)}
TOP FILES:
{_files_str(file_stats)}

QUESTION: {question}"""
    )

def generate_sprint_retro(sprint: dict, commits: list[dict]) -> str:
    return _chat(
        _base_system(),
        f"""Write a brief sprint retrospective (100 words).
Cover: what was accomplished, what to improve, one lesson learned.

SPRINT GOAL: {sprint['goal']}
SPRINT DATES: {sprint['start_date']} → {sprint['end_date']}
COMMITS DURING SPRINT:
{_commits_str(commits)}"""
    )

def detect_blockers(commits: list[dict], repos: list[str]) -> str:
    active_repos = list(set(c["repo"] for c in commits))
    stale = [r for r in repos if r not in active_repos]
    if not stale:
        return ""
    return _chat(
        _base_system(),
        f"""These repos haven't had commits in 7+ days: {', '.join(stale[:5])}
Other active repos: {', '.join(active_repos[:5])}

In one sentence per stale repo, suggest why it might be stalled and what to do.
Keep it friendly, not judgmental.""",
        max_tokens=200
    )

def analyze_productivity(calendar_days: list[dict]) -> str:
    lines = "\n".join(
        f"  {d['date']}: {d['status']}" + (f" — {d.get('commit_msg','')[:50]}" if d.get('commit_msg') else "")
        for d in calendar_days[-14:]
    )
    return _chat(
        _base_system(),
        f"""Analyze this developer's activity pattern over the last 2 weeks.
In 80 words: when are they most productive? any patterns? one practical tip.

ACTIVITY:
{lines}"""
    )

def update_memory_from_session(commits: list[dict], file_stats: dict):
    """Extract and persist key facts about the developer from their activity."""
    top_repos = list(set(c["repo"] for c in commits[:15]))
    top_files = sorted(file_stats.items(), key=lambda x: x[1]["count"], reverse=True)[:5]
    langs = [f.split(".")[-1] for f, _ in top_files if "." in f]

    insight = _chat(
        "Extract 2-3 short facts about this developer's work style and focus. JSON format: {\"facts\": [\"...\", \"...\"]}",
        f"Top repos: {top_repos}\nTop files: {[f for f,_ in top_files]}\nLanguages: {set(langs)}",
        max_tokens=150
    )
    try:
        import json
        data = json.loads(insight.replace("```json","").replace("```","").strip())
        for i, fact in enumerate(data.get("facts", [])[:3]):
            db.set_memory(f"fact_{i}", fact)
        db.set_memory("top_repos", ", ".join(top_repos[:4]))
    except Exception:
        pass
