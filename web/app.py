"""
Flask web dashboard — opens in browser via `gitmind --web`
Clean, simple, works on any device on localhost.
"""
from flask import Flask, render_template_string, jsonify, request
from agent import database as db, github_client as gh, ai
from agent.config import load
from datetime import date

app = Flask(__name__)

HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GitMind ⚡</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0d1117; color: #e6edf3; min-height: 100vh; }
  .header { background: #161b22; border-bottom: 1px solid #30363d; padding: 16px 32px; display: flex; align-items: center; gap: 12px; }
  .header h1 { font-size: 20px; color: #58a6ff; }
  .header span { color: #8b949e; font-size: 13px; }
  .container { max-width: 1100px; margin: 0 auto; padding: 24px 32px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 20px; }
  .card .value { font-size: 36px; font-weight: 800; color: #58a6ff; }
  .card .label { color: #8b949e; font-size: 13px; margin-top: 4px; }
  .section { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 20px; margin-bottom: 20px; }
  .section h2 { font-size: 14px; color: #8b949e; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 16px; }
  .commit { padding: 10px 0; border-bottom: 1px solid #21262d; display: flex; gap: 14px; align-items: flex-start; }
  .commit:last-child { border-bottom: none; }
  .dot { width: 8px; height: 8px; background: #3fb950; border-radius: 50%; margin-top: 5px; flex-shrink: 0; }
  .commit-msg { font-size: 14px; }
  .commit-meta { font-size: 12px; color: #8b949e; margin-top: 3px; }
  .commit-repo { color: #58a6ff; }
  .cal { display: flex; flex-wrap: wrap; gap: 4px; }
  .cal-day { width: 14px; height: 14px; border-radius: 3px; }
  .cal-committed { background: #3fb950; }
  .cal-skipped    { background: #f78166; }
  .cal-pending    { background: #d29922; }
  .cal-no_data    { background: #21262d; }
  .ask-box { display: flex; gap: 10px; margin-bottom: 16px; }
  .ask-box input { flex: 1; background: #0d1117; border: 1px solid #30363d; border-radius: 8px; padding: 10px 14px; color: #e6edf3; font-size: 14px; font-family: inherit; }
  .ask-box button { background: #238636; border: none; border-radius: 8px; padding: 10px 20px; color: white; cursor: pointer; font-size: 14px; font-weight: 600; }
  .ask-box button:hover { background: #2ea043; }
  #ai-response { background: #0d1117; border-radius: 8px; padding: 16px; white-space: pre-wrap; line-height: 1.7; font-size: 14px; display: none; }
  .goal { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #21262d; }
  .goal:last-child { border-bottom: none; }
  .goal-desc { font-size: 14px; }
  .goal-repo { font-size: 12px; color: #58a6ff; }
  .goal-date { font-size: 12px; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 11px; }
  .badge-green { background: rgba(63,185,80,.15); color: #3fb950; border: 1px solid rgba(63,185,80,.3); }
  .badge-yellow { background: rgba(210,153,34,.15); color: #d29922; border: 1px solid rgba(210,153,34,.3); }
  .badge-red { background: rgba(247,129,102,.15); color: #f78166; border: 1px solid rgba(247,129,102,.3); }
  .sprint-box { background: rgba(210,153,34,.08); border: 1px solid rgba(210,153,34,.3); border-radius: 8px; padding: 14px; }
  .loading { color: #8b949e; font-style: italic; }
  @media (max-width: 600px) { .container { padding: 16px; } .grid { grid-template-columns: 1fr 1fr; } }
</style>
</head>
<body>
<div class="header">
  <span style="font-size:24px">⚡</span>
  <h1>GitMind</h1>
  <span id="username-label">Loading...</span>
  <span style="margin-left:auto; color:#8b949e; font-size:12px" id="last-updated"></span>
</div>
<div class="container">
  <div class="grid" id="stats-grid">
    <div class="card"><div class="value" id="s-commits">—</div><div class="label">Commits this week</div></div>
    <div class="card"><div class="value" id="s-streak" style="color:#ffa657">—</div><div class="label">Day streak 🔥</div></div>
    <div class="card"><div class="value" id="s-repos" style="color:#3fb950">—</div><div class="label">Active repos</div></div>
    <div class="card"><div class="value" id="s-files" style="color:#d2a8ff">—</div><div class="label">Files changed</div></div>
  </div>

  <div class="section" id="sprint-section" style="display:none">
    <h2>🏃 Active Sprint</h2>
    <div class="sprint-box" id="sprint-content"></div>
  </div>

  <div class="section">
    <h2>🤖 Ask Anything</h2>
    <div class="ask-box">
      <input type="text" id="ask-input" placeholder="e.g. What did I work on last week? / What should I do next?" onkeydown="if(event.key==='Enter')askAI()">
      <button onclick="askAI()">Ask →</button>
    </div>
    <div id="ai-response"></div>
    <div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:10px" id="quick-q">
      <button onclick="quickAsk('What did I do last week?')" style="background:#21262d;border:1px solid #30363d;border-radius:6px;padding:6px 12px;color:#c9d1d9;cursor:pointer;font-size:12px">📅 Last week</button>
      <button onclick="quickAsk('What should I work on next?')" style="background:#21262d;border:1px solid #30363d;border-radius:6px;padding:6px 12px;color:#c9d1d9;cursor:pointer;font-size:12px">🎯 Next tasks</button>
      <button onclick="quickAsk('Which repo needs the most attention?')" style="background:#21262d;border:1px solid #30363d;border-radius:6px;padding:6px 12px;color:#c9d1d9;cursor:pointer;font-size:12px">🔥 Focus area</button>
      <button onclick="quickAsk('Analyze my productivity patterns')" style="background:#21262d;border:1px solid #30363d;border-radius:6px;padding:6px 12px;color:#c9d1d9;cursor:pointer;font-size:12px">📊 Productivity</button>
    </div>
  </div>

  <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px">
    <div class="section">
      <h2>💬 Recent Commits</h2>
      <div id="commits-list"><div class="loading">Loading...</div></div>
    </div>
    <div class="section">
      <h2>📅 Activity Calendar</h2>
      <div class="cal" id="cal-grid"></div>
      <div style="margin-top:12px; font-size:12px; color:#8b949e; display:flex; gap:12px">
        <span><span style="display:inline-block;width:10px;height:10px;background:#3fb950;border-radius:2px;margin-right:4px"></span>Committed</span>
        <span><span style="display:inline-block;width:10px;height:10px;background:#f78166;border-radius:2px;margin-right:4px"></span>Skipped</span>
        <span><span style="display:inline-block;width:10px;height:10px;background:#21262d;border-radius:2px;margin-right:4px"></span>No data</span>
      </div>
    </div>
  </div>

  <div class="section">
    <h2>🎯 Active Goals</h2>
    <div id="goals-list"><div class="loading">Loading...</div></div>
  </div>
</div>

<script>
async function load() {
  const r = await fetch('/api/dashboard');
  const d = await r.json();

  document.getElementById('username-label').textContent = '@' + (d.username || '');
  document.getElementById('last-updated').textContent = 'Updated: ' + new Date().toLocaleTimeString();

  // Stats
  document.getElementById('s-commits').textContent = d.stats.commits;
  document.getElementById('s-streak').textContent  = d.stats.streak;
  document.getElementById('s-repos').textContent   = d.stats.repos;
  document.getElementById('s-files').textContent   = d.stats.files;

  // Sprint
  if (d.sprint) {
    document.getElementById('sprint-section').style.display = '';
    document.getElementById('sprint-content').innerHTML =
      '<strong>' + d.sprint.goal + '</strong><br><span style="color:#8b949e;font-size:13px">Ends ' + d.sprint.end_date + ' (' + d.sprint.days_left + ' days left)</span>';
  }

  // Commits
  const cl = document.getElementById('commits-list');
  if (d.commits.length === 0) { cl.innerHTML = '<div style="color:#8b949e">No commits in the last 7 days.</div>'; }
  else {
    cl.innerHTML = d.commits.slice(0,8).map(c =>
      `<div class="commit"><div class="dot"></div><div>
        <div class="commit-msg">${c.message}</div>
        <div class="commit-meta"><span class="commit-repo">${c.repo}</span> · ${c.date}</div>
      </div></div>`
    ).join('');
  }

  // Calendar
  const cg = document.getElementById('cal-grid');
  cg.innerHTML = d.calendar.map(day =>
    `<div class="cal-day cal-${day.status}" title="${day.date}: ${day.status}"></div>`
  ).join('');

  // Goals
  const gl = document.getElementById('goals-list');
  if (d.goals.length === 0) { gl.innerHTML = '<div style="color:#8b949e">No active goals. Add one in the terminal!</div>'; }
  else {
    gl.innerHTML = d.goals.map(g => {
      const days = Math.ceil((new Date(g.deadline) - new Date()) / 86400000);
      const badge = days <= 3 ? 'badge-red' : days <= 7 ? 'badge-yellow' : 'badge-green';
      return `<div class="goal">
        <div><div class="goal-desc">${g.description}</div><div class="goal-repo">${g.repo}</div></div>
        <span class="badge ${badge}">${days}d left</span>
      </div>`;
    }).join('');
  }
}

async function askAI() {
  const q = document.getElementById('ask-input').value.trim();
  if (!q) return;
  const box = document.getElementById('ai-response');
  box.style.display = 'block';
  box.textContent = '⏳ Thinking...';
  const r = await fetch('/api/ask', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({question: q}) });
  const d = await r.json();
  box.textContent = d.answer;
}

function quickAsk(q) {
  document.getElementById('ask-input').value = q;
  askAI();
}

load();
setInterval(load, 60000);
</script>
</body>
</html>'''

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/dashboard")
def dashboard():
    cfg = load()
    commits    = gh.fetch_all_recent(7)
    file_stats = {}
    try:
        file_stats = gh.get_file_stats(7)
    except Exception:
        pass

    stats_db = db.get_stats()
    sprint   = db.get_active_sprint()
    goals    = db.get_active_goals()
    calendar = db.get_calendar(35)

    repos = list(set(c["repo"] for c in commits))

    sprint_data = None
    if sprint:
        days_left = (date.fromisoformat(sprint["end_date"]) - date.today()).days
        sprint_data = {**sprint, "days_left": days_left}

    return jsonify({
        "username": cfg.get("github_username", ""),
        "stats": {
            "commits": len(commits),
            "streak":  stats_db["streak"],
            "repos":   len(repos),
            "files":   sum(s["count"] for s in file_stats.values()),
        },
        "commits":  commits[:15],
        "calendar": calendar,
        "goals":    goals,
        "sprint":   sprint_data,
    })

@app.route("/api/ask", methods=["POST"])
def ask():
    data     = request.get_json()
    question = data.get("question", "")
    commits  = gh.fetch_all_recent(7)
    try:
        file_stats = gh.get_file_stats(7)
    except Exception:
        file_stats = {}
    answer = ai.answer_question(question, commits, file_stats)
    return jsonify({"answer": answer})

def run_web(port: int = 7123):
    import logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)  # silence Flask logs
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
