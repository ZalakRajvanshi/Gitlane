# GitMind for VS Code

Thin VS Code client for the GitMind Python project. Hits the local Flask API at `http://localhost:7123`.

## What it adds inside the editor

- **Status bar** showing your streak (`🔥 5 ✓`) — turns yellow with the uncommitted file count the moment you change a file (`🔥 5 · 8 to commit`).
- **`GitMind: Commit Now`** — one command that runs the full ship flow:
  1. `git add -A`
  2. scan staged files for secrets
  3. on hit → prompt to auto-move them to `.env` + rewrite source to `os.getenv(...)`
  4. ask "what did you change?" → AI writes the commit message
  5. commit + push (creates the GitHub repo if it doesn't exist yet)
- **`GitMind: Ask a Question`** — opens a markdown buffer with the AI answer.
- **`GitMind: Open Dashboard`** — launches the browser dashboard.
- **`GitMind: Start Background Server`** — spawns `python main.py --web` if `localhost:7123` is down.

All four are also reachable by clicking the status-bar item.

## Setup

```
cd vscode-extension
npm install
npm run compile
```

Then in VS Code: open this folder, press `F5` to launch the Extension Development Host.

Required setting once you've installed it for real use:

```jsonc
// settings.json
"gitmind.projectRoot": "C:\\Users\\you\\path\\to\\gitmind_v2\\gitmind_v2"
```

Other settings:
- `gitmind.serverUrl` (default `http://localhost:7123`)
- `gitmind.pythonPath` (default `python`)

## How it pairs with the rest of GitMind

- The 6 PM Windows Task Scheduler tick is **untouched** — keep it for the daily digest + dashboard pop.
- The browser dashboard is **untouched** — it's still the rich morning surface.
- This extension is the always-on "near-zero-click" lane: change a file, status bar nudges you, one command ships it.
