"""
Flask web dashboard — opens in browser via `gitmind --web`
"""
import os
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request
from agent import database as db, github_client as gh, ai
from agent import git_manager as gm
from agent import commit_flow as cf
from agent.config import load, save
from datetime import date

app = Flask(__name__)

HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GitMind ⚡</title>
<style>
  :root {
    --bg:        #0a0e14;
    --bg-card:   #141a23;
    --bg-deep:   #0d1117;
    --bg-soft:   #1c2230;
    --border:    #2a3140;
    --border-hi: #3d465a;
    --text:      #e6edf3;
    --text-dim:  #9aa5b8;
    --text-faint:#5b6477;
    --accent:    #58a6ff;
    --accent-2:  #7c5cff;
    --success:   #3fb950;
    --warn:      #e3b341;
    --danger:    #f85149;
    --orange:    #ffa657;
    --shadow:    0 4px 16px rgba(0,0,0,.35);
    --shadow-lg: 0 16px 48px rgba(0,0,0,.55);
    --radius:    12px;
    --radius-sm: 8px;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; }
  body {
    font-family: -apple-system, 'Segoe UI', system-ui, Roboto, sans-serif;
    background: radial-gradient(ellipse at top, #11161f 0%, var(--bg) 60%);
    color: var(--text); min-height: 100vh; -webkit-font-smoothing: antialiased;
    line-height: 1.5;
  }
  ::selection { background: rgba(88,166,255,.25); }
  ::-webkit-scrollbar { width: 10px; height: 10px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: #2a3140; border-radius: 5px; }
  ::-webkit-scrollbar-thumb:hover { background: #3d465a; }

  /* ── Header ─────────────────────────────────────────────── */
  .header {
    background: rgba(20,26,35,.85); backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--border);
    padding: 16px 32px; display: flex; align-items: center; gap: 14px;
    position: sticky; top: 0; z-index: 50;
  }
  .header .logo {
    width: 32px; height: 32px; border-radius: 8px;
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; box-shadow: 0 4px 12px rgba(88,166,255,.3);
  }
  .header h1 {
    font-size: 19px; font-weight: 700;
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -.02em;
  }
  .header .user { color: var(--text-dim); font-size: 13px; font-weight: 500; }
  .header .updated { margin-left: auto; color: var(--text-faint); font-size: 12px; display: flex; align-items: center; gap: 6px; }
  .header .dot-live { width: 7px; height: 7px; background: var(--success); border-radius: 50%; box-shadow: 0 0 8px var(--success); animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1; transform:scale(1)} 50%{opacity:.5; transform:scale(.85)} }

  .container { max-width: 1180px; margin: 0 auto; padding: 28px 32px 60px; }

  /* ── Stats grid ─────────────────────────────────────────── */
  .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 22px; }
  .stat-card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 20px 22px;
    position: relative; overflow: hidden;
    transition: transform .2s, border-color .2s, box-shadow .2s;
  }
  .stat-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: var(--accent-line, var(--accent)); opacity: .8;
  }
  .stat-card:hover { transform: translateY(-2px); border-color: var(--border-hi); box-shadow: var(--shadow); }
  .stat-card .val { font-size: 30px; font-weight: 800; line-height: 1.1; letter-spacing: -.02em; font-variant-numeric: tabular-nums; }
  .stat-card .lbl { color: var(--text-dim); font-size: 11px; margin-top: 8px; text-transform: uppercase; letter-spacing: .08em; font-weight: 600; }
  .stat-card .sub { color: var(--text-faint); font-size: 11px; margin-top: 4px; }
  .stat-card.s-commits { --accent-line: var(--accent); }
  .stat-card.s-streak  { --accent-line: var(--orange); }
  .stat-card.s-repos   { --accent-line: var(--success); }
  .stat-card.s-files   { --accent-line: #d2a8ff; }

  /* ── Sections ────────────────────────────────────────────── */
  .row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-bottom: 18px; }
  .section {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 22px 24px; margin-bottom: 18px;
    transition: border-color .2s;
  }
  .section:hover { border-color: var(--border-hi); }
  .section-title {
    font-size: 11px; color: var(--text-dim); text-transform: uppercase;
    letter-spacing: .09em; font-weight: 700; margin-bottom: 18px;
    display: flex; align-items: center; gap: 8px;
  }

  /* ── Commits list ────────────────────────────────────────── */
  .commit-item { display: flex; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--border); align-items: flex-start; }
  .commit-item:last-child { border-bottom: none; padding-bottom: 0; }
  .commit-item:first-child { padding-top: 0; }
  .commit-dot { width: 8px; height: 8px; background: var(--success); border-radius: 50%; margin-top: 6px; flex-shrink: 0; box-shadow: 0 0 6px rgba(63,185,80,.5); }
  .commit-msg { font-size: 14px; color: var(--text); line-height: 1.45; font-weight: 500; }
  .commit-meta { font-size: 12px; color: var(--text-dim); margin-top: 4px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .commit-repo { color: var(--accent); font-weight: 600; }
  .commit-sha { background: var(--bg-soft); padding: 2px 7px; border-radius: 4px; font-family: 'JetBrains Mono', Consolas, monospace; font-size: 11px; color: var(--text-dim); }
  .empty-state { color: var(--text-faint); font-size: 13px; padding: 18px 0; text-align: center; line-height: 1.6; }

  /* ── Calendar ────────────────────────────────────────────── */
  .cal-header { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; margin-bottom: 6px; }
  .cal-header span { font-size: 10px; color: var(--text-faint); text-align: center; font-weight: 600; letter-spacing: .05em; }
  .cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
  .cal-day { aspect-ratio: 1; border-radius: 4px; cursor: default; position: relative; transition: transform .15s; }
  .cal-day:hover { transform: scale(1.15); z-index: 5; }
  .cal-day:hover .cal-tooltip { display: block; }
  .cal-committed { background: var(--success); box-shadow: 0 0 8px rgba(63,185,80,.35); }
  .cal-skipped    { background: #f78166; }
  .cal-pending    { background: var(--warn); }
  .cal-no_data    { background: var(--bg-soft); }
  .cal-today      { outline: 2px solid var(--accent); outline-offset: 2px; }
  .cal-tooltip {
    display: none; position: absolute; bottom: calc(100% + 8px); left: 50%; transform: translateX(-50%);
    background: #1c2128; border: 1px solid var(--border-hi); border-radius: 6px; padding: 6px 10px;
    font-size: 11px; white-space: nowrap; z-index: 10; color: var(--text);
    pointer-events: none; box-shadow: var(--shadow);
  }
  .cal-legend { display: flex; gap: 16px; margin-top: 14px; flex-wrap: wrap; }
  .cal-legend span { font-size: 11px; color: var(--text-dim); display: flex; align-items: center; gap: 6px; font-weight: 500; }
  .cal-legend i { width: 11px; height: 11px; border-radius: 3px; display: inline-block; }

  /* ── Goals ───────────────────────────────────────────────── */
  .goal-item { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--border); gap: 12px; }
  .goal-item:last-child { border-bottom: none; padding-bottom: 0; }
  .goal-item:first-child { padding-top: 0; }
  .goal-desc { font-size: 14px; font-weight: 500; }
  .goal-repo { font-size: 12px; color: var(--accent); margin-top: 3px; font-weight: 500; }
  .badge { display: inline-block; padding: 4px 11px; border-radius: 20px; font-size: 11px; font-weight: 700; white-space: nowrap; }
  .badge-green  { background: rgba(63,185,80,.15);  color: var(--success); border: 1px solid rgba(63,185,80,.3); }
  .badge-yellow { background: rgba(227,179,65,.15); color: var(--warn); border: 1px solid rgba(227,179,65,.3); }
  .badge-red    { background: rgba(248,81,73,.15);  color: var(--danger); border: 1px solid rgba(248,81,73,.3); }

  /* ── Sprint ──────────────────────────────────────────────── */
  .sprint-box { background: linear-gradient(135deg, rgba(227,179,65,.1), rgba(255,166,87,.05)); border: 1px solid rgba(227,179,65,.3); border-radius: var(--radius-sm); padding: 16px 18px; }
  .sprint-goal { font-size: 15px; font-weight: 600; margin-bottom: 6px; }
  .sprint-meta { font-size: 12px; color: var(--text-dim); }
  .sprint-bar-wrap { background: rgba(0,0,0,.25); border-radius: 4px; height: 6px; margin-top: 12px; overflow: hidden; }
  .sprint-bar { background: linear-gradient(90deg, var(--warn), var(--orange)); height: 100%; border-radius: 4px; transition: width .6s ease; }

  /* ── Ask AI ──────────────────────────────────────────────── */
  .ask-row { display: flex; gap: 10px; margin-bottom: 14px; }
  .ask-row input {
    flex: 1; background: var(--bg-deep); border: 1px solid var(--border);
    border-radius: var(--radius-sm); padding: 12px 16px; color: var(--text);
    font-size: 14px; font-family: inherit; outline: none; transition: border-color .15s, box-shadow .15s;
  }
  .ask-row input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(88,166,255,.12); }
  .ask-row button {
    background: linear-gradient(135deg, #2ea043, var(--success));
    border: none; border-radius: var(--radius-sm); padding: 12px 22px;
    color: white; cursor: pointer; font-size: 14px; font-weight: 600;
    white-space: nowrap; transition: transform .15s, box-shadow .15s;
  }
  .ask-row button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(63,185,80,.35); }
  .quick-btns { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
  .quick-btn {
    background: var(--bg-soft); border: 1px solid var(--border); border-radius: 18px;
    padding: 7px 14px; color: var(--text-dim); cursor: pointer; font-size: 12px;
    font-family: inherit; font-weight: 500; transition: all .15s;
  }
  .quick-btn:hover { border-color: var(--accent); color: var(--accent); background: rgba(88,166,255,.08); }
  #ai-response {
    background: var(--bg-deep); border: 1px solid var(--border); border-radius: var(--radius-sm);
    padding: 18px; white-space: pre-wrap; line-height: 1.75; font-size: 14px;
    display: none; color: var(--text);
  }

  /* ── Loading shimmer ─────────────────────────────────────── */
  .loading-shimmer { background: linear-gradient(90deg, var(--bg-soft) 25%, #2d333b 50%, var(--bg-soft) 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; border-radius: 6px; height: 14px; margin: 8px 0; }
  @keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }

  /* ── Smart Commit launcher ───────────────────────────────── */
  .commit-launcher {
    background:
      radial-gradient(ellipse at top right, rgba(124,92,255,.18), transparent 60%),
      linear-gradient(135deg, rgba(63,185,80,.18), rgba(88,166,255,.12));
    border: 1px solid rgba(63,185,80,.4); border-radius: var(--radius);
    padding: 22px 26px; display: flex; align-items: center; gap: 18px;
    position: relative; overflow: hidden;
    box-shadow: 0 4px 24px rgba(63,185,80,.08);
  }
  .commit-launcher .icon-box {
    width: 48px; height: 48px; border-radius: 12px;
    background: linear-gradient(135deg, var(--success), #2ea043);
    display: flex; align-items: center; justify-content: center;
    font-size: 24px; box-shadow: 0 6px 16px rgba(63,185,80,.4); flex-shrink: 0;
  }
  .commit-launcher .left { flex: 1; }
  .commit-launcher h3 { font-size: 17px; font-weight: 700; margin-bottom: 4px; color: var(--text); letter-spacing: -.01em; }
  .commit-launcher p { font-size: 13px; color: var(--text-dim); line-height: 1.5; }
  .commit-launcher button {
    background: linear-gradient(135deg, #2ea043, var(--success));
    border: none; border-radius: var(--radius-sm); padding: 13px 26px;
    color: white; cursor: pointer; font-size: 14px; font-weight: 700;
    white-space: nowrap; transition: transform .15s, box-shadow .15s;
    box-shadow: 0 4px 14px rgba(63,185,80,.35);
  }
  .commit-launcher button:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(63,185,80,.5); }

  /* ── Wizard modal ────────────────────────────────────────── */
  .wiz-overlay {
    display: none; position: fixed; inset: 0;
    background: rgba(5,8,12,.75); backdrop-filter: blur(6px);
    z-index: 100; padding: 24px; overflow-y: auto;
    animation: fadeIn .2s ease;
  }
  .wiz-overlay.open { display: block; }
  @keyframes fadeIn { from { opacity: 0 } to { opacity: 1 } }
  .wiz-modal {
    max-width: 780px; margin: 24px auto;
    background: var(--bg-card); border: 1px solid var(--border-hi);
    border-radius: 16px; padding: 0; box-shadow: var(--shadow-lg);
    animation: slideUp .25s ease;
  }
  @keyframes slideUp { from { opacity: 0; transform: translateY(16px) } to { opacity: 1; transform: translateY(0) } }
  .wiz-head {
    padding: 20px 26px; border-bottom: 1px solid var(--border);
    display: flex; align-items: center; gap: 12px;
  }
  .wiz-head .ico {
    width: 36px; height: 36px; border-radius: 10px;
    background: linear-gradient(135deg, var(--success), #2ea043);
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; box-shadow: 0 4px 12px rgba(63,185,80,.35);
  }
  .wiz-head h2 { font-size: 17px; color: var(--text); font-weight: 700; flex: 1; letter-spacing: -.01em; }
  .wiz-close {
    background: transparent; border: none; color: var(--text-dim);
    font-size: 22px; cursor: pointer; padding: 0; width: 32px; height: 32px;
    border-radius: 8px; display: flex; align-items: center; justify-content: center;
    transition: all .15s;
  }
  .wiz-close:hover { color: var(--text); background: var(--bg-soft); }

  /* ── Wizard step indicator (numbered circles) ─────────────── */
  .wiz-steps {
    display: flex; align-items: flex-start; justify-content: space-between;
    padding: 22px 32px 18px; background: var(--bg-deep);
    border-bottom: 1px solid var(--border); gap: 4px;
  }
  .wiz-step { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 8px; position: relative; min-width: 0; }
  .wiz-step:not(:last-child)::after {
    content: ''; position: absolute; top: 13px; left: calc(50% + 18px); right: calc(-50% + 18px);
    height: 2px; background: var(--border); transition: background .3s;
  }
  .wiz-step.done:not(:last-child)::after { background: var(--success); }
  .wiz-step .circle {
    width: 28px; height: 28px; border-radius: 50%;
    background: var(--bg-soft); border: 2px solid var(--border);
    color: var(--text-faint); font-size: 12px; font-weight: 700;
    display: flex; align-items: center; justify-content: center;
    transition: all .25s; z-index: 2; position: relative;
  }
  .wiz-step .label { font-size: 10px; color: var(--text-faint); text-transform: uppercase; letter-spacing: .06em; font-weight: 600; text-align: center; max-width: 80px; line-height: 1.2; }
  .wiz-step.active .circle { background: var(--accent); border-color: var(--accent); color: white; box-shadow: 0 0 0 4px rgba(88,166,255,.18); }
  .wiz-step.active .label { color: var(--accent); }
  .wiz-step.done .circle { background: var(--success); border-color: var(--success); color: white; }
  .wiz-step.done .label { color: var(--text-dim); }

  .wiz-body { padding: 28px 30px; min-height: 260px; }
  .wiz-body h3 { font-size: 16px; color: var(--text); margin-bottom: 6px; font-weight: 700; letter-spacing: -.01em; }
  .wiz-body .hint { font-size: 13px; color: var(--text-dim); margin-bottom: 18px; line-height: 1.5; }
  .wiz-body .hint code { background: var(--bg-soft); padding: 2px 6px; border-radius: 4px; font-size: 12px; color: var(--text); }
  .wiz-body label { display: block; font-size: 13px; color: var(--text-dim); margin-bottom: 8px; font-weight: 500; }
  .wiz-body input[type=text], .wiz-body textarea, .wiz-body select {
    width: 100%; background: var(--bg-deep); border: 1px solid var(--border);
    border-radius: var(--radius-sm); padding: 11px 14px; color: var(--text);
    font-size: 14px; font-family: inherit; outline: none; transition: all .15s;
  }
  .wiz-body input[type=text]:focus, .wiz-body textarea:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(88,166,255,.12); }
  .wiz-body textarea { resize: vertical; min-height: 80px; line-height: 1.5; }

  .wiz-foot {
    padding: 18px 26px; border-top: 1px solid var(--border);
    display: flex; justify-content: space-between; gap: 10px;
    background: var(--bg-deep); border-radius: 0 0 16px 16px;
  }
  .wiz-btn {
    background: var(--bg-soft); border: 1px solid var(--border);
    border-radius: var(--radius-sm); padding: 10px 20px;
    color: var(--text-dim); cursor: pointer; font-size: 13px;
    font-family: inherit; font-weight: 600; transition: all .15s;
  }
  .wiz-btn:hover:not(:disabled) { border-color: var(--border-hi); color: var(--text); }
  .wiz-btn-primary {
    background: linear-gradient(135deg, #2ea043, var(--success));
    border-color: transparent; color: white;
    box-shadow: 0 2px 8px rgba(63,185,80,.3);
  }
  .wiz-btn-primary:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(63,185,80,.45); }
  .wiz-btn-danger { background: linear-gradient(135deg, #b62324, var(--danger)); border-color: transparent; color: white; }
  .wiz-btn:disabled { opacity: .45; cursor: not-allowed; }

  /* ── Repo cards in wizard ────────────────────────────────── */
  .repo-card {
    background: var(--bg-deep); border: 1px solid var(--border);
    border-radius: var(--radius-sm); padding: 14px 16px; margin-bottom: 10px;
    cursor: pointer; display: flex; align-items: center; gap: 14px;
    transition: all .15s;
  }
  .repo-card:hover { border-color: var(--border-hi); background: rgba(88,166,255,.04); }
  .repo-card.selected { border-color: var(--accent); background: rgba(88,166,255,.1); box-shadow: 0 0 0 3px rgba(88,166,255,.12); }
  .repo-card .nm { font-weight: 600; font-size: 14px; color: var(--text); }
  .repo-card .pth { font-size: 11px; color: var(--text-faint); margin-top: 3px; font-family: 'JetBrains Mono', Consolas, monospace; }
  .repo-card .tag { font-size: 11px; padding: 3px 10px; border-radius: 12px; font-weight: 600; }
  .tag-github { background: rgba(63,185,80,.15); color: var(--success); border: 1px solid rgba(63,185,80,.35); }
  .tag-local  { background: rgba(227,179,65,.15); color: var(--warn); border: 1px solid rgba(227,179,65,.35); }

  /* ── File list ───────────────────────────────────────────── */
  .file-list {
    background: var(--bg-deep); border: 1px solid var(--border);
    border-radius: var(--radius-sm); padding: 12px 16px; max-height: 200px;
    overflow-y: auto; font-family: 'JetBrains Mono', Consolas, monospace; font-size: 12px;
  }
  .file-list .f { padding: 3px 0; color: var(--text); display: flex; align-items: center; gap: 8px; }
  .file-list .f .x {
    color: var(--success); font-weight: 700; min-width: 14px; text-align: center;
    font-size: 11px;
  }

  /* ── Status pills ────────────────────────────────────────── */
  .status-row { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
  .pill {
    padding: 6px 13px; border-radius: 20px; font-size: 12px;
    background: var(--bg-soft); border: 1px solid var(--border);
    color: var(--text); font-weight: 500;
  }
  .pill .k { color: var(--text-dim); margin-right: 4px; }
  .pill.ok    { color: var(--success); border-color: rgba(63,185,80,.35); background: rgba(63,185,80,.1); }
  .pill.warn  { color: var(--warn); border-color: rgba(227,179,65,.35); background: rgba(227,179,65,.1); }

  /* ── Security findings ───────────────────────────────────── */
  .scan-block { border-radius: var(--radius-sm); padding: 16px; margin-bottom: 12px; }
  .scan-block.danger  { background: rgba(248,81,73,.08); border: 1px solid rgba(248,81,73,.4); }
  .scan-block.warn    { background: rgba(227,179,65,.08); border: 1px solid rgba(227,179,65,.4); }
  .scan-block.ok      { background: rgba(63,185,80,.08); border: 1px solid rgba(63,185,80,.35); }
  .scan-block .title  { font-weight: 700; font-size: 13px; margin-bottom: 10px; display: flex; align-items: center; gap: 6px; }
  .scan-block.danger .title { color: var(--danger); }
  .scan-block.warn .title   { color: var(--warn); }
  .scan-block.ok .title     { color: var(--success); }
  .finding { font-size: 12px; padding: 8px 0; border-top: 1px dashed rgba(255,255,255,.08); line-height: 1.5; }
  .finding:first-of-type { border-top: none; padding-top: 0; }
  .finding code { background: rgba(0,0,0,.25); padding: 2px 5px; border-radius: 3px; font-family: 'JetBrains Mono', Consolas, monospace; }
  .finding .ln { color: var(--text-dim); font-family: 'JetBrains Mono', Consolas, monospace; }
  .finding .arrow { color: var(--warn); margin-top: 4px; }

  .gen-msg {
    background: linear-gradient(135deg, rgba(63,185,80,.1), rgba(88,166,255,.06));
    border: 1px solid rgba(63,185,80,.35); border-radius: var(--radius-sm);
    padding: 16px 18px; margin-bottom: 14px; font-weight: 600; font-size: 14px; color: var(--text);
    line-height: 1.5;
  }

  .wiz-success { text-align: center; padding: 36px 0 16px; }
  .wiz-success .ico { font-size: 56px; margin-bottom: 14px; animation: bounce .5s ease; }
  @keyframes bounce { 0%{transform:scale(.6)} 60%{transform:scale(1.15)} 100%{transform:scale(1)} }
  .wiz-success h3 { font-size: 20px; color: var(--success); margin-bottom: 10px; font-weight: 700; }
  .wiz-success a {
    color: var(--accent); text-decoration: none; word-break: break-all;
    background: var(--bg-soft); padding: 6px 12px; border-radius: 6px;
    display: inline-block; font-size: 13px;
  }
  .wiz-success a:hover { background: var(--bg-deep); text-decoration: underline; }

  .wiz-error {
    background: rgba(248,81,73,.1); border: 1px solid rgba(248,81,73,.4);
    border-radius: var(--radius-sm); padding: 13px 15px; color: var(--danger);
    font-size: 13px; margin-bottom: 12px; line-height: 1.5;
  }

  .radio-row { display: flex; gap: 16px; margin-top: 8px; }
  .radio-row label { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px; color: var(--text); margin: 0; }
  .radio-row input[type=radio] { accent-color: var(--accent); }

  /* ── Responsive ──────────────────────────────────────────── */
  @media (max-width: 768px) {
    .stats-grid { grid-template-columns: 1fr 1fr; }
    .row2 { grid-template-columns: 1fr; }
    .container { padding: 18px; }
    .header { padding: 14px 18px; }
    .commit-launcher { flex-direction: column; text-align: center; align-items: stretch; }
    .commit-launcher button { width: 100%; }
    .wiz-steps { padding: 18px 12px 14px; }
    .wiz-step .label { font-size: 9px; max-width: 60px; }
    .wiz-body { padding: 22px 20px; }
  }
</style>
</head>
<body>
<div class="header">
  <div class="logo">⚡</div>
  <h1>GitMind</h1>
  <span class="user" id="username-label"></span>
  <span class="updated"><span class="dot-live"></span><span id="last-updated">Loading...</span></span>
</div>

<div class="container">

  <!-- Stats -->
  <div class="stats-grid">
    <div class="stat-card s-commits">
      <div class="val" id="s-commits" style="color:#58a6ff">—</div>
      <div class="lbl">Commits this week</div>
      <div class="sub" id="s-commits-sub"></div>
    </div>
    <div class="stat-card s-streak">
      <div class="val" id="s-streak" style="color:#ffa657">—</div>
      <div class="lbl">Day streak 🔥</div>
      <div class="sub" id="s-streak-sub"></div>
    </div>
    <div class="stat-card s-repos">
      <div class="val" id="s-repos" style="color:#3fb950">—</div>
      <div class="lbl">Active repos</div>
      <div class="sub" id="s-repos-sub"></div>
    </div>
    <div class="stat-card s-files">
      <div class="val" id="s-files" style="color:#d2a8ff">—</div>
      <div class="lbl">Files changed</div>
      <div class="sub" id="s-files-sub"></div>
    </div>
  </div>

  <!-- Smart Commit & Deploy launcher -->
  <div style="margin-bottom:18px">
    <div class="commit-launcher">
      <div class="icon-box">🚀</div>
      <div class="left">
        <h3>Smart Commit &amp; Deploy</h3>
        <p>Scan secrets · auto-fix · generate AI message · commit · push (or create new GitHub repo)</p>
      </div>
      <button onclick="wizOpen()">Start →</button>
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

<!-- ── Smart Commit Wizard ─────────────────────────────────── -->
<div class="wiz-overlay" id="wiz-overlay">
  <div class="wiz-modal">
    <div class="wiz-head">
      <div class="ico">🚀</div>
      <h2 id="wiz-title">Smart Commit &amp; Deploy</h2>
      <button class="wiz-close" onclick="wizClose()">×</button>
    </div>
    <div class="wiz-steps" id="wiz-steps">
      <div class="wiz-step"><div class="circle">1</div><div class="label">Repo</div></div>
      <div class="wiz-step"><div class="circle">2</div><div class="label">Review</div></div>
      <div class="wiz-step"><div class="circle">3</div><div class="label">Scan</div></div>
      <div class="wiz-step"><div class="circle">4</div><div class="label">Message</div></div>
      <div class="wiz-step"><div class="circle">5</div><div class="label">Commit</div></div>
      <div class="wiz-step"><div class="circle">6</div><div class="label">Push</div></div>
    </div>
    <div class="wiz-body" id="wiz-body"></div>
    <div class="wiz-foot">
      <button class="wiz-btn" id="wiz-back" onclick="wizBack()" style="visibility:hidden">← Back</button>
      <button class="wiz-btn wiz-btn-primary" id="wiz-next" onclick="wizNext()">Next →</button>
    </div>
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

/* ──────────────────────────────────────────────────────────
   SMART COMMIT WIZARD
   Steps: 1.Repo  2.Changes  3.Scan  4.Message  5.Commit  6.Push
   ────────────────────────────────────────────────────────── */

const wiz = {
  step: 0,
  projectsFolder: '',
  repos: [],
  selectedRepo: null,
  status: null,         // {branch, has_remote, unstaged, gitignore_created}
  scanResult: null,     // {staged, blocked_files, findings}
  finalStaged: [],
  description: '',
  commitMsg: '',
  busy: false,
  pushResult: null
};

function wizOpen() {
  wiz.step = 0;
  document.getElementById('wiz-overlay').classList.add('open');
  wizRender();
}
function wizClose() {
  document.getElementById('wiz-overlay').classList.remove('open');
}
function wizSetBusy(b) {
  wiz.busy = b;
  document.getElementById('wiz-next').disabled = b;
  document.getElementById('wiz-back').disabled = b;
}
function wizSetSteps() {
  const els = document.querySelectorAll('#wiz-steps .wiz-step');
  els.forEach((el, i) => {
    el.classList.remove('active', 'done');
    const circle = el.querySelector('.circle');
    if (i < wiz.step) {
      el.classList.add('done');
      circle.textContent = '✓';
    } else {
      circle.textContent = String(i + 1);
      if (i === wiz.step) el.classList.add('active');
    }
  });
  document.getElementById('wiz-back').style.visibility = wiz.step === 0 ? 'hidden' : 'visible';
}

async function wizRender() {
  wizSetSteps();
  const body = document.getElementById('wiz-body');
  const nextBtn = document.getElementById('wiz-next');
  nextBtn.textContent = 'Next →';
  nextBtn.classList.add('wiz-btn-primary');
  nextBtn.classList.remove('wiz-btn-danger');

  if (wiz.step === 0) await renderStepRepo(body);
  else if (wiz.step === 1) await renderStepChanges(body);
  else if (wiz.step === 2) await renderStepScan(body);
  else if (wiz.step === 3) renderStepMessage(body);
  else if (wiz.step === 4) renderStepCommit(body);
  else if (wiz.step === 5) renderStepPush(body);
}

/* ── STEP 1: PICK REPO ─────────────────────────────────── */
async function renderStepRepo(body) {
  body.innerHTML = '<div class="hint">Loading...</div>';
  let d;
  try {
    const r = await fetch('/api/commit/init');
    d = await r.json();
  } catch (e) {
    body.innerHTML = '<div class="wiz-error">Could not contact backend.</div>';
    return;
  }

  wiz.projectsFolder = d.projects_folder || '';
  wiz.repos = d.repos || [];

  let html = '';
  if (!d.projects_folder || !d.folder_exists) {
    html += `<h3>Where are your projects stored?</h3>
      <p class="hint">Example: <code>C:\\Users\\zalak\\OneDrive\\Desktop\\Projects</code></p>
      <input type="text" id="wiz-folder" value="${escHtml(d.projects_folder || '')}" placeholder="Full folder path">
      <div style="margin-top:10px"><button class="wiz-btn wiz-btn-primary" onclick="wizSaveFolder()">Save folder</button></div>
      ${d.projects_folder && !d.folder_exists ? '<div class="wiz-error" style="margin-top:10px">Saved folder no longer exists.</div>' : ''}`;
    body.innerHTML = html;
    document.getElementById('wiz-next').disabled = true;
    return;
  }

  html += `<h3>Pick a repository</h3>
    <p class="hint">Found ${wiz.repos.length} git repo(s) in <code>${escHtml(wiz.projectsFolder)}</code> · <a href="#" onclick="wizResetFolder();return false" style="color:#58a6ff">change folder</a></p>`;
  if (!wiz.repos.length) {
    html += '<div class="wiz-error">No git repos found in that folder.</div>';
  } else {
    html += wiz.repos.map((r, i) => `
      <div class="repo-card${wiz.selectedRepo && wiz.selectedRepo.path === r.path ? ' selected' : ''}" onclick="wizPickRepo(${i})">
        <div style="flex:1">
          <div class="nm">${escHtml(r.name)}</div>
          <div class="pth">${escHtml(r.path)}</div>
        </div>
        <span class="tag ${r.has_remote ? 'tag-github' : 'tag-local'}">${r.has_remote ? 'GitHub' : 'local only'}</span>
      </div>`).join('');
  }
  body.innerHTML = html;
  document.getElementById('wiz-next').disabled = !wiz.selectedRepo;
}

async function wizSaveFolder() {
  const folder = document.getElementById('wiz-folder').value.trim();
  if (!folder) return;
  wizSetBusy(true);
  const r = await fetch('/api/commit/set-folder', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({folder})
  });
  const d = await r.json();
  wizSetBusy(false);
  if (!d.ok) {
    document.getElementById('wiz-body').insertAdjacentHTML('beforeend',
      `<div class="wiz-error" style="margin-top:10px">${escHtml(d.error)}</div>`);
    return;
  }
  await renderStepRepo(document.getElementById('wiz-body'));
}

async function wizResetFolder() {
  await fetch('/api/commit/clear-folder', {method: 'POST'});
  wiz.selectedRepo = null;
  await renderStepRepo(document.getElementById('wiz-body'));
}

function wizPickRepo(i) {
  wiz.selectedRepo = wiz.repos[i];
  document.querySelectorAll('.repo-card').forEach((el, idx) => {
    el.classList.toggle('selected', idx === i);
  });
  document.getElementById('wiz-next').disabled = false;
}

/* ── STEP 2: REVIEW CHANGES ────────────────────────────── */
async function renderStepChanges(body) {
  body.innerHTML = '<div class="hint">Reading repo status...</div>';
  const r = await fetch('/api/commit/repo-status', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({repo_path: wiz.selectedRepo.path})
  });
  const d = await r.json();
  if (!d.ok) {
    body.innerHTML = `<div class="wiz-error">${escHtml(d.error)}</div>`;
    document.getElementById('wiz-next').disabled = true;
    return;
  }
  wiz.status = d;

  let html = `<h3>${escHtml(wiz.selectedRepo.name)}</h3>
    <div class="status-row">
      <span class="pill"><span class="k">Branch:</span> <b>${escHtml(d.branch)}</b></span>
      <span class="pill ${d.has_remote ? 'ok' : 'warn'}">${d.has_remote ? '✓ GitHub connected' : '⚠ no GitHub remote'}</span>
      <span class="pill ${d.gitignore_created ? 'ok' : ''}">${d.gitignore_created ? '✓ .gitignore created' : '.gitignore exists'}</span>
    </div>`;

  if (!d.unstaged.length) {
    html += '<div class="wiz-error">No changes to commit.</div>';
    body.innerHTML = html;
    document.getElementById('wiz-next').disabled = true;
    return;
  }

  html += `<h3 style="margin-top:8px">Changed files (${d.unstaged.length})</h3>
    <p class="hint">All of these will be staged with <code>git add -A</code></p>
    <div class="file-list">${d.unstaged.map(f =>
      `<div class="f"><span class="x">M</span>${escHtml(f)}</div>`
    ).join('')}</div>`;
  body.innerHTML = html;
  document.getElementById('wiz-next').textContent = 'Stage & scan →';
  document.getElementById('wiz-next').disabled = false;
}

/* ── STEP 3: SECURITY SCAN ─────────────────────────────── */
async function renderStepScan(body) {
  body.innerHTML = '<div class="hint">Staging files and scanning for secrets...</div>';
  const r = await fetch('/api/commit/stage-and-scan', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({repo_path: wiz.selectedRepo.path})
  });
  const d = await r.json();
  if (!d.ok) {
    body.innerHTML = `<div class="wiz-error">${escHtml(d.error)}</div>`;
    document.getElementById('wiz-next').disabled = true;
    return;
  }
  wiz.scanResult = d;
  renderScanUI(body);
}

function renderScanUI(body) {
  const d = wiz.scanResult;
  let html = '';

  if (d.blocked_files && d.blocked_files.length) {
    html += `<div class="scan-block danger">
      <div class="title">⛔ Blocked files (auto-removed from commit + added to .gitignore)</div>
      ${d.blocked_files.map(f => `<div class="finding">🚨 ${escHtml(f)}</div>`).join('')}
    </div>`;
  }

  const findingsKeys = Object.keys(d.findings || {});
  if (findingsKeys.length) {
    html += findingsKeys.map(fname => `
      <div class="scan-block warn">
        <div class="title">⚠️ Sensitive data in ${escHtml(fname)}</div>
        ${d.findings[fname].map(f => `
          <div class="finding">
            <div><span class="ln">Line ${f.line_num}:</span> <code>${escHtml(f.line.slice(0,90))}</code></div>
            <div class="arrow">→ Will move to .env as <b>${escHtml(f.env_key)}</b></div>
          </div>`).join('')}
      </div>`).join('');
    html += `<div style="display:flex;gap:10px;margin-top:8px">
      <button class="wiz-btn wiz-btn-primary" onclick="wizDoAutofix()">✨ Auto-fix (move to .env)</button>
      <button class="wiz-btn" onclick="wizSkipAutofix()">Skip (unstage these files)</button>
    </div>`;
    body.innerHTML = html;
    document.getElementById('wiz-next').disabled = true;
    return;
  }

  if (!d.staged || !d.staged.length) {
    html += '<div class="wiz-error">Nothing left to commit after security scan.</div>';
    body.innerHTML = html;
    document.getElementById('wiz-next').disabled = true;
    return;
  }

  html += `<div class="scan-block ok">
    <div class="title">✅ All clear — no secrets detected</div>
    <div style="font-size:12px;color:#8b949e">${d.staged.length} file(s) ready to commit</div>
  </div>
  <div class="file-list">${d.staged.map(f =>
    `<div class="f"><span class="x">+</span>${escHtml(f)}</div>`
  ).join('')}</div>`;
  wiz.finalStaged = d.staged;
  body.innerHTML = html;
  document.getElementById('wiz-next').disabled = false;
  document.getElementById('wiz-next').textContent = 'Continue →';
}

async function wizDoAutofix() {
  wizSetBusy(true);
  document.getElementById('wiz-body').innerHTML = '<div class="hint">Moving secrets to .env...</div>';
  const r = await fetch('/api/commit/autofix', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({repo_path: wiz.selectedRepo.path, findings: wiz.scanResult.findings})
  });
  const d = await r.json();
  wizSetBusy(false);
  if (!d.ok) {
    document.getElementById('wiz-body').innerHTML = `<div class="wiz-error">${escHtml(d.error)}</div>`;
    return;
  }
  wiz.scanResult = {staged: d.staged, blocked_files: [], findings: {}};
  wiz.finalStaged = d.staged;
  renderScanUI(document.getElementById('wiz-body'));
}

async function wizSkipAutofix() {
  wizSetBusy(true);
  const files = Object.keys(wiz.scanResult.findings);
  const r = await fetch('/api/commit/unstage-files', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({repo_path: wiz.selectedRepo.path, files})
  });
  const d = await r.json();
  wizSetBusy(false);
  if (!d.ok) {
    document.getElementById('wiz-body').innerHTML = `<div class="wiz-error">${escHtml(d.error)}</div>`;
    return;
  }
  wiz.scanResult = {staged: d.staged, blocked_files: [], findings: {}};
  wiz.finalStaged = d.staged;
  renderScanUI(document.getElementById('wiz-body'));
}

