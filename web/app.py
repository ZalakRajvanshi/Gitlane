"""
Flask web dashboard — opens in browser via `gitmind --web`
"""
import os
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request
from agent import database as db, github_client as gh, ai
from agent import git_manager as gm
from agent import commit_flow as cf
from agent import insights
from agent.config import load, save
from datetime import date, timedelta

app = Flask(__name__)


def _err(msg, code: int = 200):
    return jsonify({"ok": False, "error": str(msg)}), code

HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GitMind ⚡</title>
<style>
  /* ── Cursor/Claude-style minimalist palette ─────────────── */
  :root {
    --bg:         #0a0c10;
    --surface:    #11141b;
    --surface-2:  #161a23;
    --surface-3:  #1c2230;
    --border:     #1f2630;
    --border-hi:  #2c3444;

    --text:       #e8eaef;
    --text-2:     #98a2b3;
    --text-3:     #5d6677;

    --accent:     #6366f1;       /* refined indigo - the ONE accent */
    --accent-soft: rgba(99,102,241,.14);
    --accent-line: rgba(99,102,241,.45);

    /* status colors used sparingly, only for true status */
    --success:    #22c55e;
    --warn:       #f59e0b;
    --danger:     #ef4444;

    /* Calendar intensity shades — 5 levels of accent indigo */
    --cal-0:      #161a23;       /* no activity */
    --cal-1:      rgba(99,102,241,.22);
    --cal-2:      rgba(99,102,241,.42);
    --cal-3:      rgba(99,102,241,.65);
    --cal-4:      rgba(99,102,241,.92);

    --shadow:     0 1px 3px rgba(0,0,0,.4);
    --shadow-md:  0 8px 24px rgba(0,0,0,.45);
    --shadow-lg:  0 16px 48px rgba(0,0,0,.55);
    --radius:     10px;
    --radius-sm:  6px;
    --radius-lg:  14px;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; }
  body {
    font-family: ui-sans-serif, -apple-system, 'Inter', 'Segoe UI', system-ui, Roboto, sans-serif;
    background: var(--bg);
    color: var(--text); min-height: 100vh; -webkit-font-smoothing: antialiased;
    line-height: 1.55; font-size: 14px;
  }
  ::selection { background: var(--accent-soft); }
  ::-webkit-scrollbar { width: 8px; height: 8px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border-hi); border-radius: 4px; }
  ::-webkit-scrollbar-thumb:hover { background: #3a4356; }

  a { color: inherit; text-decoration: none; }
  code { font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace; font-size: .92em; }

  /* ── Header ─────────────────────────────────────────────── */
  .header {
    background: rgba(10,12,16,.85); backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border);
    padding: 14px 28px; display: flex; align-items: center; gap: 14px;
    position: sticky; top: 0; z-index: 50;
  }
  .header .logo {
    width: 28px; height: 28px; border-radius: 7px;
    background: var(--accent);
    display: flex; align-items: center; justify-content: center;
    font-size: 15px; color: white; font-weight: 700;
  }
  .header h1 { font-size: 16px; font-weight: 600; color: var(--text); letter-spacing: -.01em; }
  .header .user { color: var(--text-2); font-size: 13px; }
  .header .updated { margin-left: auto; color: var(--text-3); font-size: 12px; display: flex; align-items: center; gap: 6px; }
  .header .dot-live { width: 6px; height: 6px; background: var(--success); border-radius: 50%; animation: pulse 2.4s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }

  .container { max-width: 1180px; margin: 0 auto; padding: 28px 28px 80px; }

  /* ── Stats grid (very minimal) ──────────────────────────── */
  .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
  .stat-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 18px 20px;
    transition: border-color .15s;
  }
  .stat-card:hover { border-color: var(--border-hi); }
  .stat-card .lbl { color: var(--text-2); font-size: 12px; font-weight: 500; margin-bottom: 8px; }
  .stat-card .val { font-size: 28px; font-weight: 600; color: var(--text); line-height: 1.1; letter-spacing: -.02em; font-variant-numeric: tabular-nums; }
  .stat-card .sub { color: var(--text-3); font-size: 12px; margin-top: 6px; }

  /* ── Sections ─────────────────────────────────────────────── */
  .row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px; }
  .section {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 22px 24px; margin-bottom: 14px;
  }
  .section-title {
    font-size: 13px; color: var(--text); font-weight: 600;
    margin-bottom: 18px;
    display: flex; align-items: center; gap: 8px; justify-content: space-between;
  }
  .section-title .right { color: var(--text-3); font-size: 11px; font-weight: 500; }
  .section-sub { color: var(--text-2); font-size: 13px; margin-top: -10px; margin-bottom: 16px; }

  /* ── Commits list ────────────────────────────────────────── */
  .commit-item { display: flex; gap: 12px; padding: 11px 0; border-bottom: 1px solid var(--border); align-items: flex-start; }
  .commit-item:last-child { border-bottom: none; padding-bottom: 0; }
  .commit-item:first-child { padding-top: 0; }
  .commit-dot { width: 6px; height: 6px; background: var(--accent); border-radius: 50%; margin-top: 7px; flex-shrink: 0; }
  .commit-msg { font-size: 13.5px; color: var(--text); line-height: 1.5; }
  .commit-meta { font-size: 12px; color: var(--text-3); margin-top: 3px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .commit-repo { color: var(--accent); font-weight: 500; }
  .commit-sha { background: var(--surface-3); padding: 1px 6px; border-radius: 3px; font-family: 'JetBrains Mono', Consolas, monospace; font-size: 11px; color: var(--text-2); }
  .empty-state { color: var(--text-3); font-size: 13px; padding: 16px 0; text-align: center; line-height: 1.6; }

  /* ── Calendar (GitHub style, single hue intensity) ───────── */
  .cal-header { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; margin-bottom: 6px; }
  .cal-header span { font-size: 10px; color: var(--text-3); text-align: center; font-weight: 500; }
  .cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
  .cal-day { aspect-ratio: 1; border-radius: 3px; cursor: default; position: relative; transition: transform .12s; border: 1px solid transparent; }
  .cal-day:hover { transform: scale(1.18); z-index: 5; border-color: var(--border-hi); }
  .cal-day:hover .cal-tooltip { display: block; }
  /* intensity levels (count-based) */
  .cal-l0 { background: var(--cal-0); }
  .cal-l1 { background: var(--cal-1); }
  .cal-l2 { background: var(--cal-2); }
  .cal-l3 { background: var(--cal-3); }
  .cal-l4 { background: var(--cal-4); }
  /* skipped: tiny inset ring without changing intensity */
  .cal-skip { box-shadow: inset 0 0 0 1px rgba(245,158,11,.55); }
  .cal-today { outline: 1.5px solid var(--accent); outline-offset: 1.5px; }
  .cal-tooltip {
    display: none; position: absolute; bottom: calc(100% + 6px); left: 50%; transform: translateX(-50%);
    background: var(--surface-3); border: 1px solid var(--border-hi); border-radius: 6px; padding: 6px 10px;
    font-size: 11px; white-space: nowrap; z-index: 10; color: var(--text);
    pointer-events: none; box-shadow: var(--shadow-md);
  }
  .cal-legend { display: flex; align-items: center; gap: 6px; margin-top: 14px; font-size: 11px; color: var(--text-3); justify-content: flex-end; }
  .cal-legend .scale { display: flex; gap: 3px; margin: 0 6px; }
  .cal-legend .scale i { width: 11px; height: 11px; border-radius: 3px; display: inline-block; }

  /* ── Goals ───────────────────────────────────────────────── */
  .goal-item { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--border); gap: 12px; }
  .goal-item:last-child { border-bottom: none; padding-bottom: 0; }
  .goal-item:first-child { padding-top: 0; }
  .goal-desc { font-size: 14px; font-weight: 500; }
  .goal-repo { font-size: 12px; color: var(--text-2); margin-top: 3px; }
  .goal-repo b { color: var(--accent); font-weight: 500; }
  .badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; white-space: nowrap; }
  .badge-ok    { background: rgba(34,197,94,.12);  color: var(--success); border: 1px solid rgba(34,197,94,.3); }
  .badge-warn  { background: rgba(245,158,11,.12); color: var(--warn); border: 1px solid rgba(245,158,11,.3); }
  .badge-late  { background: rgba(239,68,68,.12);  color: var(--danger); border: 1px solid rgba(239,68,68,.3); }

  /* Goal progress signals */
  .goal-row { align-items: flex-start; }
  .goal-reason { font-size: 11.5px; color: var(--text-3); margin-top: 4px; }
  .goal-bar-wrap { background: var(--surface-3); border-radius: 999px; height: 4px; margin-top: 8px; overflow: hidden; max-width: 320px; }
  .goal-bar { height: 100%; border-radius: 999px; transition: width .5s ease; }
  .sig-badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; white-space: nowrap; flex-shrink: 0; }
  .goal-bar.sig-ok,   .sig-badge.sig-ok   { }
  .goal-bar.sig-ok    { background: var(--success); }
  .goal-bar.sig-warn  { background: var(--warn); }
  .goal-bar.sig-late  { background: var(--danger); }
  .sig-badge.sig-ok   { background: rgba(34,197,94,.12);  color: var(--success); border: 1px solid rgba(34,197,94,.3); }
  .sig-badge.sig-warn { background: rgba(245,158,11,.12); color: var(--warn);    border: 1px solid rgba(245,158,11,.3); }
  .sig-badge.sig-late { background: rgba(239,68,68,.12);  color: var(--danger);  border: 1px solid rgba(239,68,68,.3); }

  /* ── Sprint ──────────────────────────────────────────────── */
  .sprint-box { background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 16px 18px; }
  .sprint-goal { font-size: 14px; font-weight: 600; margin-bottom: 4px; color: var(--text); }
  .sprint-meta { font-size: 12px; color: var(--text-2); }
  .sprint-bar-wrap { background: var(--surface-3); border-radius: 999px; height: 4px; margin-top: 12px; overflow: hidden; }
  .sprint-bar { background: var(--accent); height: 100%; border-radius: 999px; transition: width .6s ease; }

  /* ── Inputs / buttons ────────────────────────────────────── */
  input[type=text], input[type=number], input[type=date], textarea, select {
    background: var(--bg); border: 1px solid var(--border);
    border-radius: var(--radius-sm); padding: 10px 13px; color: var(--text);
    font-size: 14px; font-family: inherit; outline: none;
    transition: border-color .12s, box-shadow .12s;
    width: 100%;
  }
  input:focus, textarea:focus, select:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
  textarea { resize: vertical; min-height: 70px; line-height: 1.5; }

  .btn {
    background: var(--surface-2); border: 1px solid var(--border);
    border-radius: var(--radius-sm); padding: 9px 16px;
    color: var(--text); cursor: pointer; font-size: 13px;
    font-family: inherit; font-weight: 500; transition: all .12s;
    display: inline-flex; align-items: center; gap: 6px;
  }
  .btn:hover:not(:disabled) { border-color: var(--border-hi); background: var(--surface-3); }
  .btn:disabled { opacity: .5; cursor: not-allowed; }
  .btn-primary { background: var(--accent); border-color: var(--accent); color: white; }
  .btn-primary:hover:not(:disabled) { background: #5557e6; border-color: #5557e6; }
  .btn-ghost { background: transparent; border-color: var(--border); }
  .btn-ghost:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
  .btn-sm { padding: 6px 12px; font-size: 12px; }

  /* ── Ask AI ──────────────────────────────────────────────── */
  .ask-row { display: flex; gap: 8px; margin-bottom: 14px; }
  .ask-row input { flex: 1; }
  .quick-btns { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
  .quick-btn {
    background: transparent; border: 1px solid var(--border); border-radius: 999px;
    padding: 6px 12px; color: var(--text-2); cursor: pointer; font-size: 12px;
    font-family: inherit; transition: all .12s;
  }
  .quick-btn:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }
  .ai-output {
    background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius-sm);
    padding: 16px 18px; white-space: pre-wrap; line-height: 1.7; font-size: 13.5px;
    color: var(--text);
  }
  .ai-output:empty { display: none; }

  /* ── Insights cards (4-up) ───────────────────────────────── */
  .insights-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
  .insight-card {
    background: var(--surface-2); border: 1px solid var(--border);
    border-radius: var(--radius-sm); padding: 16px 18px; cursor: pointer;
    transition: all .12s;
  }
  .insight-card:hover { border-color: var(--accent); background: var(--surface-3); }
  .insight-card .ico { font-size: 18px; margin-bottom: 8px; }
  .insight-card h4 { font-size: 13px; font-weight: 600; color: var(--text); margin-bottom: 4px; }
  .insight-card p  { font-size: 12px; color: var(--text-2); line-height: 1.5; }
  .insight-card.loading { opacity: .6; }
  .insight-output { margin-top: 12px; }

  /* ── Loading shimmer ─────────────────────────────────────── */
  .loading-shimmer { background: linear-gradient(90deg, var(--surface-2) 25%, var(--surface-3) 50%, var(--surface-2) 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; border-radius: 4px; height: 12px; margin: 7px 0; }
  @keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }

  /* ── Smart Commit launcher ───────────────────────────────── */
  .commit-launcher {
    background: var(--surface);
    border: 1px solid var(--border); border-radius: var(--radius);
    padding: 18px 22px; display: flex; align-items: center; gap: 16px;
    margin-bottom: 20px;
    transition: border-color .15s;
  }
  .commit-launcher:hover { border-color: var(--border-hi); }
  .commit-launcher .icon-box {
    width: 38px; height: 38px; border-radius: 9px;
    background: var(--accent-soft); border: 1px solid var(--accent-line);
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; flex-shrink: 0;
  }
  .commit-launcher .left { flex: 1; }
  .commit-launcher h3 { font-size: 14px; font-weight: 600; color: var(--text); margin-bottom: 2px; letter-spacing: -.01em; }
  .commit-launcher p  { font-size: 12.5px; color: var(--text-2); line-height: 1.5; }
  .commit-launcher button { padding: 9px 18px; }

  /* ── Form rows ───────────────────────────────────────────── */
  .form-row { display: grid; gap: 10px; margin-bottom: 14px; }
  .form-row.cols-2 { grid-template-columns: 1fr 1fr; }
  .form-label { font-size: 12px; color: var(--text-2); margin-bottom: 6px; font-weight: 500; }

  /* ── Toast ───────────────────────────────────────────────── */
  .toast {
    position: fixed; bottom: 24px; right: 24px; z-index: 200;
    background: var(--surface-3); border: 1px solid var(--border-hi);
    border-radius: var(--radius-sm); padding: 12px 16px;
    font-size: 13px; color: var(--text); box-shadow: var(--shadow-lg);
    transform: translateY(100px); opacity: 0; transition: all .25s;
  }
  .toast.show { transform: translateY(0); opacity: 1; }
  .toast.ok    { border-left: 3px solid var(--success); }
  .toast.err   { border-left: 3px solid var(--danger); }

  /* ── Wizard modal ────────────────────────────────────────── */
  .wiz-overlay {
    display: none; position: fixed; inset: 0;
    background: rgba(5,7,10,.78); backdrop-filter: blur(6px);
    z-index: 100; padding: 24px; overflow-y: auto;
    animation: fadeIn .18s ease;
  }
  .wiz-overlay.open { display: block; }
  @keyframes fadeIn { from { opacity: 0 } to { opacity: 1 } }
  .wiz-modal {
    max-width: 760px; margin: 24px auto;
    background: var(--surface); border: 1px solid var(--border-hi);
    border-radius: var(--radius-lg); padding: 0; box-shadow: var(--shadow-lg);
    animation: slideUp .22s ease;
  }
  @keyframes slideUp { from { opacity: 0; transform: translateY(12px) } to { opacity: 1; transform: translateY(0) } }
  .wiz-head {
    padding: 18px 24px; border-bottom: 1px solid var(--border);
    display: flex; align-items: center; gap: 12px;
  }
  .wiz-head .ico {
    width: 30px; height: 30px; border-radius: 8px;
    background: var(--accent-soft); border: 1px solid var(--accent-line);
    display: flex; align-items: center; justify-content: center; font-size: 15px;
  }
  .wiz-head h2 { font-size: 15px; color: var(--text); font-weight: 600; flex: 1; letter-spacing: -.01em; }
  .wiz-close {
    background: transparent; border: none; color: var(--text-2);
    font-size: 20px; cursor: pointer; padding: 0; width: 28px; height: 28px;
    border-radius: 6px; display: flex; align-items: center; justify-content: center;
    transition: all .12s;
  }
  .wiz-close:hover { color: var(--text); background: var(--surface-2); }

  .wiz-steps {
    display: flex; align-items: flex-start; justify-content: space-between;
    padding: 18px 28px 14px; background: var(--bg);
    border-bottom: 1px solid var(--border); gap: 4px;
  }
  .wiz-step { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 6px; position: relative; min-width: 0; }
  .wiz-step:not(:last-child)::after {
    content: ''; position: absolute; top: 11px; left: calc(50% + 14px); right: calc(-50% + 14px);
    height: 1.5px; background: var(--border); transition: background .25s;
  }
  .wiz-step.done:not(:last-child)::after { background: var(--accent); }
  .wiz-step .circle {
    width: 24px; height: 24px; border-radius: 50%;
    background: var(--surface-2); border: 1.5px solid var(--border);
    color: var(--text-3); font-size: 11px; font-weight: 600;
    display: flex; align-items: center; justify-content: center;
    transition: all .2s; z-index: 2; position: relative;
  }
  .wiz-step .label { font-size: 10px; color: var(--text-3); font-weight: 500; text-align: center; max-width: 70px; line-height: 1.2; }
  .wiz-step.active .circle { background: var(--accent); border-color: var(--accent); color: white; box-shadow: 0 0 0 4px var(--accent-soft); }
  .wiz-step.active .label { color: var(--text); }
  .wiz-step.done .circle { background: var(--accent); border-color: var(--accent); color: white; }
  .wiz-step.done .label { color: var(--text-2); }

  .wiz-body { padding: 24px 26px; min-height: 240px; }
  .wiz-body h3 { font-size: 14px; color: var(--text); margin-bottom: 6px; font-weight: 600; letter-spacing: -.01em; }
  .wiz-body .hint { font-size: 12.5px; color: var(--text-2); margin-bottom: 16px; line-height: 1.55; }
  .wiz-body .hint code { background: var(--surface-3); padding: 2px 6px; border-radius: 4px; font-size: 11.5px; color: var(--text); }
  .wiz-body label { display: block; font-size: 12px; color: var(--text-2); margin-bottom: 6px; font-weight: 500; }

  .wiz-foot {
    padding: 14px 24px; border-top: 1px solid var(--border);
    display: flex; justify-content: space-between; gap: 10px;
    background: var(--bg); border-radius: 0 0 var(--radius-lg) var(--radius-lg);
  }

  /* ── Repo cards in wizard ────────────────────────────────── */
  .repo-card {
    background: var(--bg); border: 1px solid var(--border);
    border-radius: var(--radius-sm); padding: 12px 14px; margin-bottom: 8px;
    cursor: pointer; display: flex; align-items: center; gap: 12px;
    transition: all .12s;
  }
  .repo-card:hover { border-color: var(--border-hi); }
  .repo-card.selected { border-color: var(--accent); background: var(--accent-soft); }
  .repo-card .nm { font-weight: 600; font-size: 13.5px; color: var(--text); }
  .repo-card .pth { font-size: 11px; color: var(--text-3); margin-top: 2px; font-family: 'JetBrains Mono', Consolas, monospace; }
  .repo-card .tag { font-size: 10.5px; padding: 2px 9px; border-radius: 10px; font-weight: 500; }
  .tag-github { background: rgba(34,197,94,.1); color: var(--success); border: 1px solid rgba(34,197,94,.3); }
  .tag-local  { background: var(--surface-3); color: var(--text-2); border: 1px solid var(--border); }

  /* ── File list ───────────────────────────────────────────── */
  .file-list {
    background: var(--bg); border: 1px solid var(--border);
    border-radius: var(--radius-sm); padding: 10px 14px; max-height: 200px;
    overflow-y: auto; font-family: 'JetBrains Mono', Consolas, monospace; font-size: 12px;
  }
  .file-list .f { padding: 2px 0; color: var(--text); display: flex; align-items: center; gap: 8px; }
  .file-list .f .x { color: var(--accent); font-weight: 600; min-width: 14px; text-align: center; font-size: 11px; }

  /* ── Status pills ────────────────────────────────────────── */
  .status-row { display: flex; gap: 6px; margin-bottom: 14px; flex-wrap: wrap; }
  .pill {
    padding: 5px 11px; border-radius: 999px; font-size: 11.5px;
    background: var(--surface-2); border: 1px solid var(--border);
    color: var(--text); font-weight: 500;
  }
  .pill .k { color: var(--text-2); margin-right: 4px; }
  .pill.ok    { color: var(--success); border-color: rgba(34,197,94,.3); background: rgba(34,197,94,.08); }
  .pill.warn  { color: var(--warn); border-color: rgba(245,158,11,.3); background: rgba(245,158,11,.08); }

  /* ── Security findings ───────────────────────────────────── */
  .scan-block { border-radius: var(--radius-sm); padding: 14px; margin-bottom: 10px; }
  .scan-block.danger  { background: rgba(239,68,68,.06); border: 1px solid rgba(239,68,68,.3); }
  .scan-block.warn    { background: rgba(245,158,11,.06); border: 1px solid rgba(245,158,11,.3); }
  .scan-block.ok      { background: rgba(34,197,94,.05); border: 1px solid rgba(34,197,94,.25); }
  .scan-block .title  { font-weight: 600; font-size: 13px; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }
  .scan-block.danger .title { color: var(--danger); }
  .scan-block.warn .title   { color: var(--warn); }
  .scan-block.ok .title     { color: var(--success); }
  .finding { font-size: 12px; padding: 7px 0; border-top: 1px dashed var(--border); line-height: 1.5; }
  .finding:first-of-type { border-top: none; padding-top: 0; }
  .finding code { background: var(--bg); padding: 2px 5px; border-radius: 3px; }
  .finding .ln { color: var(--text-2); font-family: 'JetBrains Mono', Consolas, monospace; }
  .finding .arrow { color: var(--warn); margin-top: 4px; }

  .gen-msg {
    background: var(--surface-2); border: 1px solid var(--border);
    border-left: 2px solid var(--accent);
    border-radius: var(--radius-sm);
    padding: 14px 16px; margin-bottom: 12px; font-weight: 500; font-size: 13.5px; color: var(--text);
    line-height: 1.55;
  }

  .wiz-success { text-align: center; padding: 28px 0 12px; }
  .wiz-success .ico { font-size: 40px; margin-bottom: 12px; }
  .wiz-success h3 { font-size: 17px; color: var(--text); margin-bottom: 10px; font-weight: 600; }
  .wiz-success a {
    color: var(--accent); text-decoration: none; word-break: break-all;
    background: var(--surface-2); border: 1px solid var(--border);
    padding: 6px 12px; border-radius: 6px;
    display: inline-block; font-size: 12.5px;
    font-family: 'JetBrains Mono', Consolas, monospace;
  }
  .wiz-success a:hover { border-color: var(--accent); }

  .wiz-error {
    background: rgba(239,68,68,.07); border: 1px solid rgba(239,68,68,.35);
    border-radius: var(--radius-sm); padding: 11px 13px; color: var(--danger);
    font-size: 12.5px; margin-bottom: 10px; line-height: 1.5;
  }

  .radio-row { display: flex; gap: 14px; margin-top: 6px; }
  .radio-row label { display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 13px; color: var(--text); margin: 0; }
  .radio-row input[type=radio] { accent-color: var(--accent); }

  /* ── Responsive ──────────────────────────────────────────── */
  @media (max-width: 768px) {
    .stats-grid { grid-template-columns: 1fr 1fr; }
    .row2 { grid-template-columns: 1fr; }
    .insights-grid { grid-template-columns: 1fr; }
    .form-row.cols-2 { grid-template-columns: 1fr; }
    .container { padding: 18px; }
    .header { padding: 12px 18px; }
    .commit-launcher { flex-direction: column; align-items: stretch; text-align: center; }
    .commit-launcher button { width: 100%; }
    .wiz-steps { padding: 14px 12px 12px; }
    .wiz-step .label { font-size: 9px; max-width: 56px; }
    .wiz-body { padding: 20px 18px; }
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
    <div class="stat-card">
      <div class="lbl">Commits this week</div>
      <div class="val" id="s-commits">—</div>
      <div class="sub" id="s-commits-sub">past 7 days</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Day streak</div>
      <div class="val" id="s-streak">—</div>
      <div class="sub" id="s-streak-sub">days in a row</div>
    </div>
    <div class="stat-card">
      <div class="lbl">Active repos</div>
      <div class="val" id="s-repos">—</div>
      <div class="sub" id="s-repos-sub"></div>
    </div>
    <div class="stat-card">
      <div class="lbl">Files changed</div>
      <div class="val" id="s-files">—</div>
      <div class="sub" id="s-files-sub">unique files</div>
    </div>
  </div>

  <!-- Smart Commit launcher -->
  <div class="commit-launcher">
    <div class="icon-box">⚡</div>
    <div class="left">
      <h3>Smart Commit &amp; Deploy</h3>
      <p>Scan secrets · auto-fix · generate AI message · commit · push or create GitHub repo</p>
    </div>
    <button class="btn btn-primary" onclick="wizOpen()">Start</button>
  </div>

  <!-- Sprint (shown if active) -->
  <div class="section" id="sprint-section" style="display:none">
    <div class="section-title">Active sprint</div>
    <div class="sprint-box">
      <div class="sprint-goal" id="sprint-goal"></div>
      <div class="sprint-meta" id="sprint-meta"></div>
      <div class="sprint-bar-wrap"><div class="sprint-bar" id="sprint-bar" style="width:0%"></div></div>
      <div style="margin-top:14px;display:flex;gap:8px">
        <button class="btn btn-sm btn-ghost" onclick="closeSprint()">Close sprint &amp; generate retro</button>
      </div>
    </div>
  </div>

  <!-- Two column: Commits + Calendar -->
  <div class="row2">
    <div class="section">
      <div class="section-title">
        Recent commits
        <span class="right" id="commits-count"></span>
      </div>
      <div id="commits-list">
        <div class="loading-shimmer"></div>
        <div class="loading-shimmer" style="width:70%"></div>
        <div class="loading-shimmer" style="width:85%"></div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">
        Contribution activity
        <span class="right" id="cal-summary">last 35 days</span>
      </div>
      <div class="cal-header">
        <span>Sun</span><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span>
      </div>
      <div class="cal-grid" id="cal-grid"></div>
      <div class="cal-legend">
        <span>Less</span>
        <div class="scale">
          <i class="cal-l0"></i><i class="cal-l1"></i><i class="cal-l2"></i><i class="cal-l3"></i><i class="cal-l4"></i>
        </div>
        <span>More</span>
      </div>
    </div>
  </div>

  <!-- Ask AI -->
  <div class="section">
    <div class="section-title">Ask AI</div>
    <div class="section-sub">Ask anything about your work — it sees your commits, files, and context.</div>
    <div class="ask-row">
      <input type="text" id="ask-input" placeholder="What did I work on this week? What should I focus on next?" onkeydown="if(event.key==='Enter')askAI()">
      <button class="btn btn-primary" onclick="askAI()">Ask</button>
    </div>
    <div class="quick-btns">
      <button class="quick-btn" onclick="quickAsk('Summarize what I worked on this week')">This week</button>
      <button class="quick-btn" onclick="quickAsk('What should I work on next?')">Next tasks</button>
      <button class="quick-btn" onclick="quickAsk('Which repo needs the most attention right now?')">Focus area</button>
      <button class="quick-btn" onclick="quickAsk('Are there any repos I have been neglecting?')">Stalled repos</button>
    </div>
    <div class="ai-output" id="ai-response"></div>
  </div>

  <!-- AI Insights -->
  <div class="section">
    <div class="section-title">AI insights</div>
    <div class="section-sub">Click a card to generate an analysis from your recent activity.</div>
    <div class="insights-grid">
      <div class="insight-card" onclick="loadInsight('summary', this)">
        <div class="ico">▦</div>
        <h4>Weekly summary</h4>
        <p>What you shipped this week, in one paragraph.</p>
        <div class="insight-output" id="insight-summary"></div>
      </div>
      <div class="insight-card" onclick="loadInsight('suggestions', this)">
        <div class="ico">→</div>
        <h4>Suggested next tasks</h4>
        <p>What to tackle next based on momentum &amp; gaps.</p>
        <div class="insight-output" id="insight-suggestions"></div>
      </div>
      <div class="insight-card" onclick="loadInsight('productivity', this)">
        <div class="ico">∿</div>
        <h4>Productivity patterns</h4>
        <p>When you ship most, where you stall.</p>
        <div class="insight-output" id="insight-productivity"></div>
      </div>
      <div class="insight-card" onclick="loadInsight('blockers', this)">
        <div class="ico">!</div>
        <h4>Stalled repos</h4>
        <p>Projects that have gone quiet.</p>
        <div class="insight-output" id="insight-blockers"></div>
      </div>
    </div>
  </div>

  <!-- Sprint manager (always visible) -->
  <div class="section" id="sprint-manager">
    <div class="section-title">Sprints</div>
    <div id="sprint-empty" style="display:none">
      <div class="section-sub">No active sprint. Start one to focus your week.</div>
      <div class="form-row cols-2">
        <div>
          <div class="form-label">Sprint goal</div>
          <input type="text" id="sprint-goal-input" placeholder="e.g. ship the dashboard refresh">
        </div>
        <div>
          <div class="form-label">Days</div>
          <input type="number" id="sprint-days-input" value="7" min="1" max="60">
        </div>
      </div>
      <button class="btn btn-primary" onclick="startSprint()">Start sprint</button>
    </div>
    <div id="sprint-active-msg" style="display:none;font-size:13px;color:var(--text-2)">Active sprint shown above.</div>
  </div>

  <!-- Goals -->
  <div class="section">
    <div class="section-title">
      Goals
      <button class="btn btn-sm btn-ghost" onclick="toggleGoalForm()" id="goal-toggle-btn">+ Add goal</button>
    </div>

    <div id="goal-form" style="display:none;margin-bottom:18px">
      <div class="form-row cols-2">
        <div>
          <div class="form-label">Repo</div>
          <input type="text" id="goal-repo" placeholder="repo-name">
        </div>
        <div>
          <div class="form-label">Deadline</div>
          <input type="date" id="goal-deadline">
        </div>
      </div>
      <div class="form-row">
        <div>
          <div class="form-label">Description</div>
          <input type="text" id="goal-desc" placeholder="What do you want to ship?">
        </div>
      </div>
      <div style="display:flex;gap:8px">
        <button class="btn btn-primary btn-sm" onclick="addGoal()">Save goal</button>
        <button class="btn btn-sm" onclick="toggleGoalForm()">Cancel</button>
      </div>
    </div>

    <div id="goals-list">
      <div class="loading-shimmer" style="width:60%"></div>
    </div>
  </div>

</div>

<!-- Toast -->
<div class="toast" id="toast"></div>

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

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function toast(msg, kind) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show ' + (kind || 'ok');
  setTimeout(() => { t.classList.remove('show'); }, 2400);
}

