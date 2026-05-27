import * as vscode from "vscode";

/**
 * Tiny module that exposes the activated extension context so other modules
 * can persist small bits of state without us having to plumb the context
 * through every function signature.
 *
 * workspaceState is scoped to the workspace, so different windows / projects
 * remember their own "last picked folder" without stepping on each other.
 */
let context: vscode.ExtensionContext | undefined;

const LAST_REPO_KEY = "gitlane.lastRepoPath";

export function setContext(ctx: vscode.ExtensionContext): void {
  context = ctx;
}

export function getLastRepoPath(): string | undefined {
  return context?.workspaceState.get<string>(LAST_REPO_KEY);
}

export function setLastRepoPath(path: string): void {
  void context?.workspaceState.update(LAST_REPO_KEY, path);
}