/* ── STEP 4: COMMIT MESSAGE ────────────────────────────── */
function renderStepMessage(body) {
  body.innerHTML = `<h3>What did you change?</h3>
    <p class="hint">Brief description — AI will turn this into a clean commit message.</p>
    <textarea id="wiz-desc" placeholder="e.g. fixed the login redirect bug">${escHtml(wiz.description)}</textarea>
    <div style="margin-top:10px">
      <button class="wiz-btn wiz-btn-primary" onclick="wizGenMsg()">✨ Generate message</button>
    </div>
    ${wiz.commitMsg ? `
      <div style="margin-top:18px">
        <h3>Suggested message</h3>
        <div class="gen-msg" id="wiz-msg-preview">${escHtml(wiz.commitMsg)}</div>
        <label>Edit if needed:</label>
        <input type="text" id="wiz-msg-edit" value="${escHtml(wiz.commitMsg)}" oninput="wiz.commitMsg=this.value">
      </div>` : ''}`;
  document.getElementById('wiz-next').disabled = !wiz.commitMsg;
  document.getElementById('wiz-next').textContent = 'Commit →';
}

async function wizGenMsg() {
  const desc = document.getElementById('wiz-desc').value.trim();
  wiz.description = desc;
  wizSetBusy(true);
  const prev = document.getElementById('wiz-msg-preview');
  if (prev) prev.textContent = '⏳ Generating...';
  const r = await fetch('/api/commit/generate-message', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({repo_path: wiz.selectedRepo.path, description: desc})
  });
  const d = await r.json();
  wizSetBusy(false);
  if (!d.ok) {
    document.getElementById('wiz-body').insertAdjacentHTML('beforeend',
      `<div class="wiz-error" style="margin-top:10px">${escHtml(d.error)}</div>`);
    return;
  }
  wiz.commitMsg = d.message;
  renderStepMessage(document.getElementById('wiz-body'));
}

