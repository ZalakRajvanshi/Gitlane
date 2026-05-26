# Gitlane — AI Commits & Secret Guard

**AI-generated commit messages, automatic secret detection in your staged files, and one-click push — all from the VS Code status bar.**

A free, local alternative to GitHub Copilot for commit messages, with a secret scanner built in that doesn't just *block* leaked API keys, it **moves them to `.env` and rewrites your source for you**.

---

## What it does

| | |
|---|---|
| 🤖 **AI commit messages** | Type one line about what you changed. Gitlane writes the full Conventional Commits message via Groq (free, fast, no card). |
| 🛡️ **Secret detection + auto-fix** | Staged files are scanned for API keys, tokens, passwords, OpenAI/Groq/GitHub keys, Google API keys. On hit, Gitlane moves the value to `.env`, replaces the source line with `os.getenv(...)` / `process.env.X`, and adds `.env` to `.gitignore`. |
| 🚀 **One-click commit + push** | Stage → scan → fix → message → commit → push, all from one command. If there's no GitHub remote, Gitlane asks for a name and **creates the repo for you**. |
| 🔥 **Streak in the status bar** | See your commit streak from any window. Status bar turns yellow with a file count the moment you change a file. |
| 💬 **Ask about your work** | "What did I build last week?" — Gitlane reads your recent commits and answers. |

---

## Why Gitlane vs. the alternatives

| Tool | AI commit msg | Secret detection | **Secret auto-fix** | One-click push |
|---|---|---|---|---|
| GitHub Copilot | ✅ | ❌ | ❌ | ❌ |
| GitLens | ❌ | ❌ | ❌ | ❌ |
| Conventional Commits ext. | ❌ (template) | ❌ | ❌ | ❌ |
| git-secrets / detect-secrets | ❌ | ✅ | ❌ (only blocks) | ❌ |
| **Gitlane** | ✅ | ✅ | ✅ | ✅ |

The **secret auto-fix** is the move competitors don't make. Most tools see `API_KEY = "sk-…"` in your diff and refuse to let you commit. Gitlane sees it, moves the value out, rewrites your code, and lets you ship.

---

## Setup

1. Install this extension.
2. Open any folder in VS Code → a banner appears asking for the Gitlane project folder. Pick it once.
3. Status bar lights up. Done.

You'll also need:
- A free **[Groq API key](https://console.groq.com)** in your project's `.env`
- Optionally a **GitHub Personal Access Token** with `repo` scope for the auto-create-repo feature

Gitlane reuses the `.env` and SQLite database from the [Gitlane Python project](https://github.com/ZalakRajvanshi/gitlane), so the optional 6 PM daily digest and browser dashboard share the same streak, sprints, and goals as the editor.

---

## Commands

All available from the command palette (`Ctrl+Shift+P`) or by clicking the status-bar item:

- **Gitlane: Commit Now** — full ship flow
- **Gitlane: Ask a Question** — answers in a markdown buffer
- **Gitlane: Open Dashboard** — opens the browser dashboard (needs the Python server)
- **Gitlane: Show Menu** — quick-pick of the above

---

## Status bar

| State | Meaning |
|---|---|
| `⚙ Gitlane: set up` | First-run — click to pick your project folder |
| `🔥 5 ✓` | 5-day streak, working copy clean |
| `🔥 5 · 3 to commit` (yellow) | 3 uncommitted changes — click to commit |
| `⚡ ✓` | Up and running, no streak yet |

---

## Keywords

AI commit message generator, AI commits, Conventional Commits, smart commit, git AI, git assistant, secret scanner, secret detection, credential leak prevention, gitleaks alternative, detect secrets, .env helper, dotenv, one-click commit, GitHub Copilot alternative, Groq, Llama, productivity, streak tracker.

---

## License

MIT. Free to use, modify, and ship.

Author: **Zalak Rajvanshi** — [github.com/ZalakRajvanshi](https://github.com/ZalakRajvanshi)
