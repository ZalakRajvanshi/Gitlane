# ⚡ GitMind — AI Commits, Secret Guard & a Personal GitHub Coach

> **AI-generated commit messages, automatic secret detection in your code, and a streak/sprint coach — all powered by a free local agent. Works from the terminal, a browser dashboard, *and* a VS Code extension.**

A personal AI assistant that lives on your machine, reads your git activity, writes your commit messages in Conventional Commits format, catches leaked API keys before they hit GitHub, and tracks your shipping streak day by day. No subscription. No cloud lock-in. The AI runs on **Groq (free, no credit card)**.

---

## Three surfaces, one shared brain

| Surface | What you use it for | Trigger |
|---|---|---|
| 🧩 **VS Code extension** | One-click commit + secret scan + push from the editor status bar | Manual (commands) or auto on file change |
| 🖥️ **Browser dashboard** | Calendar, sprints, goals, ask anything visually | `gitmind --web` → `localhost:7123` |
| ⏰ **Daily tick** | 6 PM toast + auto-open dashboard with weekly digest | Windows Task Scheduler |

All three read and write the **same SQLite file** (`data/gitmind.db`) and the same `.env`, so they always see the same streak, sprints, goals, and memory. A commit logged from VS Code shows up in the next morning's digest. The 6 PM check-in updates the editor's streak instantly.

---

## Install

### Option 1 — Windows (most users)

```powershell
git clone https://github.com/ZalakRajvanshi/Git-mind.git
cd Git-mind
.\setup.ps1
```

`setup.ps1` creates a virtual environment, installs everything, creates a `gitmind.bat` launcher, and optionally adds the daily 6 PM scheduled task.

### Option 2 — Mac / Linux

```bash
git clone https://github.com/ZalakRajvanshi/Git-mind.git
cd Git-mind
bash setup.sh
```