/* ── STEP 5: COMMIT ────────────────────────────────────── */
function renderStepCommit(body) {
  body.innerHTML = `<h3>Ready to commit</h3>
    <p class="hint">Repo: <b>${escHtml(wiz.selectedRepo.name)}</b> · Branch: <b>${escHtml(wiz.status.branch)}</b> · ${wiz.finalStaged.length} file(s)</p>
    <div class="gen-msg">${escHtml(wiz.commitMsg)}</div>
    <div class="file-list">${wiz.finalStaged.map(f =>
      `<div class="f"><span class="x">+</span>${escHtml(f)}</div>`
    ).join('')}</div>
    <div style="margin-top:14px">
      <button class="wiz-btn wiz-btn-primary" onclick="wizDoCommit()">✓ Run git commit</button>
    </div>
    <div id="wiz-commit-result"></div>`;
  document.getElementById('wiz-next').disabled = true;
  document.getElementById('wiz-next').textContent = 'Continue →';
}

async function wizDoCommit() {
  wizSetBusy(true);
  document.getElementById('wiz-commit-result').innerHTML = '<div class="hint" style="margin-top:10px">Committing...</div>';
  const r = await fetch('/api/commit/commit', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({repo_path: wiz.selectedRepo.path, message: wiz.commitMsg})
  });
  const d = await r.json();
  wizSetBusy(false);
  if (!d.ok) {
    document.getElementById('wiz-commit-result').innerHTML = `<div class="wiz-error" style="margin-top:10px">${escHtml(d.error)}</div>`;
    return;
  }
  document.getElementById('wiz-commit-result').innerHTML =
    '<div class="scan-block ok" style="margin-top:14px"><div class="title">✅ Committed locally</div></div>';
  document.getElementById('wiz-next').disabled = false;
}

