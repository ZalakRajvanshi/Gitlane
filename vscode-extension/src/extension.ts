import * as vscode from "vscode";
import { StatusBar } from "./statusBar";
import { runCommitFlow } from "./commitFlow";
import { linkedProjectRoot, pickProjectRoot } from "./env";
import { answerQuestion, canAnswerQuestions, resolveProvider } from "./ai";
import { fetchAllRecent } from "./github";
import { setContext } from "./state";
import { generateCommitMessageCommand } from "./scmCommand";
import { getGithubSession, getGithubToken, getGithubUsername } from "./credentials";

let statusBar: StatusBar | undefined;

export function activate(context: vscode.ExtensionContext): void {
  setContext(context);
  statusBar = new StatusBar();
  context.subscriptions.push({ dispose: () => statusBar?.dispose() });

  // Status bar's project label follows the active editor + the open folders.
  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor(() => statusBar?.refresh()),
    vscode.workspace.onDidChangeWorkspaceFolders(() => statusBar?.refresh()),
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("gitbuddy.commitNow",             runCommitFlow),
    vscode.commands.registerCommand("gitbuddy.generateCommitMessage", generateCommitMessageCommand),
    vscode.commands.registerCommand("gitbuddy.ask",                   askQuestion),
    vscode.commands.registerCommand("gitbuddy.openDashboard",         openDashboard),
    vscode.commands.registerCommand("gitbuddy.showMenu",              showMenu),
    vscode.commands.registerCommand("gitbuddy.signInGithub",          signInGithub),
    vscode.commands.registerCommand("gitbuddy.linkPythonProject",     linkPythonProject),
  );

  // Off the activation hot path. Nothing here prompts, ever.
  statusBar.attach().catch(err => console.error("[gitbuddy] status bar attach failed:", err));
}

export function deactivate(): void {
  statusBar?.dispose();
}

function openDashboard(): void {
  const url = vscode.workspace.getConfiguration("gitbuddy").get<string>("dashboardUrl", "http://localhost:7123");
  vscode.env.openExternal(vscode.Uri.parse(url));
}

async function signInGithub(): Promise<void> {
  const session = await getGithubSession(true);
  if (session) {
    vscode.window.showInformationMessage(`Signed in to GitHub as @${session.account.label}.`);
  }
}

async function linkPythonProject(): Promise<void> {
  const root = await pickProjectRoot();
  if (!root) return;
  vscode.window.showInformationMessage(`Linked to ${root} — the CLI and the editor now share one streak database.`);
  await statusBar?.refresh();
}

async function askQuestion(): Promise<void> {
  const ai = await resolveProvider(true);
  if (!canAnswerQuestions(ai)) {
    vscode.window.showInformationMessage(
      "Ask Gitbuddy uses GitHub Copilot, which isn't available here. " +
      "Commit messages don't need it — those work either way.",
    );
    return;
  }

  // Reading your commits needs to know whose they are — the sign-in gives us
  // both the name and the token, so this is one dialog, not two questions.
  const username = await getGithubUsername(true);
  if (!username) {
    vscode.window.showErrorMessage("Sign in to GitHub so Gitbuddy knows whose commits to read.");
    return;
  }

  const question = await vscode.window.showInputBox({ prompt: "Ask Gitbuddy anything about your work" });
  if (!question) return;

  await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: "Gitbuddy", cancellable: false },
    async progress => {
      progress.report({ message: "Fetching commits + thinking…" });
      try {
        const commits = await fetchAllRecent(await getGithubToken(false), username, 7);
        const answer = await answerQuestion(ai, username, question, commits);
        const doc = await vscode.workspace.openTextDocument({
          content: `Q: ${question}\n\n${answer}`, language: "markdown",
        });
        await vscode.window.showTextDocument(doc, { preview: true });
      } catch (e: any) {
        vscode.window.showErrorMessage(`Gitbuddy: ${e.message || e}`);
      }
    },
  );
}

async function showMenu(): Promise<void> {
  const linked  = linkedProjectRoot();
  const session = await getGithubSession(false);

  const items: vscode.QuickPickItem[] = [
    { label: "$(git-commit) Commit now",    description: "Stage, scan for secrets, write the message, push" },
    { label: "$(sparkle) Generate message", description: "Fill the Source Control box only" },
    { label: "$(question) Ask Gitbuddy",    description: "What did I work on this week?" },
    {
      label: "$(github) GitHub sign-in",
      description: session ? `Signed in as @${session.account.label}` : "Optional — lets Gitbuddy create repos for you",
    },
    {
      label: "$(link) Link Python project",
      description: linked ? `Linked: ${linked}` : "Optional — share the streak database with the CLI",
    },
  ];
  // A dead button for anyone not running the Python server, so only offer it
  // when a project is actually linked.
  if (linked) {
    items.push({ label: "$(browser) Open dashboard", description: "Needs the Python server running" });
  }

  const pick = await vscode.window.showQuickPick(items, { placeHolder: "Gitbuddy" });
  if (!pick) return;
  if (pick.label.includes("Commit now"))          return runCommitFlow();
  if (pick.label.includes("Generate message"))    return generateCommitMessageCommand();
  if (pick.label.includes("Ask Gitbuddy"))        return askQuestion();
  if (pick.label.includes("GitHub sign-in"))      return signInGithub();
  if (pick.label.includes("Link Python project")) return linkPythonProject();
  if (pick.label.includes("Open dashboard"))      return openDashboard();
}
