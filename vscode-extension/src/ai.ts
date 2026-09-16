import * as vscode from "vscode";
import { buildCommitMessage } from "./localMessage";
import { StagedEntry } from "./gitOps";

/**
 * Where the commit message comes from. Detected, never configured.
 *
 * If GitHub Copilot is installed and signed in — the free tier counts — VS
 * Code's Language Model API lends us its model. Otherwise the offline
 * generator builds the message from git's own added/modified/deleted signal.
 *
 * There is no third option and no setup step. Nothing in this extension asks
 * a user for an API key.
 */
export type Provider = "copilot" | "local";

export interface Resolved {
  provider: Provider;
  model?: vscode.LanguageModelChat;
}

export interface CommitContext {
  files: string[];
  diff: string;
  /** Added/modified/deleted, for the offline generator. */
  entries: StagedEntry[];
  /** The one line the user typed, when the flow collected one. */
  description?: string;
}

/**
 * VS Code requires Copilot consent to come from a user action, so background
 * callers pass `interactive: false` and land on the offline generator.
 */
export async function resolveProvider(interactive: boolean): Promise<Resolved> {
  if (interactive) {
    try {
      const [model] = await vscode.lm.selectChatModels({ vendor: "copilot" });
      if (model) return { provider: "copilot", model };
    } catch {
      // Not installed, not signed in, or consent declined.
    }
  }
  return { provider: "local" };
}

/** Copilot has no system role, so the instruction rides along with the prompt. */
async function askCopilot(model: vscode.LanguageModelChat, system: string, user: string): Promise<string> {
  const messages = [vscode.LanguageModelChatMessage.User(`${system}\n\n${user}`)];
  const res = await model.sendRequest(messages, {});
  let out = "";
  for await (const chunk of res.text) out += chunk;
  return out.trim();
}

/** Chat models like to gift-wrap one-liners in fences or quotes. Unwrap them. */
function unwrap(text: string): string {
  let t = text.trim();
  const fenced = t.match(/^```[a-z]*\s*\n?([\s\S]*?)\n?```$/i);
  if (fenced) t = fenced[1].trim();
  t = t.replace(/^["'`]+|["'`]+$/g, "").trim();
  return t.split("\n")[0].trim();
}

const COMMIT_SYSTEM =
  "You write conventional git commit messages. Format: type(scope): description. " +
  "Under 72 chars. Return ONLY the message — no quotes, no code fences, no explanation.";

export async function generateCommitMessage(resolved: Resolved, ctx: CommitContext): Promise<string> {
  const offline = () => buildCommitMessage(ctx.entries, ctx.description);
  if (resolved.provider !== "copilot" || !resolved.model) return offline();

  const user =
    `Staged files:\n${ctx.files.map(f => `  ${f}`).join("\n")}\n\n` +
    `Diff summary:\n${(ctx.diff || "Not available").slice(0, 800)}\n\n` +
    (ctx.description ? `The developer describes the change as: ${ctx.description}\n\n` : "") +
    `Write one commit message.`;

  try {
    return unwrap(await askCopilot(resolved.model, COMMIT_SYSTEM, user)) || offline();
  } catch {
    // Rate limited, offline, quota used up — the model's problem, not the
    // user's. They still get a message.
    return offline();
  }
}

/** Summarising your week is the one thing with no offline answer. */
export function canAnswerQuestions(resolved: Resolved): boolean {
  return resolved.provider === "copilot";
}

export async function answerQuestion(
  resolved: Resolved,
  username: string,
  question: string,
  commits: Array<{ repo: string; message: string; date: string }>,
): Promise<string> {
  if (!resolved.model) throw new Error("GitHub Copilot isn't available.");
  const repos = Array.from(new Set(commits.map(c => c.repo)));
  const system =
    `You are Gitbuddy, a personal GitHub work assistant for @${username}. ` +
    `Be friendly, concise and specific. Max 200 words.`;
  const user =
    `ACTIVE REPOS: ${repos.join(", ")}\nRECENT COMMITS:\n` +
    (commits.length
      ? commits.slice(0, 25).map(c => `  [${c.repo}] ${c.message}  (${c.date})`).join("\n")
      : "  No commits found.") +
    `\n\nQUESTION: ${question}`;
  return askCopilot(resolved.model, system, user);
}