/* ── STEP 6: PUSH ──────────────────────────────────────── */
function renderStepPush(body) {
  if (wiz.pushResult && wiz.pushResult.ok) {
    body.innerHTML = `<div class="wiz-success">
      <div class="ico">🚀</div>
      <h3>Pushed to GitHub!</h3>
      ${wiz.pushResult.url ? `<a href="${wiz.pushResult.url}" target="_blank">${escHtml(wiz.pushResult.url)}</a>` : ''}
    </div>`;
    document.getElementById('wiz-next').textContent = 'Done';
    document.getElementById('wiz-next').onclick = () => { wizClose(); document.getElementById('wiz-next').onclick = wizNext; };
    return;
  }

  if (wiz.status.has_remote) {
    body.innerHTML = `<h3>Push to GitHub</h3>
      <p class="hint">Remote already configured. This will run <code>git push</code>.</p>
      <button class="wiz-btn wiz-btn-primary" onclick="wizDoPush()">🚀 Push now</button>
      <div id="wiz-push-result"></div>`;
  } else {
    body.innerHTML = `<h3>No GitHub repo yet — let's create one</h3>
      <p class="hint">This will create a new repo on GitHub and push your code.</p>
      <label>Repo name</label>
      <input type="text" id="wiz-repo-name" value="${escHtml(wiz.selectedRepo.name.toLowerCase().replace(/[ _]/g,'-'))}">
      <label style="margin-top:12px">Visibility</label>
      <div class="radio-row">
        <label><input type="radio" name="vis" value="private" checked> Private</label>
        <label><input type="radio" name="vis" value="public"> Public</label>
      </div>
      <div style="margin-top:14px">
        <button class="wiz-btn wiz-btn-primary" onclick="wizCreateAndPush()">📦 Create repo + push</button>
      </div>
      <div id="wiz-push-result"></div>`;
  }
  document.getElementById('wiz-next').textContent = 'Close';
  document.getElementById('wiz-next').onclick = () => { wizClose(); document.getElementById('wiz-next').onclick = wizNext; };
}

