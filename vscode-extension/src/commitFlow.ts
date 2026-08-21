import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import { dbPath } from "./env";
import { getGithubToken, getGithubUsername } from "./credentials";
import { GitbuddyDb } from "./db";
import { generateCommitMessage, resolveProvider } from "./ai";
import { createRepo, getRepoIfExists } from "./github";
import { scanFile, autofixFile, ensureGitignore, appendToGitignore, BLOCKED_FILENAMES, Finding } from "./scanner";
import * as git from "./gitOps";
import { getLastRepoPath, setLastRepoPath } from "./state";

/**
 * VS Code runs fine without git installed; this extension does not. Check once
 * and say so plainly, with somewhere to go — otherwise every git call fails
 * with ENOENT and the extension just looks broken.
 */
export async function requireGit(): Promise<boolean> {
  if (await git.isGitAvailable()) return true;
  const INSTALL = "Download Git";
  const choice = await vscode.window.showErrorMessage(
    "Git isn't installed, or isn't on your PATH — Gitbuddy needs it to stage and commit. " +
    "Install it, then restart VS Code.",
    INSTALL,
  );
  if (choice === INSTALL) {
    await vscode.env.openExternal(vscode.Uri.parse("https://git-scm.com/downloads"));
  }
  return false;
}

/**
 * Pick which workspace folder to commit into. Priority:
 *   1. Active editor's workspace folder (you committed where you're typing)
 *   2. Last folder you committed to in this workspace
 *   3. Quick-pick over all workspace folders, with last-used marked
 *
 * Single-folder workspaces skip the picker entirely.
 */
async function pickRepoPath(): Promise<string | undefined> {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders || folders.length === 0) {
    vscode.window.showErrorMessage("Open a folder in VS Code to use Gitbuddy.");
    return;
  }
  if (folders.length === 1) {
    setLastRepoPath(folders[0].uri.fsPath);
    return folders[0].uri.fsPath;
  }

  // The folder of the file you're currently editing wins.
  const activeUri = vscode.window.activeTextEditor?.document.uri;
  if (activeUri) {
    const owner = vscode.workspace.getWorkspaceFolder(activeUri);
    if (owner) {
      setLastRepoPath(owner.uri.fsPath);
      return owner.uri.fsPath;
    }
  }

  // Otherwise show the picker, with the last-used folder marked.
  const last = getLastRepoPath();
  const items = folders.map(f => ({
    label: f.name + (f.uri.fsPath === last ? "  $(history) last used" : ""),
    description: f.uri.fsPath,
    path: f.uri.fsPath,
  }));
  const pick = await vscode.window.showQuickPick(items, { placeHolder: "Which workspace folder?" });
  if (pick?.path) setLastRepoPath(pick.path);
  return pick?.path;
}

/**
 * Single source of truth for "push to GitHub" — used both after a fresh
 * commit AND from the "nothing-new-to-commit-but-you-have-unpushed-stuff"
 * recovery path. Handles three states transparently:
 *
 *   - Remote already wired up → just `git push` (with non-FF auto-rebase)
 *   - No remote, but a GitHub repo with the folder's name exists → link + push
 *   - Neither → ask for a name + visibility, create the repo, push
 */
async function pushOrSetupRemote(
  repoPath: string,
  username: string,
  token: string | undefined,
): Promise<void> {
  if (await git.hasRemote(repoPath)) {
    const p = await git.push(repoPath);
    if (!p.ok) {
      vscode.window.showErrorMessage(`Push failed: ${p.out}`);
      return;
    }
    const url = await git.remoteUrl(repoPath);
    vscode.window.showInformationMessage(`🚀 Pushed${url ? `: ${url}` : ""}.`);
    return;
  }

  // No remote yet, so we're about to create a repo — this is the moment where
  // interrupting for a GitHub sign-in is justified.
  if (!token) {
    token = await getGithubToken(true);
    if (!username) username = await getGithubUsername(true);
  }
  if (!token) {
    vscode.window.showErrorMessage(
      "Sign in to GitHub to have Gitbuddy create the repo for you, or add a remote manually with `git remote add origin …`.",
    );
    return;
  }

  const defaultName = path.basename(repoPath).toLowerCase().replace(/[ _]/g, "-");

  // Auto-detect existing repo so the user doesn't have to type a name.
  if (username) {
    const existing = await getRepoIfExists(token, username, defaultName);
    if (existing) {
      const choice = await vscode.window.showInformationMessage(
        `Found existing GitHub repo "${username}/${existing.name}". Link this folder to it and push?`,
        { modal: true }, "Link and push", "Create a different repo",
      );
      if (!choice) return;
      if (choice === "Link and push") {
        const sp = await git.setOriginAndPush(repoPath, existing.clone_url);
        if (!sp.ok) {
          vscode.window.showErrorMessage(`Linked but push failed: ${sp.out}`);
          return;
        }
        vscode.window.showInformationMessage(`🚀 Pushed: ${existing.html_url}`);
        return;
      }
    }
  }

  // Either no match, no username, or user chose to create a different repo.
  const name = await vscode.window.showInputBox({
    prompt: "Name for the new GitHub repo:",
    value: defaultName,
  });
  if (!name) return;
  const visibility = await vscode.window.showQuickPick(
    ["private", "public"],
    { placeHolder: "Visibility" },
  );
  if (!visibility) return;
  const r = await createRepo(token, name, visibility === "private");
  if (!r.ok) {
    vscode.window.showErrorMessage(`GitHub: ${r.error}`);
    return;
  }
  const sp = await git.setOriginAndPush(repoPath, r.clone_url);
  if (!sp.ok) {
    vscode.window.showErrorMessage(`Repo created but push failed: ${sp.out}`);
    return;
  }
  vscode.window.showInformationMessage(`🚀 Pushed: https://github.com/${username}/${name}`);
}

