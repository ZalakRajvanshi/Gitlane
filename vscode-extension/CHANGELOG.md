# Changelog

## 0.7.0

### Nothing to set up any more
- **AI commit messages now use GitHub Copilot when it's there.** Via VS Code's
  Language Model API, so anyone signed into Copilot — the free tier counts —
  gets commit messages without an API key, an account, or knowing what Groq is.
  A Groq key is now an optional fallback that is never prompted for.
- **GitHub is handled by VS Code's built-in sign-in**, the same one GitLens and
  the GitHub PR extension use. No more pasting a personal access token, and the
  username comes from the signed-in account instead of a setting.
- **The secret scanner never asks for anything.** The scan, the auto-fix, the
  `.gitignore` repair, `git init` and the commit itself all run with nothing
  configured. A model is requested at one point only: writing the message.
- **Git missing is now a clear message,** not a pile of `spawn git ENOENT`
  failures pretending to be "this isn't a repository".

### Fixed
- **Commit messages came back empty.** Groq decommissioned the entire Llama
  line — `llama-3.3-70b-versatile` now 404s and `llama3-70b-8192` returns
  `model_decommissioned`. Every model Groq still serves is a reasoning model,
  and reasoning tokens are billed against the same completion budget as the
  answer, so the old 80-token cap was spent entirely on thinking and the reply
  arrived blank. The default is now `openai/gpt-oss-120b`, the reasoning budget
  is set per model family, and an empty reply raises a real error instead of
  silently filling the commit box with nothing.
- Stale `llama*` values in an existing configuration are upgraded automatically
  rather than failing on the first click.

### Changed
- **The extension now works on its own.** The Groq API key and GitHub token are
  entered in VS Code and stored in your OS keychain via SecretStorage. Cloning
  the companion Python project and hand-editing a `.env` is no longer required —
  it is an optional link, for sharing one streak database with the CLI.
- Removed the hardcoded filesystem paths that only resolved on the author's
  machine.
- New settings: `gitbuddy.model`, `gitbuddy.githubUsername`.
- New commands: Set Groq API Key, Set GitHub Token, Link Python Project,
  Remove Stored Credentials.

## 0.6.0
- Sparkle button in the Source Control panel, `Ctrl+Alt+M` to fill the commit box.
- Secret detection with auto-fix to `.env`, one-click commit + push, repo
  auto-creation, and the status-bar streak.
