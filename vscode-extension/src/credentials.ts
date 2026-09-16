import * as vscode from "vscode";
import { getProjectRoot, readEnv, legacyUsername } from "./env";

/**
 * GitHub is the only account Gitbuddy ever touches, and even that is optional:
 * it's needed only to create a repo for you or to read your commit history.
 *
 * It goes through VS Code's own GitHub sign-in — the same provider GitLens and
 * the GitHub Pull Requests extension use. The user clicks Allow once; VS Code
 * stores and refreshes the token. Nobody pastes anything.
 */

const GITHUB_SCOPES = ["repo"];

/**
 * `interactive` decides whether the user can see a sign-in prompt. Background
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
    // Dismissed the dialog, or no network.
    return undefined;
  }
}

export async function getGithubToken(interactive = false): Promise<string | undefined> {
  const session = await getGithubSession(interactive);
  if (session) return session.accessToken;

  // Already present on the machine — never asked for.
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