function intensityClass(count) {
  if (!count) return 'cal-l0';
  if (count <= 1) return 'cal-l1';
  if (count <= 3) return 'cal-l2';
  if (count <= 6) return 'cal-l3';
  return 'cal-l4';
}

async function loadDashboard() {
  let d;
  try {
    const r = await fetch('/api/dashboard');
    d = await r.json();
  } catch(e) {
    document.getElementById('last-updated').textContent = 'Connection error';
    return;
  }

  document.getElementById('username-label').textContent = d.username ? '@' + d.username : '';
  document.getElementById('last-updated').textContent = 'Updated ' + new Date().toLocaleTimeString();

  // Stats
  document.getElementById('s-commits').textContent = d.stats.commits;
  document.getElementById('s-streak').textContent = d.stats.streak;
  document.getElementById('s-streak-sub').textContent = d.stats.streak === 1 ? 'day in a row' : 'days in a row';
  document.getElementById('s-repos').textContent = d.stats.repos;
  document.getElementById('s-repos-sub').textContent = (d.stats.repo_names || []).slice(0, 2).join(', ');
  document.getElementById('s-files').textContent = d.stats.files;

  // Sprint
  const sprintBox = document.getElementById('sprint-section');
  const sprintEmpty = document.getElementById('sprint-empty');
  const sprintActiveMsg = document.getElementById('sprint-active-msg');
  if (d.sprint) {
    sprintBox.style.display = '';
    document.getElementById('sprint-goal').textContent = d.sprint.goal;
    const dl = d.sprint.days_left;
    document.getElementById('sprint-meta').textContent =
      dl < 0 ? `Ended ${Math.abs(dl)} day(s) ago · ${d.sprint.end_date}` :
      dl === 0 ? `Ends today · ${d.sprint.end_date}` :
      `${dl} day(s) left · ends ${d.sprint.end_date}`;
    const pct = Math.max(5, Math.min(100, 100 - (dl / d.sprint.total_days * 100)));
    document.getElementById('sprint-bar').style.width = pct + '%';
    window._activeSprintId = d.sprint.id;
    if (sprintEmpty) sprintEmpty.style.display = 'none';
    if (sprintActiveMsg) sprintActiveMsg.style.display = '';
  } else {
    sprintBox.style.display = 'none';
    window._activeSprintId = null;
    if (sprintEmpty) sprintEmpty.style.display = '';
    if (sprintActiveMsg) sprintActiveMsg.style.display = 'none';
  }

  // Commits
  const cl = document.getElementById('commits-list');
  document.getElementById('commits-count').textContent = d.commits.length ? `${d.commits.length} this week` : '';
  if (!d.commits.length) {
    cl.innerHTML = '<div class="empty-state">No commits in the last 7 days.<br><span style="font-size:11.5px;color:var(--text-3)">Verify your GitHub token has repo scope.</span></div>';
  } else {
    cl.innerHTML = d.commits.slice(0, 10).map(c => `
      <div class="commit-item">
        <div class="commit-dot"></div>
        <div style="flex:1;min-width:0">
          <div class="commit-msg">${escHtml(c.message)}</div>
          <div class="commit-meta">
            <span class="commit-repo">${escHtml(c.repo)}</span>
            <span>·</span><span>${c.date}</span>
            <span class="commit-sha">${c.sha}</span>
          </div>
        </div>
      </div>`).join('');
  }

  // Calendar (GitHub-style, intensity by commit count)
  const cg = document.getElementById('cal-grid');
  const days = d.calendar || [];
  const firstDay = days.length ? new Date(days[0].date + 'T00:00:00') : new Date();
  const startPad = firstDay.getDay();
  let html = '';
  for (let i = 0; i < startPad; i++) html += '<div></div>';
  let totalCommits = 0, activeDays = 0;
  days.forEach(day => {
    const count = day.count || 0;
    if (count > 0) { totalCommits += count; activeDays += 1; }
    const isToday = day.date === today;
    const cls = intensityClass(count) +
      (day.status === 'skipped' ? ' cal-skip' : '') +
      (isToday ? ' cal-today' : '');
    const tip = count
      ? `${count} contribution${count === 1 ? '' : 's'}`
      : (day.status === 'skipped' ? 'Skipped' : 'No activity');
    html += `<div class="cal-day ${cls}" title="${day.date}: ${tip}">
      <div class="cal-tooltip">${day.date}<br>${tip}${day.commit_msg ? '<br>' + escHtml(day.commit_msg.slice(0,40)) : ''}</div>
    </div>`;
  });
  cg.innerHTML = html;
  document.getElementById('cal-summary').textContent =
    `${totalCommits} contributions · ${activeDays} active days`;

  // Goals
  renderGoals(d.goals);
}

