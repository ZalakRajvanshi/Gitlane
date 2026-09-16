import * as fs from "fs";
import * as path from "path";

const SENSITIVE_PATTERNS: Array<{ pattern: RegExp; envKey: string }> = [
  { pattern: /(?:api[_-]?key)\s*=\s*["']([^"']{8,})["']/i,             envKey: "API_KEY" },
  { pattern: /(?:secret[_-]?key|secret)\s*=\s*["']([^"']{8,})["']/i,   envKey: "SECRET_KEY" },
  { pattern: /(?:password|passwd|pwd)\s*=\s*["']([^"']{4,})["']/i,     envKey: "PASSWORD" },
  { pattern: /(?:token)\s*=\s*["']([^"']{8,})["']/i,                   envKey: "TOKEN" },
  { pattern: /(?:access[_-]?key)\s*=\s*["']([^"']{8,})["']/i,          envKey: "ACCESS_KEY" },
  { pattern: /(sk-[A-Za-z0-9]{20,})/,                                  envKey: "OPENAI_KEY" },
  { pattern: /(gsk_[A-Za-z0-9]{20,})/,                                 envKey: "GROQ_KEY" },
  { pattern: /(ghp_[A-Za-z0-9]{20,})/,                                 envKey: "GITHUB_TOKEN" },
  { pattern: /(AIza[A-Za-z0-9_\-]{30,})/,                              envKey: "GOOGLE_KEY" },
];

export const BLOCKED_FILENAMES = new Set([
  ".env", ".env.local", ".env.production", ".env.development",
  "credentials.json", "secrets.json", "serviceAccountKey.json",
  "private_key.pem", "id_rsa",
]);

const SKIP_EXTENSIONS = new Set([
  ".png", ".jpg", ".jpeg", ".gif", ".mp4", ".zip",
  ".exe", ".dll", ".pyc", ".db", ".sqlite", ".pem",
]);

const PLACEHOLDER_VALUES = new Set(["your_key_here", "xxx", "***", "", "none", "null", "true", "false"]);

export interface Finding {
  lineNum: number;
  line: string;
  envKey: string;
  value: string;
  fullMatch: string;
}

/** Anything bigger is a bundle, a dataset or a lockfile — not hand-written secrets. */
const MAX_SCAN_BYTES = 2 * 1024 * 1024;

/**
 * The contents of a staged path, or undefined if it isn't something we can
 * meaningfully scan as text.
 *
 * "Staged path" is not the same as "file". A nested git repository or a
 * submodule is staged as a gitlink and shows up in `git diff --staged` as a
 * plain name, but on disk it's a directory — reading it threw EISDIR and took
 * down the whole commit flow. Binaries (a Windows .lnk, a compiled asset with
 * an unlisted extension) and files locked or deleted since staging are the
 * same class of problem. None of them should stop a commit.
 */
function readScannableText(filepath: string): string | undefined {
  try {
    const stat = fs.statSync(filepath);
    if (!stat.isFile() || stat.size > MAX_SCAN_BYTES) return undefined;

    const buf = fs.readFileSync(filepath);
    // Git's own binary heuristic: a NUL byte in the first 8 KB.
    if (buf.subarray(0, 8000).includes(0)) return undefined;
    return buf.toString("utf8");
  } catch {
    return undefined;
  }
}

export function scanFile(filepath: string): Finding[] {
  if (SKIP_EXTENSIONS.has(path.extname(filepath).toLowerCase())) return [];

  const text = readScannableText(filepath);
  if (text === undefined) return [];

  const lines = text.split(/\r?\n/);
  const findings: Finding[] = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    for (const { pattern, envKey } of SENSITIVE_PATTERNS) {
      const m = line.match(pattern);
      if (!m) continue;
      const value = m[m.length - 1] || m[0];
      if (PLACEHOLDER_VALUES.has(value.toLowerCase())) continue;
      findings.push({
        lineNum: i + 1,
        line: line.trim(),
        envKey,
        value,
        fullMatch: m[0],
      });
      break;
    }
  }
  return findings;
}

const DEFAULT_GITIGNORE = `.env
.env.local
.env.production
__pycache__/
*.pyc
*.pyo
.venv/
venv/
env/
node_modules/
.DS_Store
Thumbs.db
*.log
dist/
build/
.idea/
.vscode/
*.sqlite
*.db
credentials.json
secrets.json
serviceAccountKey.json
`;

export function ensureGitignore(repoPath: string): boolean {
  const gi = path.join(repoPath, ".gitignore");
  if (!fs.existsSync(gi)) {
    fs.writeFileSync(gi, DEFAULT_GITIGNORE);
    return true;
  }
  const existing = fs.readFileSync(gi, "utf8");
  const missing: string[] = [];
  for (const line of DEFAULT_GITIGNORE.split("\n")) {
    if (line && !existing.includes(line)) missing.push(line);
  }
  if (missing.length) {
    fs.appendFileSync(gi, "\n" + missing.join("\n"));
  }
  return false;
}

export function appendToGitignore(repoPath: string, lines: string[]): void {
  const gi = path.join(repoPath, ".gitignore");
  const existing = fs.existsSync(gi) ? fs.readFileSync(gi, "utf8") : "";
  const newLines = lines.filter(l => !existing.includes(l));
  if (newLines.length === 0) return;
  fs.appendFileSync(gi, "\n" + newLines.join("\n") + "\n");
}

/**
 * Move sensitive values to .env + replace the source line with os.getenv() /
 * process.env. Returns the list of env keys written.
 */
export function autofixFile(filepath: string, findings: Finding[], envPath: string): string[] {
  let content = fs.readFileSync(filepath, "utf8");
  let envContent = fs.existsSync(envPath) ? fs.readFileSync(envPath, "utf8") : "";
  const isPython = filepath.endsWith(".py");
  const accessor = isPython ? "os.getenv" : "process.env";
  const fixed: string[] = [];

  for (const f of findings) {
    let envKey = f.envKey;
    let counter = 1;
    while (!envContent.includes(`${envKey}=${f.value}`) && envContent.includes(envKey)) {
      envKey = `${f.envKey}_${counter++}`;
    }

    const replacement = isPython
      ? `${accessor}("${envKey}")`
      : `${accessor}.${envKey}`;

    const re = new RegExp(`["'][^"']*${escapeRegex(f.value)}[^"']*["']`);
    let newLine = f.fullMatch.replace(re, replacement);
    if (newLine === f.fullMatch) {
      newLine = f.fullMatch.replace(`"${f.value}"`, replacement)
                           .replace(`'${f.value}'`, replacement);
    }
    content = content.replace(f.fullMatch, newLine);

    if (!envContent.includes(envKey)) {
      envContent += `\n${envKey}=${f.value}`;
    }
    fixed.push(envKey);
  }

  if (fixed.length && isPython && !content.includes("import os")) {
    content = "import os\n" + content;
  }

  fs.writeFileSync(filepath, content);
  fs.writeFileSync(envPath, envContent.replace(/^\n+/, ""));
  return fixed;
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
