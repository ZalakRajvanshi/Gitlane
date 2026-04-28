"""
Flask web dashboard — opens in browser via `gitmind --web`
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

  .header { background: #161b22; border-bottom: 1px solid #30363d; padding: 14px 32px; display: flex; align-items: center; gap: 12px; }
  .header h1 { font-size: 18px; font-weight: 700; color: #58a6ff; }
  .header .user { color: #8b949e; font-size: 13px; }
  .header .updated { margin-left: auto; color: #484f58; font-size: 12px; }
  .header .dot-live { width: 7px; height: 7px; background: #3fb950; border-radius: 50%; display: inline-block; margin-right: 5px; animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }

  .container { max-width: 1140px; margin: 0 auto; padding: 24px 32px; }

  .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 22px; }
  .stat-card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 18px 20px; }
  .stat-card .val { font-size: 32px; font-weight: 800; line-height: 1; }
  .stat-card .lbl { color: #8b949e; font-size: 12px; margin-top: 6px; text-transform: uppercase; letter-spacing: .05em; }
  .stat-card .sub { color: #484f58; font-size: 11px; margin-top: 3px; }

  .row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-bottom: 18px; }
  .section { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 20px; margin-bottom: 18px; }
  .section-title { font-size: 12px; color: #8b949e; text-transform: uppercase; letter-spacing: .07em; font-weight: 600; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }

  /* Commits */
  .commit-item { display: flex; gap: 12px; padding: 10px 0; border-bottom: 1px solid #21262d; align-items: flex-start; }
  .commit-item:last-child { border-bottom: none; }
  .commit-dot { width: 8px; height: 8px; background: #3fb950; border-radius: 50%; margin-top: 5px; flex-shrink: 0; }
  .commit-msg { font-size: 14px; color: #e6edf3; line-height: 1.4; }
  .commit-meta { font-size: 12px; color: #8b949e; margin-top: 3px; }
  .commit-repo { color: #58a6ff; font-weight: 500; }
  .commit-sha { background: #21262d; padding: 1px 6px; border-radius: 4px; font-family: monospace; font-size: 11px; }
  .empty-state { color: #484f58; font-size: 13px; padding: 12px 0; text-align: center; }

  /* Calendar */
  .cal-header { display: grid; grid-template-columns: repeat(7, 1fr); gap: 3px; margin-bottom: 4px; }
  .cal-header span { font-size: 10px; color: #484f58; text-align: center; }
  .cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 3px; }
  .cal-day { aspect-ratio: 1; border-radius: 3px; cursor: default; position: relative; }
  .cal-day:hover .cal-tooltip { display: block; }
  .cal-committed { background: #3fb950; }
  .cal-skipped    { background: #f78166; }
  .cal-pending    { background: #d29922; }
  .cal-no_data    { background: #21262d; }
  .cal-today      { outline: 2px solid #58a6ff; outline-offset: 1px; }
  .cal-tooltip { display: none; position: absolute; bottom: calc(100% + 6px); left: 50%; transform: translateX(-50%);
    background: #1c2128; border: 1px solid #30363d; border-radius: 6px; padding: 5px 9px;
    font-size: 11px; white-space: nowrap; z-index: 10; color: #e6edf3; pointer-events: none; }
  .cal-legend { display: flex; gap: 14px; margin-top: 12px; flex-wrap: wrap; }
  .cal-legend span { font-size: 11px; color: #8b949e; display: flex; align-items: center; gap: 5px; }
  .cal-legend i { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }

  /* Goals */
  .goal-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #21262d; }
  .goal-item:last-child { border-bottom: none; }
  .goal-desc { font-size: 14px; }
  .goal-repo { font-size: 12px; color: #58a6ff; margin-top: 2px; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }
  .badge-green  { background: rgba(63,185,80,.12);  color: #3fb950; border: 1px solid rgba(63,185,80,.25); }
  .badge-yellow { background: rgba(210,153,34,.12); color: #d29922; border: 1px solid rgba(210,153,34,.25); }
  .badge-red    { background: rgba(247,129,102,.12);color: #f78166; border: 1px solid rgba(247,129,102,.25); }

  /* Sprint */
  .sprint-box { background: rgba(210,153,34,.07); border: 1px solid rgba(210,153,34,.25); border-radius: 8px; padding: 14px 16px; }
  .sprint-goal { font-size: 15px; font-weight: 600; margin-bottom: 6px; }
  .sprint-meta { font-size: 12px; color: #8b949e; }
  .sprint-bar-wrap { background: #21262d; border-radius: 4px; height: 5px; margin-top: 10px; overflow: hidden; }
  .sprint-bar { background: #d29922; height: 100%; border-radius: 4px; transition: width .5s; }

  /* Ask AI */
  .ask-row { display: flex; gap: 10px; margin-bottom: 14px; }
  .ask-row input { flex: 1; background: #0d1117; border: 1px solid #30363d; border-radius: 8px; padding: 10px 14px; color: #e6edf3; font-size: 14px; font-family: inherit; outline: none; }
  .ask-row input:focus { border-color: #58a6ff; }
  .ask-row button { background: #238636; border: none; border-radius: 8px; padding: 10px 20px; color: white; cursor: pointer; font-size: 14px; font-weight: 600; white-space: nowrap; }
  .ask-row button:hover { background: #2ea043; }
  .quick-btns { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
  .quick-btn { background: #21262d; border: 1px solid #30363d; border-radius: 6px; padding: 6px 12px; color: #c9d1d9; cursor: pointer; font-size: 12px; font-family: inherit; }
  .quick-btn:hover { border-color: #58a6ff; color: #58a6ff; }
  #ai-response { background: #0d1117; border: 1px solid #30363d; border-radius: 8px; padding: 16px; white-space: pre-wrap; line-height: 1.75; font-size: 14px; display: none; color: #e6edf3; }

  .loading-shimmer { background: linear-gradient(90deg, #21262d 25%, #2d333b 50%, #21262d 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; border-radius: 6px; height: 14px; margin: 6px 0; }
  @keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }

  @media (max-width: 768px) {
    .stats-grid { grid-template-columns: 1fr 1fr; }
    .row2 { grid-template-columns: 1fr; }
    .container { padding: 16px; }
  }
</style>
</head>
<body>
<div class="header">
  <span style="font-size:22px">⚡</span>
  <h1>GitMind</h1>
  <span class="user" id="username-label"></span>
  <span class="updated"><span class="dot-live"></span><span id="last-updated">Loading...</span></span>
</div>

<div class="container">

  <!-- Stats -->
  <div class="stats-grid">
    <div class="stat-card">
      <div class="val" id="s-commits" style="color:#58a6ff">—</div>
      <div class="lbl">Commits this week</div>
      <div class="sub" id="s-commits-sub"></div>
    </div>
    <div class="stat-card">
      <div class="val" id="s-streak" style="color:#ffa657">—</div>
      <div class="lbl">Day streak 🔥</div>
      <div class="sub" id="s-streak-sub"></div>
    </div>
    <div class="stat-card">
      <div class="val" id="s-repos" style="color:#3fb950">—</div>
      <div class="lbl">Active repos</div>
      <div class="sub" id="s-repos-sub"></div>
    </div>
    <div class="stat-card">
      <div class="val" id="s-files" style="color:#d2a8ff">—</div>
      <div class="lbl">Files changed</div>
      <div class="sub" id="s-files-sub"></div>
    </div>
  </div>

  <!-- Sprint (shown if active) -->
  <div class="section" id="sprint-section" style="display:none">
    <div class="section-title">🏃 Active Sprint</div>
    <div class="sprint-box">
      <div class="sprint-goal" id="sprint-goal"></div>
      <div class="sprint-meta" id="sprint-meta"></div>
      <div class="sprint-bar-wrap"><div class="sprint-bar" id="sprint-bar" style="width:0%"></div></div>
    </div>
  </div>

  <!-- Ask AI -->
  <div class="section">
    <div class="section-title">🤖 Ask AI About Your Work</div>
    <div class="ask-row">
      <input type="text" id="ask-input" placeholder="e.g. What did I work on this week? What should I focus on next?" onkeydown="if(event.key==='Enter')askAI()">
      <button onclick="askAI()">Ask →</button>
    </div>
    <div class="quick-btns">
      <button class="quick-btn" onclick="quickAsk('Summarize what I worked on this week')">📅 This week</button>
      <button class="quick-btn" onclick="quickAsk('What should I work on next?')">🎯 Next tasks</button>
      <button class="quick-btn" onclick="quickAsk('Which repo needs the most attention right now?')">🔥 Focus area</button>
      <button class="quick-btn" onclick="quickAsk('Analyze my productivity patterns and when I code most')">📊 Productivity</button>
      <button class="quick-btn" onclick="quickAsk('Are there any repos I have been neglecting?')">⚠️ Stalled repos</button>
    </div>
    <div id="ai-response"></div>
  </div>

  <div class="row2">
    <!-- Commits -->
    <div class="section">
      <div class="section-title">💬 Recent Commits <span style="margin-left:auto;font-size:11px;color:#484f58" id="commits-count"></span></div>
      <div id="commits-list"><div class="loading-shimmer"></div><div class="loading-shimmer" style="width:70%"></div><div class="loading-shimmer" style="width:85%"></div></div>
    </div>

    <!-- Calendar -->
    <div class="section">
      <div class="section-title">📅 Activity — Last 35 Days</div>
      <div class="cal-header">
        <span>Sun</span><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span>
      </div>
      <div class="cal-grid" id="cal-grid"></div>
      <div class="cal-legend">
        <span><i style="background:#3fb950"></i> Committed</span>
        <span><i style="background:#f78166"></i> Skipped</span>
        <span><i style="background:#d29922"></i> Pending</span>
        <span><i style="background:#21262d"></i> No data</span>
      </div>
      <div style="margin-top:12px;font-size:12px;color:#8b949e" id="cal-summary"></div>
    </div>
  </div>

  <!-- Goals -->
  <div class="section">
    <div class="section-title">🎯 Active Goals</div>
    <div id="goals-list"><div class="loading-shimmer" style="width:60%"></div></div>
  </div>

</div>

<script>
const today = new Date().toISOString().split('T')[0];

async function loadDashboard() {
  let d;
  try {
    const r = await fetch('/api/dashboard');
    d = await r.json();
  } catch(e) {
    document.getElementById('last-updated').textContent = 'Connection error — retrying...';
    return;
  }

  document.getElementById('username-label').textContent = d.username ? '@' + d.username : '';
  document.getElementById('last-updated').textContent = 'Updated ' + new Date().toLocaleTimeString();

  // Stats
  document.getElementById('s-commits').textContent = d.stats.commits;
  document.getElementById('s-commits-sub').textContent = 'past 7 days';
  document.getElementById('s-streak').textContent = d.stats.streak;
  document.getElementById('s-streak-sub').textContent = d.stats.streak === 1 ? 'day' : 'days in a row';
  document.getElementById('s-repos').textContent = d.stats.repos;
  document.getElementById('s-repos-sub').textContent = d.stats.repo_names ? d.stats.repo_names.slice(0,2).join(', ') : '';
  document.getElementById('s-files').textContent = d.stats.files;
  document.getElementById('s-files-sub').textContent = 'unique files';

  // Sprint
  if (d.sprint) {
    document.getElementById('sprint-section').style.display = '';
    document.getElementById('sprint-goal').textContent = d.sprint.goal;
    const dl = d.sprint.days_left;
    document.getElementById('sprint-meta').textContent =
      dl < 0 ? `Ended ${Math.abs(dl)} day(s) ago — ${d.sprint.end_date}` :
      dl === 0 ? `Ends today — ${d.sprint.end_date}` :
      `${dl} day(s) left — ends ${d.sprint.end_date}`;
    const pct = Math.max(5, Math.min(100, 100 - (dl / d.sprint.total_days * 100)));
    document.getElementById('sprint-bar').style.width = pct + '%';
  }

  // Commits
  const cl = document.getElementById('commits-list');
  document.getElementById('commits-count').textContent = d.commits.length ? d.commits.length + ' commits' : '';
  if (!d.commits.length) {
    cl.innerHTML = '<div class="empty-state">No commits found in the last 7 days.<br><span style="font-size:11px">Make sure your GitHub username and token are set correctly.</span></div>';
  } else {
    cl.innerHTML = d.commits.slice(0, 10).map(c => `
      <div class="commit-item">
        <div class="commit-dot"></div>
        <div>
          <div class="commit-msg">${escHtml(c.message)}</div>
          <div class="commit-meta">
            <span class="commit-repo">${escHtml(c.repo)}</span>
            &nbsp;·&nbsp; ${c.date}
            &nbsp;·&nbsp; <span class="commit-sha">${c.sha}</span>
          </div>
        </div>
      </div>`).join('');
  }

  // Calendar — align to week start (Sunday)
  const cg = document.getElementById('cal-grid');
  const days = d.calendar;
  // Pad start so first day aligns to correct weekday
  const firstDay = new Date(days[0].date + 'T00:00:00');
  const startPad = firstDay.getDay(); // 0=Sun
  let html = '';
  for (let i = 0; i < startPad; i++) html += '<div></div>';
  days.forEach(day => {
    const isToday = day.date === today;
    const label = day.status === 'no_data' ? 'No activity' :
                  day.status.charAt(0).toUpperCase() + day.status.slice(1);
    html += `<div class="cal-day cal-${day.status}${isToday ? ' cal-today' : ''}" title="${day.date}: ${label}">
      <div class="cal-tooltip">${day.date}<br>${label}${day.commit_msg ? '<br><em>' + escHtml(day.commit_msg.slice(0,40)) + '</em>' : ''}</div>
    </div>`;
  });
  cg.innerHTML = html;

  // Calendar summary
  const committed = days.filter(d => d.status === 'committed').length;
  const skipped   = days.filter(d => d.status === 'skipped').length;
  const noData    = days.filter(d => d.status === 'no_data').length;
  document.getElementById('cal-summary').textContent =
    `${committed} committed · ${skipped} skipped · ${noData} no data (last 35 days)`;

  // Goals
  const gl = document.getElementById('goals-list');
  if (!d.goals.length) {
    gl.innerHTML = '<div class="empty-state">No active goals. Add one via the terminal menu.</div>';
  } else {
    gl.innerHTML = d.goals.map(g => {
      const ms   = new Date(g.deadline + 'T00:00:00') - new Date();
      const days = Math.ceil(ms / 86400000);
      const cls  = days <= 3 ? 'badge-red' : days <= 7 ? 'badge-yellow' : 'badge-green';
      const lbl  = days < 0 ? `${Math.abs(days)}d overdue` : days === 0 ? 'Due today' : `${days}d left`;
      return `<div class="goal-item">
        <div>
          <div class="goal-desc">${escHtml(g.description)}</div>
          <div class="goal-repo">${escHtml(g.repo)} · due ${g.deadline}</div>
        </div>
        <span class="badge ${cls}">${lbl}</span>
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
  try {
    const r = await fetch('/api/ask', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({question: q})
    });
    const d = await r.json();
    box.textContent = d.answer;
  } catch(e) {
    box.textContent = '⚠️ Could not reach the server.';
  }
}

function quickAsk(q) {
  document.getElementById('ask-input').value = q;
  askAI();
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

loadDashboard();
setInterval(loadDashboard, 120000);
</script>
</body>
</html>'''

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/dashboard")
def dashboard():
    cfg        = load()
    commits    = gh.fetch_all_recent(7, use_cache=False)
    file_stats = {}
    try:
        file_stats = gh.get_file_stats(7)
    except Exception:
        pass

    stats_db = db.get_stats()
    sprint   = db.get_active_sprint()
    goals    = db.get_active_goals()
    calendar = db.get_calendar(35)
    repos    = list(set(c["repo"] for c in commits))

    sprint_data = None
    if sprint:
        from datetime import datetime, timedelta
        start      = date.fromisoformat(sprint["start_date"])
        end        = date.fromisoformat(sprint["end_date"])
        total_days = max(1, (end - start).days)
        days_left  = (end - date.today()).days
        sprint_data = {**sprint, "days_left": days_left, "total_days": total_days}

    return jsonify({
        "username": cfg.get("github_username", ""),
        "stats": {
            "commits":    len(commits),
            "streak":     stats_db["streak"],
            "repos":      len(repos),
            "repo_names": repos[:4],
            "files":      sum(s["count"] for s in file_stats.values()),
        },
        "commits":  commits[:15],
        "calendar": calendar,
        "goals":    goals,
        "sprint":   sprint_data,
    })

@app.route("/api/ask", methods=["POST"])
def ask():
    data       = request.get_json()
    question   = data.get("question", "")
    commits    = gh.fetch_all_recent(7, use_cache=True)
    file_stats = {}
    try:
        file_stats = gh.get_file_stats(7)
    except Exception:
        pass
    answer = ai.answer_question(question, commits, file_stats)
    return jsonify({"answer": answer})

def run_web(port: int = 7123):
    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