const SIGNAL_META = {
  on_track: { cls: 'sig-ok',   label: 'On track' },
  drifting: { cls: 'sig-warn', label: 'Drifting' },
  overdue:  { cls: 'sig-late', label: 'Overdue'  },
};

function renderGoals(goals) {
  const gl = document.getElementById('goals-list');
  if (!goals || !goals.length) {
    gl.innerHTML = '<div class="empty-state">No active goals.</div>';
    return;
  }
  gl.innerHTML = goals.map(g => {
    const days = (typeof g.days_left === 'number')
      ? g.days_left
      : Math.ceil((new Date(g.deadline + 'T00:00:00') - new Date()) / 86400000);
    const dueLbl = days < 0 ? `${Math.abs(days)}d overdue` : days === 0 ? 'due today' : `${days}d left`;
    const sig = SIGNAL_META[g.signal] || SIGNAL_META.on_track;
    const progress = typeof g.progress === 'number' ? g.progress : 0;
    return `<div class="goal-item goal-row">
      <div style="flex:1;min-width:0">
        <div class="goal-desc">${escHtml(g.description)}</div>
        <div class="goal-repo"><b>${escHtml(g.repo)}</b> · due ${g.deadline} · ${dueLbl}</div>
        ${g.reason ? `<div class="goal-reason">${escHtml(g.reason)}</div>` : ''}
        <div class="goal-bar-wrap"><div class="goal-bar ${sig.cls}" style="width:${Math.max(4,progress)}%"></div></div>
      </div>
      <span class="sig-badge ${sig.cls}">${sig.label}</span>
    </div>`;
  }).join('');
}