### Option 3 — Manual

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
python main.py
```

On first run, GitMind walks you through pasting a free **[Groq API key](https://console.groq.com)** and (optionally) a **[GitHub personal access token](https://github.com/settings/tokens)** with `repo` scope.

### Optional: install the VS Code extension

```powershell
cd vscode-extension
npm install
npm run compile
npx --yes @vscode/vsce package --allow-missing-repository
```

Then in VS Code → Extensions → `…` → **Install from VSIX…** → pick the generated `gitmind-vscode-*.vsix`.

Full extension docs and the marketplace landing copy live in [`vscode-extension/README.md`](vscode-extension/README.md).

---

## Day in the life

**Morning (6 PM tick the night before fires, dashboard opens automatically):**

1. **📋 Daily digest** — AI summary of your last 7 days across all repos
2. **⚠️ Stalled repos** — flags repos you haven't touched in a while
3. **🎯 Next tasks** — 5 specific things to work on today
4. **📌 Commit check-in** — type what you're working on, GitMind writes the message; press Enter to skip
5. **Interactive menu** — ask questions, manage sprints, set goals

**Throughout the day (VS Code extension):**

- Status bar shows your streak. The moment you change a file, it flips to yellow with the uncommitted file count.
- `Ctrl+Shift+P` → **GitMind: Commit Now** runs the full ship flow: stage → scan for secrets → auto-fix to `.env` → AI commit message → commit → push (creates the GitHub repo if it doesn't exist).
- `Ctrl+Shift+P` → **GitMind: Ask a Question** answers things like *"what did I build last week?"* in a markdown buffer.

---

## CLI commands

If you ran `setup.ps1` / `setup.sh` and chose to add it to PATH:

```
gitmind                 → full morning digest + commit check-in
gitmind --cli           → jump straight to the interactive menu
gitmind --web           → open the browser dashboard
gitmind --notify        → fire the 6 PM toast manually
gitmind --schedule 18:00  → (re)create the Windows daily task at 6 PM
gitmind commit          → smart commit from any project folder
gitmind ask "what did I work on this week?"
```

Without PATH installation, prefix with `python main.py` or `.\gitmind.bat`.

---

## Menu (`gitmind --cli`)

```
1  Ask a question        "what did I build last week?" "why is my streak broken?"
2  Activity calendar     visual streak + AI pattern analysis
3  Commit message        reads git diff, writes message for you
4  Sprint                set a weekly goal, get an AI retro at the end
5  Add a goal            set repo-specific deadlines
6  View goals            see what's due and when
7  Next tasks            AI-suggested things to work on
8  Productivity          analysis of your work patterns
9  Browser dashboard     opens http://localhost:7123
```

---

## Browser dashboard

`gitmind --web` opens a dashboard at `localhost:7123`:

- Stats at a glance · all recent commits · activity calendar
- Active goals with deadlines · current sprint progress
- Ask AI directly from the browser
- Full smart-commit wizard mirrored from the CLI

---

## Features

| Feature | What it does |
|---|---|
| 🤖 **AI commit messages** | Conventional Commits format, generated from your staged diff + a one-line description |
| 🛡️ **Secret auto-fix** | Detects API keys, tokens, passwords, OpenAI/Groq/GitHub/Google keys in staged files → moves them to `.env`, rewrites your source with `os.getenv(...)` / `process.env`, adds `.env` to `.gitignore` |
| 🚀 **One-click ship** | Stage + scan + fix + commit + push in one command. No GitHub remote? GitMind creates the repo. |
| 🔥 **Streak tracking** | Day-by-day streak counter; skipping is allowed and tracked without judgment |
| 🏃 **Sprints** | Set a weekly goal, get an AI retrospective when it closes |
| 🎯 **Goals** | Per-repo deadlines with on-track / drifting / overdue signals |
| 🧠 **Memory** | Remembers facts about your work style over time |
| ⚠️ **Blocker detection** | Flags repos you haven't touched in 7+ days |
| 📊 **Productivity analysis** | When do you code most? What patterns? |
| 🌐 **Browser dashboard** | Full visual UI at `localhost:7123` |
| 🧩 **VS Code extension** | Status-bar streak + one-click commit, reads the same DB |
| 🔔 **Daily notification** | Toast at a time of your choosing (Windows Task Scheduler) |

---

## Project layout

```
Git-mind/
├── main.py                     ← Python entrypoint
├── setup.ps1 / setup.sh        ← installers (Windows / Unix)
├── requirements.txt
├── gitmind.bat                 ← Windows launcher (created by setup)
├── settings.json               ← your config (gitignored)
├── .env                        ← your API keys (gitignored)
├── agent/
│   ├── ai.py                   ← Groq calls (digest, suggestions, retro)
│   ├── github_client.py        ← GitHub REST API
│   ├── database.py             ← SQLite (commits, streaks, goals, sprints, memory)
│   ├── commit_flow.py          ← smart-commit wizard
│   ├── git_manager.py          ← repo discovery + git ops
│   ├── insights.py             ← goal-progress signals
│   ├── tui.py                  ← Rich terminal UI
│   ├── onboard.py              ← first-run wizard
│   ├── notify.py               ← Windows toast
│   └── config.py               ← settings loader
├── web/
│   └── app.py                  ← Flask dashboard + REST API
├── vscode-extension/           ← TypeScript VS Code extension
│   ├── src/                    ← reads the same gitmind.db + .env
│   └── README.md               ← marketplace listing
├── data/
│   └── gitmind.db              ← shared SQLite (gitignored)
└── logs/                       ← (reserved for future digest archives)
```

---

## Security

**Never commit `.env`, `data/gitmind.db`, or `settings.json` to GitHub.** All three are in `.gitignore`.

- Get a free Groq key at [console.groq.com](https://console.groq.com)
- Optional GitHub token (for detailed file stats + repo creation) at [github.com/settings/tokens](https://github.com/settings/tokens) — `repo` scope

See [`.github/SECURITY.md`](.github/SECURITY.md) and [`.github/CONTRIBUTING.md`](.github/CONTRIBUTING.md).

---

## License

MIT — see [LICENSE](LICENSE).

Free to use, modify, and ship.

---

## Author

Built by **Zalak Rajvanshi** — [github.com/ZalakRajvanshi](https://github.com/ZalakRajvanshi)

© 2026 Zalak Rajvanshi. Released under the MIT License.
