import * as vscode from "vscode";
import * as groq from "./groq";
import { getStoredGroqKey } from "./credentials";
import { currentModel } from "./groq";
import { buildCommitMessage } from "./localMessage";
import { StagedEntry } from "./gitOps";

/**
 * Where the words come from.
 *
 * Copilot first, because VS Code hands it to us for free: anyone signed into
 * Copilot — the free tier counts — gets a model without entering a key or
 * knowing what Groq is.
 *
 * If there's no Copilot we fall through to the offline generator, which needs
 * nothing at all. There is deliberately no "none" case and no setup prompt:
 * the extension must never stop and ask a new user for credentials before it
 * will do its job.
 *
 * Groq sits in between and is opt-in only — it is never advertised, never
 * prompted for, and only used by someone who went looking for the command.
 */
export type Provider = "copilot" | "groq" | "local";

export interface Resolved {
  provider: Provider;
  model?: vscode.LanguageModelChat;
  groqKey?: string;
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
 * `interactive` controls the Copilot consent dialog. VS Code requires consent
 * to be requested from a user-initiated action, so background callers pass
 * false and simply land on the offline generator.
 */
export async function resolveProvider(interactive: boolean): Promise<Resolved> {
  if (interactive) {
    try {
      const [model] = await vscode.lm.selectChatModels({ vendor: "copilot" });
      if (model) return { provider: "copilot", model };
    } catch {
      // Not installed, not signed in, or consent declined — fall through.
    }
  }

  const groqKey = await getStoredGroqKey();
  if (groqKey) return { provider: "groq", groqKey };

  return { provider: "local" };
}

/** Copilot has no system role, so the instruction rides along with the prompt. */
async function askCopilot(
  model: vscode.LanguageModelChat,
  system: string,
  user: string,
): Promise<string> {
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

export async function generateCommitMessage(
  resolved: Resolved,
  ctx: CommitContext,
): Promise<string> {
  const offline = () => buildCommitMessage(ctx.entries, ctx.description);

  const user =
    `Staged files:\n${ctx.files.map(f => `  ${f}`).join("\n")}\n\n` +
    `Diff summary:\n${(ctx.diff || "Not available").slice(0, 800)}\n\n` +
    (ctx.description ? `The developer describes the change as: ${ctx.description}\n\n` : "") +
    `Write one commit message.`;

  try {
    if (resolved.provider === "copilot" && resolved.model) {
      const msg = unwrap(await askCopilot(resolved.model, COMMIT_SYSTEM, user));
      return msg || offline();
    }
    if (resolved.provider === "groq" && resolved.groqKey) {
      const msg = unwrap(await groq.generateCommitMessage(
        { apiKey: resolved.groqKey, model: currentModel() }, ctx.files, ctx.diff,
      ));
      return msg || offline();
    }
  } catch {
    // Rate limited, offline, quota exhausted, consent withdrawn — all of which
    // are the model's problem, not the user's. Fall back rather than fail.
    return offline();
  }
  return offline();
}

/** Unlike commit messages, this genuinely needs a model — there's no offline answer. */
export function canAnswerQuestions(resolved: Resolved): boolean {
  return resolved.provider !== "local";
}

export async function answerQuestion(
  resolved: Resolved,
  username: string,
  memory: Record<string, string>,
  question: string,
  commits: Array<{ repo: string; message: string; date: string }>,
): Promise<string> {
  if (resolved.provider === "copilot" && resolved.model) {
    const repos = Array.from(new Set(commits.map(c => c.repo)));
    const system =
      `You are Gitbuddy, a personal GitHub work assistant for @${username}. ` +
      `Be friendly, concise and specific. Max 200 words.`;
    const user =
      `ACTIVE REPOS: ${repos.join(", ")}\nRECENT COMMITS:\n` +
      commits.slice(0, 25).map(c => `  [${c.repo}] ${c.message}  (${c.date})`).join("\n") +
      `\n\nQUESTION: ${question}`;
    return askCopilot(resolved.model, system, user);
  }
  if (resolved.provider === "groq" && resolved.groqKey) {
    return groq.answerQuestion(
      { apiKey: resolved.groqKey, model: currentModel() }, username, memory, question, commits,
    );
  }
  throw new Error("No language model available.");
}

/** Human-readable, for the menu. */
export function providerLabel(p: Provider): string {
  return p === "copilot" ? "GitHub Copilot"
       : p === "groq"    ? "Groq"
       : "built-in (no AI needed)";
}