async function wizDoPush() {
  wizSetBusy(true);
  document.getElementById('wiz-push-result').innerHTML = '<div class="hint" style="margin-top:10px">Pushing...</div>';
  const r = await fetch('/api/commit/push', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({repo_path: wiz.selectedRepo.path})
  });
  const d = await r.json();
  wizSetBusy(false);
  wiz.pushResult = d;
  if (!d.ok) {
    document.getElementById('wiz-push-result').innerHTML = `<div class="wiz-error" style="margin-top:10px">${escHtml(d.error)}</div>`;
    return;
  }
  renderStepPush(document.getElementById('wiz-body'));
}

async function wizCreateAndPush() {
  const name = document.getElementById('wiz-repo-name').value.trim();
  const vis = document.querySelector('input[name=vis]:checked').value;
  if (!name) return;
  wizSetBusy(true);
  document.getElementById('wiz-push-result').innerHTML = '<div class="hint" style="margin-top:10px">Creating repo and pushing...</div>';
  const r = await fetch('/api/commit/create-and-push', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({repo_path: wiz.selectedRepo.path, name, private: vis === 'private'})
  });
  const d = await r.json();
  wizSetBusy(false);
  wiz.pushResult = d;
  if (!d.ok) {
    document.getElementById('wiz-push-result').innerHTML = `<div class="wiz-error" style="margin-top:10px">${escHtml(d.error)}</div>`;
    return;
  }
  renderStepPush(document.getElementById('wiz-body'));
}

