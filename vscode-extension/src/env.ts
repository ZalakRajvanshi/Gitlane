import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";

const PROJECT_ROOT_KEY = "gitlane.projectRoot";

export function getProjectRoot(): string {
  return vscode.workspace.getConfiguration().get<string>(PROJECT_ROOT_KEY, "").trim();
}

export async function setProjectRoot(p: string): Promise<void> {
  await vscode.workspace.getConfiguration().update(PROJECT_ROOT_KEY, p, vscode.ConfigurationTarget.Global);
}

export function projectRootIsValid(p: string): boolean {
  return !!p && fs.existsSync(path.join(p, "data", "gitmind.db"))
              || (!!p && fs.existsSync(path.join(p, "main.py")));
}

export async function ensureProjectRoot(): Promise<string | undefined> {
  const current = getProjectRoot();
  if (current && projectRootIsValid(current)) return current;

  const proceed = await vscode.window.showInformationMessage(
    "Gitlane needs to know where your project folder is (it contains data/gitmind.db and .env). Pick it once.",
    { modal: false },
    "Pick folder", "Later",
  );
  if (proceed !== "Pick folder") return undefined;

  const picked = await vscode.window.showOpenDialog({
    canSelectFolders: true,
    canSelectFiles: false,
    canSelectMany: false,
    openLabel: "Use this as Gitlane project folder",
  });
  if (!picked || picked.length === 0) return undefined;

  const candidate = picked[0].fsPath;
  if (!projectRootIsValid(candidate)) {
    vscode.window.showErrorMessage(
      `Doesn't look like a Gitlane project (no main.py and no data/gitmind.db inside ${candidate}).`,
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

export function dbPath(projectRoot: string): string {
  return path.join(projectRoot, "data", "gitmind.db");
}

export function loadSettingsJson(projectRoot: string): Record<string, unknown> {
  const f = path.join(projectRoot, "settings.json");
  if (!fs.existsSync(f)) return {};
  try { return JSON.parse(fs.readFileSync(f, "utf8")); } catch { return {}; }
}