/* ── Ask AI ────────────────────────────────────────────────── */
async function askAI() {
  const q = document.getElementById('ask-input').value.trim();
  if (!q) return;
  const box = document.getElementById('ai-response');
  box.style.display = 'block';
  box.textContent = 'Thinking…';
  try {
    const r = await fetch('/api/ask', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({question: q})
    });
    const d = await r.json();
    box.textContent = d.answer;
  } catch(e) {
    box.textContent = 'Could not reach the server.';
  }
}
function quickAsk(q) {
  document.getElementById('ask-input').value = q;
  askAI();
}

/* ── Insights ──────────────────────────────────────────────── */
async function loadInsight(kind, cardEl) {
  const out = document.getElementById('insight-' + kind);
  if (out.dataset.loaded === '1') return; // don't refetch
  cardEl.classList.add('loading');
  out.innerHTML = '<div class="loading-shimmer"></div><div class="loading-shimmer" style="width:80%"></div>';
  try {
    const r = await fetch('/api/insights/' + kind);
    const d = await r.json();
    out.innerHTML = '';
    const div = document.createElement('div');
    div.className = 'ai-output';
    div.style.marginTop = '12px';
    div.textContent = d.answer || 'No data.';
    out.appendChild(div);
    out.dataset.loaded = '1';
  } catch(e) {
    out.innerHTML = '<div class="wiz-error">Failed to load.</div>';
  }
  cardEl.classList.remove('loading');
}

