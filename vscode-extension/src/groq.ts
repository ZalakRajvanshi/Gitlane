import * as vscode from "vscode";
import { linkedProjectRoot, loadSettingsJson } from "./env";

export interface GroqOpts {
  apiKey: string;
  model?: string;
}

/**
 * Groq decommissioned the whole Llama line — `llama-3.3-70b-versatile` and
 * `llama3-70b-8192` both 404 / 400 now. Everything still served is a
 * reasoning model, which changes how we have to call the API (see below).
 */
const DEFAULT_MODEL = "openai/gpt-oss-120b";

/**
 * Reasoning tokens are billed against the same completion budget as the
 * answer, so an 80-token cap gets spent entirely on thinking and `content`
 * comes back as an empty string. Each family spells the "think less" knob
 * differently — gpt-oss wants low|medium|high, qwen wants none|default, and
 * the compound models reject the field outright — so map it per model and
 * omit it for anything we don't recognise.
 */
function reasoningEffortFor(model: string): string | undefined {
  if (model.startsWith("openai/gpt-oss")) return "low";
  if (model.startsWith("qwen/")) return "none";
  return undefined;
}

/** Belt and braces: some models narrate in <think> tags inside `content`. */
function stripThinking(text: string): string {
  return text
    .replace(/<think>[\s\S]*?<\/think>/gi, "")
    .replace(/<\/?think>/gi, "")
    .trim();
}

interface GroqResponse {
  status: number;
  body: any;
}

async function post(
  opts: GroqOpts,
  model: string,
  system: string,
  user: string,
  maxTokens: number,
  effort: string | undefined,
): Promise<GroqResponse> {
  const payload: Record<string, unknown> = {
    model,
    messages: [
      { role: "system", content: system },
      { role: "user",   content: user },
    ],
    // `max_tokens` is deprecated on Groq in favour of `max_completion_tokens`.
    max_completion_tokens: maxTokens,
    temperature: 0.7,
  };
  if (effort) payload.reasoning_effort = effort;

  const res = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${opts.apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const text = await res.text();
  let body: any;
  try { body = JSON.parse(text); } catch { body = { error: { message: text } }; }
  return { status: res.status, body };
}

async function chat(opts: GroqOpts, system: string, user: string, maxTokens = 1024): Promise<string> {
  const model  = opts.model || DEFAULT_MODEL;
  const effort = reasoningEffortFor(model);

  // Give the visible answer headroom on top of what the caller asked for —
  // the thinking has to fit in the same budget.
  const budget = Math.max(maxTokens + 512, 1024);

  let res = await post(opts, model, system, user, budget, effort);

  // A model we mis-classified rejects the knob by name. Retry once without it
  // rather than failing, so a newly-added Groq model still works.
  if (res.status === 400 && effort && String(res.body?.error?.message ?? "").includes("reasoning_effort")) {
    res = await post(opts, model, system, user, budget, undefined);
  }

  if (res.status !== 200) {
    const err  = res.body?.error ?? {};
    const code = err.code as string | undefined;
    if (code === "model_decommissioned" || code === "model_not_found") {
      throw new Error(
        `Groq no longer serves the model "${model}". ` +
        `Clear the "gitbuddy.model" setting to fall back to "${DEFAULT_MODEL}", ` +
        `or pick a current one from https://console.groq.com/docs/models`,
      );
    }
    throw new Error(`Groq ${res.status}: ${err.message ?? JSON.stringify(res.body)}`);
  }

  const choice  = res.body?.choices?.[0];
  const content = stripThinking(choice?.message?.content ?? "");

  // Ran out of budget mid-thought — an empty string here would silently land
  // in the commit box, so say what actually happened.
  if (!content) {
    if (choice?.finish_reason === "length") {
      throw new Error(
        `"${model}" spent its whole token budget reasoning and returned nothing. ` +
        `Try "${DEFAULT_MODEL}" in the "gitbuddy.model" setting.`,
      );
    }
    throw new Error(`Groq returned an empty response from "${model}".`);
  }
  return content;
}

/**
 * The VS Code setting wins; a linked Python project's settings.json is the
 * fallback so the CLI and the editor agree on one model. Stale Llama ids
 * from either source are upgraded rather than handed to a 404.
 */
export function currentModel(): string {
  const configured =
    vscode.workspace.getConfiguration().get<string>("gitbuddy.model", "").trim() ||
    fromLinkedProject();
  if (!configured || /^llama/i.test(configured)) return DEFAULT_MODEL;
  return configured;
}

function fromLinkedProject(): string {
  const linked = linkedProjectRoot();
  if (!linked) return "";
  return ((loadSettingsJson(linked).groq_model as string) || "").trim();
}

function commitsStr(commits: Array<{ repo: string; message: string; date: string }>, n = 25): string {
  if (!commits.length) return "  No commits found.";
  return commits.slice(0, n).map(c => `  [${c.repo}] ${c.message}  (${c.date})`).join("\n");
}

function baseSystem(username: string, memory: Record<string, string>): string {
  const mem = Object.entries(memory).map(([k, v]) => `  ${k}: ${v}`).join("\n");
  const memBlock = mem ? `\nKnown context about this developer:\n${mem}` : "";
  return `You are Gitbuddy, a personal GitHub work assistant for @${username}.
You help developers track their work, stay focused, and grow.
Be friendly, concise, and specific. Use plain text. Avoid jargon.
Never say "I don't have access" — work with what you know.${memBlock}`;
}

export async function generateCommitMessage(
  opts: GroqOpts,
  stagedFiles: string[],
  diff: string,
): Promise<string> {
  return chat(
    opts,
    "You write conventional git commit messages. Format: type(scope): description. Under 72 chars. Return ONLY the message.",
    `Staged files:\n${stagedFiles.map(f => `  ${f}`).join("\n")}\n\nDiff summary:\n${(diff || "Not available").slice(0, 800)}\n\nWrite one commit message.`,
    80,
  );
}

export async function answerQuestion(
  opts: GroqOpts,
  username: string,
  memory: Record<string, string>,
  question: string,
  commits: Array<{ repo: string; message: string; date: string }>,
): Promise<string> {
  const repos = Array.from(new Set(commits.map(c => c.repo)));
  return chat(
    opts,
    baseSystem(username, memory),
    `Answer this question about the developer's work.
Be specific and helpful. Max 200 words.

ACTIVE REPOS: ${repos.join(", ")}
RECENT COMMITS:
${commitsStr(commits)}

QUESTION: ${question}`,
  );
}

export async function summarizeWeek(
  opts: GroqOpts,
  username: string,
  memory: Record<string, string>,
  commits: Array<{ repo: string; message: string; date: string }>,
): Promise<string> {
  return chat(
    opts,
    baseSystem(username, memory),
    `Summarize this developer's work from the past 7 days in 150 words.
Cover: what they built, which projects got focus, any patterns.
End with one specific encouragement.

COMMITS:
${commitsStr(commits)}`,
  );
}