/* ── NAV ───────────────────────────────────────────────── */
function wizNext() {
  if (wiz.busy) return;
  if (wiz.step >= 5) { wizClose(); return; }
  wiz.step += 1;
  wizRender();
}
function wizBack() {
  if (wiz.busy || wiz.step === 0) return;
  wiz.step -= 1;
  wizRender();
}
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

# ──────────────────────────────────────────────────────────
# SMART COMMIT WIZARD — backend endpoints
# Mirrors the terminal commit_flow.run_commit_flow() step-by-step.
# ──────────────────────────────────────────────────────────

def _err(msg: str, code: int = 200):
    return jsonify({"ok": False, "error": str(msg)}), code


@app.route("/api/commit/init")
def commit_init():
    """Returns saved projects folder + list of repos found in it."""
    cfg = load()
    folder = cfg.get("projects_folder", "")
    folder_exists = bool(folder) and Path(folder).exists()
    repos = []
    if folder_exists:
        found = gm.find_git_repos(folder, cwd=os.getcwd())
        for r in found:
            repos.append({
                "name":       r["name"],
                "path":       r["path"],
                "has_remote": gm.has_remote(r["path"]),
            })
    return jsonify({
        "ok":              True,
        "projects_folder": folder,
        "folder_exists":   folder_exists,
        "repos":           repos,
    })


