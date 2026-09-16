# Changelog

## 0.7.0

### No setup, no keys
- **Commit messages need nothing from you.** If GitHub Copilot is installed and
  signed in (the free tier counts), Gitbuddy uses it through VS Code's Language
  Model API. If not, a built-in generator writes a Conventional Commits message
  from which files you added, changed and deleted. Copilot failing — rate limit,
  offline, quota — falls back to the built-in generator instead of erroring.
- **No API key, anywhere.** The Groq integration and every key prompt are gone.
- **GitHub uses VS Code's own sign-in**, the same one GitLens uses — one Allow
  click, and only when Gitbuddy is creating a repo for you. Your username comes
  from that sign-in.
- **The secret scanner, auto-fix, `.gitignore` repair and commit all run with
  nothing configured.** Previously the whole flow stopped at a missing key.
- **No startup prompts.** The old "pick the Gitlane source folder" banner and the
  hardcoded folder search are gone; linking the Python CLI is optional.
- **Missing git is explained,** instead of surfacing as `spawn git ENOENT`.

### Renamed
- Gitlane is now **Gitbuddy** on the Marketplace — the name was taken.

### Packaging
- 4.4 MB → 415 KB, by excluding unused sql.js builds.
- Added `LICENSE`, this changelog, and a prepublish compile step.
- Requires VS Code 1.90+.

## 0.6.0
- Sparkle button in the Source Control panel, `Ctrl+Alt+M` to fill the commit box.
- Secret detection with auto-fix to `.env`, one-click commit + push, repo
  auto-creation, and the status-bar streak.
