import * as vscode from "vscode";
import { getProjectRoot, readEnv, legacyUsername } from "./env";
import { getContext } from "./state";

/**
 * Two very different things live here.
 *
 * GitHub is handled by VS Code itself. `authentication.getSession` is the same
 * built-in provider GitLens and the GitHub PR extension use: the user clicks
 * Allow, a browser round-trip happens, and VS Code stores and refreshes the
 * token. Nobody pastes a personal access token, and nobody has to learn what a
 * PAT scope is.
 *
 * Groq is the optional fallback for people without Copilot. It is never
 * prompted for — the user has to go and ask for it via the command — and when
 * it does exist it lives in SecretStorage, which is the OS keychain.
 */

const GROQ_SECRET = "gitbuddy.groqApiKey";
const GITHUB_SCOPES = ["repo"];

function secrets(): vscode.SecretStorage | undefined {
  return getContext()?.secrets;
}

/* ------------------------------------------------------------------ GitHub */

/**
 * `interactive` decides whether the user sees a sign-in prompt. Background
 * callers pass false and get undefined when signed out, so nothing nags.
 */
export async function getGithubSession(
  interactive: boolean,
): Promise<vscode.AuthenticationSession | undefined> {
  try {
    return await vscode.authentication.getSession("github", GITHUB_SCOPES, {
      createIfNone: interactive,
      silent: interactive ? undefined : true,
    });
  } catch {
    // User dismissed the dialog, or no network.
    return undefined;
  }
}

export async function getGithubToken(interactive = false): Promise<string | undefined> {
  const session = await getGithubSession(interactive);
  if (session) return session.accessToken;

  // Legacy: a token in the linked Python project's .env, or the environment.
  const root = getProjectRoot();
  const fromFile = root ? readEnv(root).GITHUB_TOKEN : undefined;
  return process.env.GITHUB_TOKEN?.trim() || fromFile || undefined;
}

/** The signed-in account name, so nobody has to type their own username. */
export async function getGithubUsername(interactive = false): Promise<string> {
  const override = vscode.workspace.getConfiguration()
    .get<string>("gitbuddy.githubUsername", "").trim();
  if (override) return override;

  const session = await getGithubSession(interactive);
  if (session) return session.account.label;

  return legacyUsername();
}

/* -------------------------------------------------------------------- Groq */

/** Pure lookup. Never prompts — that's the whole point. */
export async function getStoredGroqKey(): Promise<string | undefined> {
  const stored = await secrets()?.get(GROQ_SECRET);
  if (stored) return stored;

  const fromShell = process.env.GROQ_API_KEY?.trim();
  if (fromShell) return fromShell;

  // One-time migration off the old plaintext .env, for existing installs.
  const root = getProjectRoot();
  const legacy = root ? readEnv(root).GROQ_API_KEY : undefined;
  if (legacy) {
    await secrets()?.store(GROQ_SECRET, legacy);
    return legacy;
  }
  return undefined;
}

/** Only ever reached from the explicit "Set Groq API Key" command. */
export async function promptForGroqKey(): Promise<string | undefined> {
  const key = await vscode.window.showInputBox({
    title: "Groq API key (optional)",
    prompt: "Only needed if you don't have GitHub Copilot. Free, no card, from console.groq.com/keys",
    placeHolder: "gsk_…",
    password: true,
    ignoreFocusOut: true,
    validateInput: v => {
      const t = v.trim();
      if (!t) return "Required.";
      // A convention rather than a documented guarantee — warn, don't block.
      if (!t.startsWith("gsk_")) return "That doesn't look like a Groq key (they start with \"gsk_\").";
      return undefined;
    },
  });
  if (!key) {
    const open = await vscode.window.showInformationMessage(
      "Groq keys are free and take about a minute to create.", "Open console.groq.com",
    );
    if (open) await vscode.env.openExternal(vscode.Uri.parse("https://console.groq.com/keys"));
    return undefined;
  }
  await secrets()?.store(GROQ_SECRET, key.trim());
  return key.trim();
}

export async function clearCredentials(): Promise<void> {
  await secrets()?.delete(GROQ_SECRET);
}