/* ── Sprint actions ────────────────────────────────────────── */
async function startSprint() {
  const goal = document.getElementById('sprint-goal-input').value.trim();
  const days = parseInt(document.getElementById('sprint-days-input').value, 10) || 7;
  if (!goal) { toast('Enter a sprint goal', 'err'); return; }
  const r = await fetch('/api/sprint/start', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({goal, days})
  });
  const d = await r.json();
  if (d.ok) { toast('Sprint started'); loadDashboard(); document.getElementById('sprint-goal-input').value = ''; }
  else { toast(d.error || 'Failed', 'err'); }
}
async function closeSprint() {
  if (!window._activeSprintId) return;
  const goalEl = document.getElementById('sprint-goal');
  const oldText = goalEl.textContent;
  goalEl.textContent = 'Generating retrospective…';
  const r = await fetch('/api/sprint/close', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({sprint_id: window._activeSprintId})
  });
  const d = await r.json();
  if (d.ok) {
    toast('Sprint closed');
    alert('Sprint Retrospective\\n\\n' + (d.retro || ''));
    loadDashboard();
  } else {
    goalEl.textContent = oldText;
    toast(d.error || 'Failed', 'err');
  }
}

/* ── Goal actions ──────────────────────────────────────────── */
function toggleGoalForm() {
  const f = document.getElementById('goal-form');
  f.style.display = f.style.display === 'none' ? '' : 'none';
}
async function addGoal() {
  const repo = document.getElementById('goal-repo').value.trim();
  const desc = document.getElementById('goal-desc').value.trim();
  const dl   = document.getElementById('goal-deadline').value.trim();
  if (!repo || !desc || !dl) { toast('Fill all fields', 'err'); return; }
  const r = await fetch('/api/goal/add', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({repo, description: desc, deadline: dl})
  });
  const d = await r.json();
  if (d.ok) {
    toast('Goal added');
    document.getElementById('goal-repo').value = '';
    document.getElementById('goal-desc').value = '';
    document.getElementById('goal-deadline').value = '';
    toggleGoalForm();
    loadDashboard();
  } else {
    toast(d.error || 'Failed', 'err');
  }
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
    cfg = load()
    # Single live fetch covering the whole calendar window — we slice it for
    # the 7-day stats so the calendar gets real intensity counts.
    all_commits = gh.fetch_all_recent(35, use_cache=False)
    seven_ago = (date.today() - timedelta(days=7)).isoformat()
    commits = [c for c in all_commits if c["date"] >= seven_ago]

    file_stats = {}
    try:
        file_stats = gh.get_file_stats(7)
    except Exception:
        pass

    counts_by_day = {}
    for c in all_commits:
        counts_by_day[c["date"]] = counts_by_day.get(c["date"], 0) + 1

    stats_db = db.get_stats()
    sprint   = db.get_active_sprint()
    goals    = insights.goals_with_progress(db.get_active_goals(), all_commits)
    calendar = db.get_calendar(35)
    for d in calendar:
        d["count"] = counts_by_day.get(d["date"], 0)

    repos = list(set(c["repo"] for c in commits))

    sprint_data = None
    if sprint:
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


