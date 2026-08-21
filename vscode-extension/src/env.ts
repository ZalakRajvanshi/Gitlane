import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { getContext } from "./state";

const PROJECT_ROOT_KEY = "gitbuddy.projectRoot";

/**
 * The optional companion Python project (the CLI, the 6 PM digest, the
 * browser dashboard). Linking it lets the editor and the CLI share one
 * streak database; leaving it unset is the normal case and costs nothing.
 */
export function getProjectRoot(): string {
  return vscode.workspace.getConfiguration().get<string>(PROJECT_ROOT_KEY, "").trim();
}

export async function setProjectRoot(p: string): Promise<void> {
  await vscode.workspace.getConfiguration().update(PROJECT_ROOT_KEY, p, vscode.ConfigurationTarget.Global);
}

export function projectRootIsValid(p: string): boolean {
  if (!p) return false;
  return fs.existsSync(path.join(p, "main.py"))
      || fs.existsSync(path.join(p, "data", "gitmind.db"));
}

/** A linked project root, but only if it still exists on this machine. */
export function linkedProjectRoot(): string | undefined {
  const root = getProjectRoot();
  return root && projectRootIsValid(root) ? root : undefined;
}

/**
 * Explicit opt-in, from the menu. Nothing calls this on startup — the
 * extension is fully functional without a linked project.
 */
export async function pickProjectRoot(): Promise<string | undefined> {
  const picked = await vscode.window.showOpenDialog({
    canSelectFolders: true,
    canSelectFiles: false,
    canSelectMany: false,
    openLabel: "Link this folder",
    title: "Pick your Gitlane Python project (the folder containing main.py)",
  });
  if (!picked?.length) return undefined;

  const candidate = picked[0].fsPath;
  if (!projectRootIsValid(candidate)) {
    vscode.window.showErrorMessage(
      "That folder has no main.py — it isn't the Gitlane Python project. " +
      "This is optional: leave it unlinked and everything except the shared CLI database still works.",
    );
    return undefined;
  }
  await setProjectRoot(candidate);
  return candidate;
}

export interface EnvVars {
  GROQ_API_KEY?: string;
  GITHUB_TOKEN?: string;
}

/** Legacy path: read keys out of the linked project's .env. See credentials.ts. */
export function readEnv(projectRoot: string): EnvVars {
  const envPath = path.join(projectRoot, ".env");
  if (!fs.existsSync(envPath)) return {};
  const out: EnvVars = {};
  for (const raw of fs.readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq < 0) continue;
    const key = line.slice(0, eq).trim();
    let val = line.slice(eq + 1).trim();
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    }
    if (key === "GROQ_API_KEY") out.GROQ_API_KEY = val;
    if (key === "GITHUB_TOKEN") out.GITHUB_TOKEN = val;
  }
  return out;
}

/**
 * Where the streak database lives. A linked Python project wins, so the CLI
 * and the editor stay in sync. Otherwise we keep our own copy in the
 * extension's global storage, which is created on first write.
 */
export function dbPath(): string {
  const linked = linkedProjectRoot();
  if (linked) return path.join(linked, "data", "gitmind.db");

  const storage = getContext()?.globalStorageUri.fsPath;
  if (!storage) return "";
  return path.join(storage, "gitmind.db");
}

export function loadSettingsJson(projectRoot: string): Record<string, unknown> {
  const f = path.join(projectRoot, "settings.json");
  if (!fs.existsSync(f)) return {};
  try { return JSON.parse(fs.readFileSync(f, "utf8")); } catch { return {}; }
}

/** Last resort: a username from the linked Python project's settings.json. */
export function legacyUsername(): string {
  const linked = linkedProjectRoot();
  if (!linked) return "";
  return ((loadSettingsJson(linked).github_username as string) || "").trim();
}
