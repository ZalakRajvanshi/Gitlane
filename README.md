# ⚡ GitMind — Your GitHub Work Assistant

A personal AI agent that lives on your machine, understands your code, and helps you stay productive every day — beginner-friendly, no complicated setup.

---

## Install in 2 steps

```bash
# 1. Run setup
bash setup.sh

# 2. Get a free Groq key at https://console.groq.com
#    GitMind will ask for it on first run
```

That's it. GitMind guides you through everything else.

---

## What happens every morning

When you open your terminal (or on boot):

1. **📋 Daily digest** — AI summary of your last 7 days across all repos
2. **⚠️ Stalled repos** — flags repos you haven't touched in a while
3. **🎯 Next tasks** — 5 specific things to work on today
4. **📌 Commit check-in** — asks what you're working on, generates a commit message
   - Describe your work → it writes the commit message
   - Press Enter with nothing → marks as **skip** (no judgment)
5. **Interactive menu** — ask questions, manage sprints, set goals

---

## Commands

```
./gitmind.sh           → full startup (default)
./gitmind.sh --cli     → jump straight to the menu
./gitmind.sh --web     → open browser dashboard
./gitmind.sh --notify  → send a desktop notification only
./gitmind.sh ask "what did I work on this week?"  → one-shot question
```

If you added it globally during setup:
```
gitmind
gitmind --web
gitmind ask "what should I work on next?"
```

---

## Menu Options

```
1  Ask a question     → "what did I build last week?" "why is my streak broken?"
2  Activity calendar  → visual streak + AI pattern analysis
3  Commit message     → reads git diff, writes message for you
4  Sprint             → set a weekly goal, get a retro at the end
5  Add a goal         → set repo-specific deadlines
6  View goals         → see what's due and when
7  Next tasks         → AI-suggested things to work on
8  Productivity       → analysis of your work patterns
9  Browser dashboard  → opens http://localhost:7123
```

---

## Browser Dashboard

Run `gitmind --web` and open `http://localhost:7123` to see:
- Stats at a glance
- All recent commits
- Activity calendar
- Active goals with deadlines
- Ask AI directly from the browser

---

## Features

| Feature | What it does |
|---|---|
| 🤖 AI summaries | Summarizes your week in plain English |
| 📌 Commit check-in | Asks what you're doing, writes the commit message |
| ⏭️ Skip days | Press Enter to skip — tracked without judgment |
| 🔥 Streaks | Tracks your coding streak day by day |
| 🏃 Sprints | Set a weekly goal, get an AI retrospective |
| 🎯 Goals | Add deadlines per repo, shown in calendar & dashboard |
| 🧠 Memory | Remembers facts about your work style over time |
| ⚠️ Blocker detection | Flags stalled repos automatically |
| 📊 Productivity analysis | When do you code most? What patterns do you have? |
| 🌐 Browser dashboard | Full visual UI at localhost:7123 |
| 🔔 Boot notification | Desktop notification when laptop starts |

---

## For Developers

See [INSTALLATION.md](INSTALLATION.md) for detailed setup instructions.

Quick setup:
```bash
git clone https://github.com/yourusername/gitmind.git
cd gitmind
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Add your API keys to .env
python main.py
```

## Security

**Important:** Never commit `.env` or `settings.json` to GitHub. Both are in `.gitignore`.

- Get a free Groq key at [console.groq.com](https://console.groq.com)
- Optional GitHub token for enhanced stats: [github.com/settings/tokens](https://github.com/settings/tokens)

See [SECURITY.md](.github/SECURITY.md) and [CONTRIBUTING.md](.github/CONTRIBUTING.md).

---

## Files

```
gitmind/
├── main.py              ← run this
├── setup.sh             ← run once to install
├── requirements.txt
├── settings.json        ← your config (auto-created)
├── .env                 ← your API keys (auto-created)
├── agent/
│   ├── ai.py            ← all AI logic (Groq)
│   ├── github_client.py ← GitHub API
│   ├── database.py      ← SQLite (commits, streaks, goals, sprints)
│   ├── tui.py           ← terminal UI
│   ├── onboard.py       ← first-run wizard
│   ├── notify.py        ← desktop notifications
│   └── config.py        ← settings loader
├── web/
│   └── app.py           ← Flask browser dashboard
├── data/
│   └── gitmind.db       ← your data (SQLite)
└── logs/
    └── digest_YYYY-MM-DD.txt
```

---

## Free API Key

GitMind uses **Groq** — it's free, fast, and requires no credit card.

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up → API Keys → Create Key
3. Paste when GitMind asks (or add to `.env`)

Optionally add a GitHub token for detailed file stats:
1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. Create token → check `repo` scope
3. Paste when GitMind asks (or add `GITHUB_TOKEN=...` to `.env`)

---

## License

MIT License — see [LICENSE](LICENSE) for full details.

This project is free to use, modify and contribute.

---

## Author

Built by **Zalak Rajvanshi**

© 2026 Zalak Rajvanshi. All rights reserved under the MIT License.