export async function runCommitFlow(): Promise<void> {
  if (!(await requireGit())) return;

  const repoPath = await pickRepoPath();
  if (!repoPath) return;

  // Hoisted: needed both in the post-commit push and the "nothing-to-commit-
  // but-you-have-unpushed-stuff" recovery branch below. Non-interactive here —
  // signing in is only worth interrupting for when we actually need to push.
  const githubToken = await getGithubToken(false);
  const username    = await getGithubUsername(false);

  // Caught-in-the-wild: scaffolders / copy-pasted snippets leave a remote
  // like "https://github.com/YOUR_USERNAME/repo.git" wired up. hasRemote()
  // returns true, push silently fails, user thinks the extension is broken.
  // Sniff this BEFORE doing anything else and offer to repair.
  if (await git.isGitRepo(repoPath)) {
    const bogus = await git.placeholderRemoteUrl(repoPath);
    if (bogus) {
      const choice = await vscode.window.showWarningMessage(
        `Your remote URL looks like a template:\n${bogus}\n\nThat's why pushes have been silently failing. Fix it now?`,
        { modal: true },
        "Pick from my GitHub repos", "Enter URL manually",
      );
      if (!choice) return;
      let newUrl: string | undefined;
      if (choice === "Pick from my GitHub repos") {
        if (!githubToken || !username) {
          vscode.window.showErrorMessage("Not signed in to GitHub. Falling back to manual entry.");
          newUrl = await vscode.window.showInputBox({ prompt: "Correct GitHub URL", value: bogus });
        } else {
          const defaultName = path.basename(repoPath).toLowerCase().replace(/[ _]/g, "-");
          const existing = await getRepoIfExists(githubToken, username, defaultName);
          if (existing) {
            newUrl = existing.clone_url;
          } else {
            newUrl = await vscode.window.showInputBox({
              prompt: `No repo named "${defaultName}" found under @${username}. Paste the correct URL`,
              value: bogus,
            });
          }
        }
      } else {
        newUrl = await vscode.window.showInputBox({ prompt: "Correct GitHub URL", value: bogus });
      }
      if (!newUrl) return;
      const fix = await git.setRemoteUrl(repoPath, newUrl);
      if (!fix.ok) {
        vscode.window.showErrorMessage(`Couldn't set remote: ${fix.err}`);
        return;
      }
      vscode.window.showInformationMessage(`Remote fixed → ${newUrl}`);
    }
  }

  // Brand-new folder that hasn't been git-init'd yet: offer to do it now so
  // the rest of the flow (auto .gitignore, secret scan, auto-create GitHub
  // repo on push) works on first-touch projects.
  if (!(await git.isGitRepo(repoPath))) {
    const folderName = path.basename(repoPath);
    const choice = await vscode.window.showInformationMessage(
      `"${folderName}" isn't a git repository yet. Initialize one and continue?`,
      { modal: true }, "Initialize git",
    );
    if (choice !== "Initialize git") return;
    const r = await git.init(repoPath);
    if (!r.ok) {
      vscode.window.showErrorMessage(`git init failed: ${r.err}`);
      return;
    }
    // VS Code's git extension auto-detects the new .git within a tick — the
    // status bar refreshes itself via onDidOpenRepository (see statusBar.ts).
  }

  try {
    await vscode.window.withProgress(
      { location: vscode.ProgressLocation.Notification, title: "Gitbuddy", cancellable: false },
      async progress => {
        progress.report({ message: "Checking repo…" });
        const created = ensureGitignore(repoPath);
        if (created) vscode.window.showInformationMessage("Created .gitignore with safe defaults.");

        const unstaged = await git.unstagedFiles(repoPath);
        if (unstaged.length === 0) {
          // Working tree clean — but maybe there are unpushed commits
          // (common after pressing Escape on the repo-name prompt before).
          const ahead = await git.commitsAhead(repoPath);
          if (ahead > 0) {
            const haveRemote = await git.hasRemote(repoPath);
            const msg = haveRemote
              ? `Nothing new to commit, but you have ${ahead} commit${ahead === 1 ? "" : "s"} not pushed yet. Push now?`
              : `Nothing new to commit, but ${ahead} commit${ahead === 1 ? "" : "s"} ${ahead === 1 ? "is" : "are"} sitting locally with no GitHub remote yet. Set one up and push now?`;
            const choice = await vscode.window.showInformationMessage(msg, { modal: false }, "Yes");
            if (choice === "Yes") {
              progress.report({ message: "Pushing…" });
              await pushOrSetupRemote(repoPath, username, githubToken);
            }
            return;
          }
          vscode.window.showInformationMessage("Nothing to commit.");
          return;
        }

        progress.report({ message: "Staging + scanning for secrets…" });
        const stage = await git.stageAll(repoPath);
        if (!stage.ok) {
          vscode.window.showErrorMessage(`git add failed: ${stage.err}`);
          return;
        }

        let staged = await git.stagedFiles(repoPath);
        const blocked: string[] = [];
        const findings: Record<string, Finding[]> = {};
        for (const fname of staged) {
          if (BLOCKED_FILENAMES.has(path.basename(fname))) {
            blocked.push(fname);
            continue;
          }
          const fs_ = scanFile(path.join(repoPath, fname));
          if (fs_.length) findings[fname] = fs_;
        }

        if (blocked.length) {
          appendToGitignore(repoPath, blocked.map(f => path.basename(f)));
          for (const f of blocked) await git.unstage(repoPath, f);
          vscode.window.showWarningMessage(
            `Auto-unstaged + added to .gitignore: ${blocked.join(", ")}`,
          );
          staged = await git.stagedFiles(repoPath);
        }

        const findingFiles = Object.keys(findings);
        if (findingFiles.length) {
          const summary = findingFiles.map(f => `  • ${f} (${findings[f].length})`).join("\n");
          const choice = await vscode.window.showWarningMessage(
            `Sensitive values found in:\n${summary}\n\nMove them to .env and replace with env-var references?`,
            { modal: true }, "Auto-fix", "Unstage these files",
          );
          if (choice === "Auto-fix") {
            progress.report({ message: "Moving secrets to .env…" });
            appendToGitignore(repoPath, [".env"]);
            const envFile = path.join(repoPath, ".env");
            if (!fs.existsSync(envFile)) fs.writeFileSync(envFile, "");
            for (const f of findingFiles) {
              autofixFile(path.join(repoPath, f), findings[f], envFile);
            }
            await git.stageAll(repoPath);
            await git.unstage(repoPath, ".env");
            staged = await git.stagedFiles(repoPath);
          } else if (choice === "Unstage these files") {
            for (const f of findingFiles) await git.unstage(repoPath, f);
            staged = await git.stagedFiles(repoPath);
          } else {
            return;
          }
        }

        if (staged.length === 0) {
          vscode.window.showInformationMessage("Nothing left to commit.");
          return;
        }

        // Everything above this line — the scan, the auto-fix, the .gitignore
        // repair — is offline and keyless. Only the message needs a model, so
        // this is the first and only point where we ask for a key. Ask before
        // the description prompt, so we never collect one and then bail.
        // Never blocks: with no Copilot and no key this resolves to the
        // offline generator, so the user is never stopped to set anything up.
        const ai = await resolveProvider(true);

        const description = await vscode.window.showInputBox({
          prompt: "What did you change? (one line — or leave blank and Gitbuddy works it out)",
          placeHolder: "e.g. add password reset flow",
        });
        if (description === undefined) return;

        progress.report({ message: "Writing the commit message…" });
        const diff    = await git.stagedDiff(repoPath);
        const entries = await git.stagedNameStatus(repoPath);
        const message = await generateCommitMessage(ai, {
          files: staged, diff, entries, description: description.trim() || undefined,
        });

        const action = await vscode.window.showInformationMessage(
          `Commit message:\n\n${message}`,
          { modal: true }, "Commit + Push", "Commit only", "Edit message",
        );
        if (!action) return;

        let finalMsg = message;
        if (action === "Edit message") {
          const edited = await vscode.window.showInputBox({ value: message, prompt: "Edit commit message" });
          if (!edited) return;
          finalMsg = edited;
        }

        progress.report({ message: "Committing…" });
        const c = await git.commit(repoPath, finalMsg);
        if (!c.ok) {
          vscode.window.showErrorMessage(`Commit failed: ${c.out}`);
          return;
        }

        // Mirror the Python flow: write today's log to the shared DB so the
        // 6 PM digest + dashboard see the activity.
        try {
          const db = new GitbuddyDb(dbPath());
          await db.upsertDay("committed", finalMsg, [path.basename(repoPath)]);
        } catch {
          // non-fatal
        }

        if (action === "Commit only") {
          vscode.window.showInformationMessage("✅ Committed (local).");
          return;
        }

        progress.report({ message: "Pushing…" });
        await pushOrSetupRemote(repoPath, username, githubToken);
      },
    );
  } catch (e: any) {
    vscode.window.showErrorMessage(`Gitbuddy: ${e.message || e}`);
  }
}
