import * as path from "path";
import { StagedEntry } from "./gitOps";

/**
 * A Conventional Commits message built from nothing but the staged file list.
 *
 * No model, no key, no account, no network, no Copilot. This is what runs for
 * a user who installed the extension thirty seconds ago and has set up
 * nothing at all — which is most of them, and the whole point.
 *
 * It won't out-write a language model. It doesn't have to: it produces a
 * correct, specific first draft in the commit box that the user edits, which
 * beats an empty box and beats being asked for an API key.
 */

const TEST_HINTS  = [/(^|[\/.])tests?[\/.]/i, /(^|[\/.])spec[\/.]/i, /__tests__/i, /\.(test|spec)\.[jt]sx?$/i];
const DOC_EXTS    = new Set([".md", ".mdx", ".rst", ".txt", ".adoc"]);
const STYLE_EXTS  = new Set([".css", ".scss", ".sass", ".less", ".styl"]);
const CI_HINTS    = [/^\.github\//i, /^\.gitlab-ci/i, /^azure-pipelines/i, /^Jenkinsfile/i, /^\.circleci\//i];
const BUILD_FILES = new Set([
  "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "tsconfig.json",
  "webpack.config.js", "vite.config.ts", "vite.config.js", "rollup.config.js",
  "requirements.txt", "pyproject.toml", "setup.py", "Pipfile", "poetry.lock",
  "Dockerfile", "docker-compose.yml", "Makefile", "go.mod", "go.sum", "Cargo.toml",
]);
const CHORE_FILES = new Set([".gitignore", ".gitattributes", ".editorconfig", ".env.example", "LICENSE"]);

function every(files: string[], pred: (f: string) => boolean): boolean {
  return files.length > 0 && files.every(pred);
}

const isTest  = (f: string) => TEST_HINTS.some(r => r.test(f));
const isDoc   = (f: string) => DOC_EXTS.has(path.extname(f).toLowerCase());
const isStyle = (f: string) => STYLE_EXTS.has(path.extname(f).toLowerCase());
const isCi    = (f: string) => CI_HINTS.some(r => r.test(f));
const isBuild = (f: string) => BUILD_FILES.has(path.basename(f));
const isChore = (f: string) => CHORE_FILES.has(path.basename(f));

/**
 * Type is decided by what the files *are* first, and only then by what
 * happened to them — a new test file is still `test`, not `feat`.
 */
function commitType(entries: StagedEntry[]): string {
  const files = entries.map(e => e.file);

  if (every(files, isTest))  return "test";
  if (every(files, isDoc))   return "docs";
  if (every(files, isStyle)) return "style";
  if (every(files, isCi))    return "ci";
  if (every(files, f => isBuild(f) || isChore(f))) {
    return every(files, isChore) ? "chore" : "build";
  }

  const added   = entries.filter(e => e.status === "A").length;
  const deleted = entries.filter(e => e.status === "D").length;

  // Only deletions, and nothing new — that's cleanup, not a feature or a fix.
  if (deleted > 0 && added === 0 && deleted === entries.length) return "refactor";
  // New source files are the clearest signal of new capability we have.
  if (added > 0) return "feat";
  return "fix";
}

/**
 * The deepest directory that contains every staged file, minus the noise at
 * the top of the tree. Files scattered across the repo get no scope, which is
 * correct — a scope that covers everything says nothing.
 */
function commitScope(files: string[]): string {
  // Folders that say nothing about *what* changed. "tests" and "docs" are in
  // here because the type already carries that meaning — test(tests) is noise.
  const IGNORED_TOP = new Set([
    "src", "lib", "app", "packages", "source", "internal", "pkg",
    "tests", "test", "docs", "doc", "spec", "__tests__",
  ]);

  const dirs = files.map(f => path.dirname(f).split(/[\\/]/).filter(p => p && p !== "."));
  if (!dirs.length) return "";

  const common: string[] = [];
  for (let i = 0; i < dirs[0].length; i++) {
    const seg = dirs[0][i];
    if (dirs.every(d => d[i] === seg)) common.push(seg); else break;
  }

  // Walk back from the deepest shared folder to the first meaningful name.
  for (let i = common.length - 1; i >= 0; i--) {
    if (!IGNORED_TOP.has(common[i].toLowerCase())) return common[i].toLowerCase();
  }

  // Everything shared was generic. A single file can still name itself —
  // but a dotfile makes an ugly scope, and repeating the filename in both the
  // scope and the description just says it twice.
  if (files.length === 1) {
    const base = path.basename(files[0], path.extname(files[0])).toLowerCase();
    if (base && !base.startsWith(".") && !IGNORED_TOP.has(base)) return base;
  }
  return "";
}

function nameList(files: string[], max = 2): string {
  const names = files.map(f => path.basename(f));
  if (names.length <= max) return names.join(" and ");
  return `${names.slice(0, max).join(", ")} and ${names.length - max} more`;
}

/** Falls back to describing the change when the user gave us nothing to go on. */
function describe(entries: StagedEntry[]): string {
  const added    = entries.filter(e => e.status === "A").map(e => e.file);
  const modified = entries.filter(e => e.status === "M").map(e => e.file);
  const deleted  = entries.filter(e => e.status === "D").map(e => e.file);

  if (added.length && !modified.length && !deleted.length) return `add ${nameList(added)}`;
  if (deleted.length && !added.length && !modified.length) return `remove ${nameList(deleted)}`;
  if (modified.length && !added.length && !deleted.length) {
    return modified.length === 1 ? `update ${nameList(modified)}` : `update ${modified.length} files`;
  }

  const parts: string[] = [];
  if (added.length)    parts.push(`add ${nameList(added, 1)}`);
  if (modified.length) parts.push(`update ${nameList(modified, 1)}`);
  if (deleted.length)  parts.push(`remove ${nameList(deleted, 1)}`);
  return parts.join(", ");
}

/** Conventional Commits caps the header at 72 characters. */
function truncate(header: string): string {
  if (header.length <= 72) return header;
  return header.slice(0, 69).replace(/[ ,;:-]+$/, "") + "…";
}

/**
 * `description` is the one line the user typed in the Commit Now flow. When we
 * have it, it *is* the message — they just told us the intent, so guessing at
 * it from filenames would be strictly worse.
 */
export function buildCommitMessage(entries: StagedEntry[], description?: string): string {
  if (!entries.length) return "chore: update";

  const type  = commitType(entries);
  const scope = commitScope(entries.map(e => e.file));

  let subject = (description ?? "").trim();
  if (!subject) subject = describe(entries);

  // Strip a type prefix the user typed themselves, so we don't double it up.
  subject = subject.replace(/^(feat|fix|docs|style|refactor|test|chore|build|ci|perf)(\([^)]*\))?:\s*/i, "");
  // Headers are lowercase and unpunctuated by convention.
  subject = subject.replace(/\.+$/, "");
  if (subject) subject = subject.charAt(0).toLowerCase() + subject.slice(1);

  // `docs(readme): update README.md` says "readme" twice — drop the scope.
  const redundant = scope && entries.length === 1 &&
    path.basename(entries[0].file, path.extname(entries[0].file)).toLowerCase() === scope;

  return truncate(scope && !redundant ? `${type}(${scope}): ${subject}` : `${type}: ${subject}`);
}