@app.route("/api/commit/set-folder", methods=["POST"])
def commit_set_folder():
    folder = (request.get_json() or {}).get("folder", "").strip().strip('"')
    if not folder:
        return _err("Folder path required.")
    if not Path(folder).exists():
        return _err(f"Folder not found: {folder}")
    cfg = load()
    cfg["projects_folder"] = folder
    save(cfg)
    return jsonify({"ok": True})


@app.route("/api/commit/clear-folder", methods=["POST"])
def commit_clear_folder():
    cfg = load()
    cfg.pop("projects_folder", None)
    save(cfg)
    return jsonify({"ok": True})


@app.route("/api/commit/repo-status", methods=["POST"])
def commit_repo_status():
    repo_path = (request.get_json() or {}).get("repo_path", "")
    if not repo_path or not Path(repo_path).exists():
        return _err("Invalid repo path.")
    try:
        created = cf.ensure_gitignore(repo_path)
        return jsonify({
            "ok":                True,
            "branch":            gm.get_current_branch(repo_path),
            "has_remote":        gm.has_remote(repo_path),
            "unstaged":          gm.get_unstaged_changes(repo_path),
            "gitignore_created": created,
        })
    except Exception as e:
        return _err(e)


@app.route("/api/commit/stage-and-scan", methods=["POST"])
def commit_stage_and_scan():
    """git add -A, then scan staged files for blocked filenames + sensitive patterns."""
    repo_path = (request.get_json() or {}).get("repo_path", "")
    if not repo_path or not Path(repo_path).exists():
        return _err("Invalid repo path.")

    ok, msg = gm.stage_all(repo_path)
    if not ok:
        return _err(f"git add failed: {msg}")

    staged = gm.get_staged_files(repo_path)
    if not staged:
        return jsonify({"ok": True, "staged": [], "blocked_files": [], "findings": {}})

    blocked_files = []
    findings = {}
    for fname in staged:
        if Path(fname).name in cf.BLOCKED_FILENAMES:
            blocked_files.append(fname)
            continue
        fpath = Path(repo_path) / fname
        f = cf._scan_file_lines(fpath)
        if f:
            findings[fname] = f

    # Auto-handle blocked files: append to .gitignore + unstage
    if blocked_files:
        gitignore = Path(repo_path) / ".gitignore"
        existing = gitignore.read_text(encoding="utf-8", errors="ignore") if gitignore.exists() else ""
        with open(gitignore, "a", encoding="utf-8") as gf:
            for fname in blocked_files:
                base = Path(fname).name
                if base not in existing:
                    gf.write(f"\n{base}")
        for fname in blocked_files:
            gm._run(["git", "reset", "HEAD", fname], repo_path)

    # If blocked files were unstaged, refresh staged list
    if blocked_files:
        staged = gm.get_staged_files(repo_path)

    return jsonify({
        "ok":            True,
        "staged":        staged,
        "blocked_files": blocked_files,
        "findings":      findings,
    })