# ──────────────────────────────────────────────────────────
# AI INSIGHTS — surface the terminal menu's AI options
# ──────────────────────────────────────────────────────────
def _ctx_for_ai(days: int = 7):
    commits = gh.fetch_all_recent(days, use_cache=True)
    try:
        file_stats = gh.get_file_stats(days)
    except Exception:
        file_stats = {}
    return commits, file_stats


@app.route("/api/insights/summary")
def insight_summary():
    commits, file_stats = _ctx_for_ai(7)
    if not commits:
        return jsonify({"answer": "No commits in the last 7 days to summarise."})
    return jsonify({"answer": ai.summarize_week(commits, file_stats)})


@app.route("/api/insights/suggestions")
def insight_suggestions():
    commits, file_stats = _ctx_for_ai(7)
    return jsonify({"answer": ai.suggest_next_tasks(commits, file_stats)})


@app.route("/api/insights/productivity")
def insight_productivity():
    cal = db.get_calendar(21)
    return jsonify({"answer": ai.analyze_productivity(cal)})


@app.route("/api/insights/blockers")
def insight_blockers():
    commits, _ = _ctx_for_ai(7)
    cfg = load()
    try:
        all_repos = [r["name"] for r in gh.get_repos(cfg.get("github_username", ""))]
    except Exception:
        all_repos = list({c["repo"] for c in commits})
    answer = ai.detect_blockers(commits, all_repos) or "No stalled repos detected."
    return jsonify({"answer": answer})


