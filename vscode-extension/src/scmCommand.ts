import * as vscode from "vscode";
import { ensureProjectRoot, readEnv, loadSettingsJson } from "./env";
import { generateCommitMessage, modelFromSettings } from "./groq";
import * as git from "./gitOps";

type GitRepo = {
  rootUri: vscode.Uri;
  inputBox: { value: string; placeholder?: string };
};

type GitAPI = {
  repositories: GitRepo[];
};

/**
 * The sparkle button in VS Code's Source Control panel — and Ctrl+Alt+M.
 *
 * Reads staged (or unstaged) files, asks Groq for a Conventional Commits
 * message, and drops the result into the SCM input box. The user then hits
 * VS Code's own commit button to ship it. No prompts, no modals.
 *
 * When the user clicks the icon in the SCM toolbar, VS Code passes the
 * SourceControl object — we use its rootUri to pick the right repo in
 * multi-root workspaces.
 */
export async function generateCommitMessageCommand(arg?: vscode.SourceControl): Promise<void> {
  const projectRoot = await ensureProjectRoot();
  if (!projectRoot) return;

  const env = readEnv(projectRoot);
  if (!env.GROQ_API_KEY) {
    vscode.window.showErrorMessage("GROQ_API_KEY missing from the Gitlane project's .env file.");
    return;
  }

  const repo = await pickRepo(arg);
  if (!repo) {
    vscode.window.showErrorMessage("No git repository found in this workspace.");
    return;
  }
  const repoPath = repo.rootUri.fsPath;

  // Prefer staged. Fall back to unstaged so the button still works when
  // the user is mid-edit and hasn't run `git add` yet.
  let files = await git.stagedFiles(repoPath);
  let diff  = await git.stagedDiff(repoPath);
  if (files.length === 0) {
    files = await git.unstagedFiles(repoPath);
    if (files.length === 0) {
      vscode.window.showInformationMessage("Nothing to commit.");
      return;
    }
    diff = `Changed files (unstaged):\n${files.map(f => `  ${f}`).join("\n")}`;
  }

  await vscode.window.withProgress(
    { location: vscode.ProgressLocation.SourceControl, title: "Gitlane: generating commit message…" },
    async () => {
      try {
        const model = modelFromSettings(projectRoot);
        const msg = await generateCommitMessage(
          { apiKey: env.GROQ_API_KEY!, model },
          files,
          diff,
        );
        repo.inputBox.value = msg;
      } catch (e: any) {
        vscode.window.showErrorMessage(`Gitlane: ${e.message || e}`);
      }
      // settings.json is read here only to keep the import alive for future use
      // (e.g. project-specific commit-style overrides); intentional no-op call.
      loadSettingsJson(projectRoot);
    },
  );
}

async function pickRepo(arg?: vscode.SourceControl): Promise<GitRepo | undefined> {
  const ext = vscode.extensions.getExtension<{ getAPI(v: number): GitAPI }>("vscode.git");
  if (!ext) return undefined;
  const api = (await ext.activate()).getAPI(1);
  if (api.repositories.length === 0) return undefined;
  if (api.repositories.length === 1) return api.repositories[0];

  // Triggered from the SCM toolbar: VS Code passes the SourceControl whose
  // button was clicked. Match its rootUri.
  if (arg?.rootUri) {
    const hit = api.repositories.find(r => r.rootUri.fsPath === arg.rootUri!.fsPath);
    if (hit) return hit;
  }

  // Otherwise follow the active editor.
  const active = vscode.window.activeTextEditor?.document.uri.fsPath;
  if (active) {
    const hit = api.repositories.find(r => active.startsWith(r.rootUri.fsPath));
    if (hit) return hit;
  }

  return api.repositories[0];
}