@app.route("/api/commit/autofix", methods=["POST"])
def commit_autofix():
    """Move sensitive values to .env + replace with os.getenv() calls."""
    data = request.get_json() or {}
    repo_path = data.get("repo_path", "")
    findings = data.get("findings", {})
    if not repo_path or not Path(repo_path).exists():
        return _err("Invalid repo path.")
    try:
        env_path = Path(repo_path) / ".env"
        gitignore = Path(repo_path) / ".gitignore"
        existing = gitignore.read_text(encoding="utf-8", errors="ignore") if gitignore.exists() else ""
        if ".env" not in existing:
            with open(gitignore, "a", encoding="utf-8") as gf:
                gf.write("\n.env\n")

        for fname, items in findings.items():
            fpath = Path(repo_path) / fname
            if fpath.exists():
                cf._autofix_file(fpath, items, env_path)

        gm.stage_all(repo_path)
        gm._run(["git", "reset", "HEAD", ".env"], repo_path)
        return jsonify({"ok": True, "staged": gm.get_staged_files(repo_path)})
    except Exception as e:
        return _err(e)


@app.route("/api/commit/unstage-files", methods=["POST"])
def commit_unstage_files():
    data = request.get_json() or {}
    repo_path = data.get("repo_path", "")
    files = data.get("files", [])
    if not repo_path:
        return _err("Invalid repo path.")
    for f in files:
        gm._run(["git", "reset", "HEAD", f], repo_path)
    return jsonify({"ok": True, "staged": gm.get_staged_files(repo_path)})


@app.route("/api/commit/generate-message", methods=["POST"])
def commit_generate_message():
    data = request.get_json() or {}
    repo_path = data.get("repo_path", "")
    description = (data.get("description", "") or "").strip()
    if not repo_path:
        return _err("Invalid repo path.")
    try:
        staged = gm.get_staged_files(repo_path)
        if not staged:
            return _err("Nothing staged.")
        if not description:
            description = f"update {', '.join(staged[:3])}"
        diff = gm.get_staged_diff(repo_path)
        msg = ai.generate_commit_message(staged, diff or description)
        return jsonify({"ok": True, "message": msg})
    except Exception as e:
        return _err(e)


@app.route("/api/commit/commit", methods=["POST"])
def commit_commit():
    data = request.get_json() or {}
    repo_path = data.get("repo_path", "")
    message = (data.get("message", "") or "").strip()
    if not repo_path or not message:
        return _err("Repo path and message required.")
    ok, out = gm.commit(repo_path, message)
    if not ok:
        return _err(out)
    # Mirror terminal flow: log to local DB so dashboard reflects activity
    try:
        db.upsert_day("committed", commit_msg=message, repos=[Path(repo_path).name])
    except Exception:
        pass
    return jsonify({"ok": True, "output": out})


@app.route("/api/commit/push", methods=["POST"])
def commit_push():
    repo_path = (request.get_json() or {}).get("repo_path", "")
    if not repo_path:
        return _err("Invalid repo path.")
    ok, out = gm.push(repo_path)
    if not ok:
        return _err(out)
    cfg = load()
    user = cfg.get("github_username", "")
    # Try to derive URL from origin
    _, url, _ = gm._run(["git", "remote", "get-url", "origin"], repo_path)
    if url.endswith(".git"):
        url = url[:-4]
    if url.startswith("git@github.com:"):
        url = "https://github.com/" + url[len("git@github.com:"):]
    return jsonify({"ok": True, "url": url, "output": out})


@app.route("/api/commit/create-and-push", methods=["POST"])
def commit_create_and_push():
    data = request.get_json() or {}
    repo_path = data.get("repo_path", "")
    name = (data.get("name", "") or "").strip()
    private = bool(data.get("private", True))
    if not repo_path or not name:
        return _err("Repo path and name required.")

    ok, result = cf.create_github_repo(name, private)
    if not ok:
        return _err(result)
    clone_url = result

    ok, out = cf.setup_remote_and_push(repo_path, clone_url)
    if not ok:
        return _err(f"Repo created but push failed: {out}")

    cfg = load()
    user = cfg.get("github_username", "")
    url = f"https://github.com/{user}/{name}" if user else clone_url
    return jsonify({"ok": True, "url": url, "output": out})


def run_web(port: int = 7123):
    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