# ──────────────────────────────────────────────────────────
# SPRINTS
# ──────────────────────────────────────────────────────────
@app.route("/api/sprint/start", methods=["POST"])
def sprint_start():
    data = request.get_json() or {}
    goal = (data.get("goal", "") or "").strip()
    days = int(data.get("days", 7) or 7)
    if not goal:
        return _err("Sprint goal required.")
    if db.get_active_sprint():
        return _err("There is already an active sprint. Close it first.")
    try:
        sid = db.create_sprint(goal, max(1, min(60, days)))
        return jsonify({"ok": True, "id": sid})
    except Exception as e:
        return _err(e)


@app.route("/api/sprint/close", methods=["POST"])
def sprint_close():
    data = request.get_json() or {}
    sid = data.get("sprint_id")
    sprint = db.get_active_sprint()
    if not sprint or (sid and sprint["id"] != sid):
        return _err("No active sprint to close.")
    commits, _ = _ctx_for_ai(7)
    try:
        retro = ai.generate_sprint_retro(sprint, commits)
        db.close_sprint(sprint["id"], retro)
        return jsonify({"ok": True, "retro": retro})
    except Exception as e:
        return _err(e)


# ──────────────────────────────────────────────────────────
# GOALS
# ──────────────────────────────────────────────────────────
@app.route("/api/goal/add", methods=["POST"])
def goal_add():
    data = request.get_json() or {}
    repo = (data.get("repo", "") or "").strip()
    desc = (data.get("description", "") or "").strip()
    dl   = (data.get("deadline", "") or "").strip()
    if not (repo and desc and dl):
        return _err("repo, description, and deadline are required.")
    try:
        date.fromisoformat(dl)
    except ValueError:
        return _err("Deadline must be YYYY-MM-DD.")
    try:
        gid = db.add_goal(repo, desc, dl)
        return jsonify({"ok": True, "id": gid})
    except Exception as e:
        return _err(e)


@app.route("/api/goals/progress")
def goals_progress():
    """Active goals enriched with on-track / drifting signals."""
    try:
        commits = gh.fetch_all_recent(35, use_cache=True)
    except Exception:
        commits = []
    return jsonify({"goals": insights.goals_with_progress(db.get_active_goals(), commits)})


@app.route("/api/goal/complete", methods=["POST"])
def goal_complete():
    gid = (request.get_json() or {}).get("goal_id")
    if not gid:
        return _err("goal_id required.")
    try:
        db.complete_goal(int(gid))
        return jsonify({"ok": True})
    except Exception as e:
        return _err(e)

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
