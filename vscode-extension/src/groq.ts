import { loadSettingsJson } from "./env";

export interface GroqOpts {
  apiKey: string;
  model?: string;
}

const DEFAULT_MODEL = "llama-3.3-70b-versatile";

async function chat(opts: GroqOpts, system: string, user: string, maxTokens = 1024): Promise<string> {
  const model = opts.model || DEFAULT_MODEL;
  const res = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${opts.apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model,
      messages: [
        { role: "system", content: system },
        { role: "user",   content: user },
      ],
      max_tokens: maxTokens,
      temperature: 0.7,
    }),
  });
  if (!res.ok) throw new Error(`Groq ${res.status}: ${await res.text()}`);
  const data: any = await res.json();
  return (data.choices?.[0]?.message?.content ?? "").trim();
}

export function modelFromSettings(projectRoot: string): string {
  const s = loadSettingsJson(projectRoot);
  return (s.groq_model as string) || DEFAULT_MODEL;
}

function commitsStr(commits: Array<{ repo: string; message: string; date: string }>, n = 25): string {
  if (!commits.length) return "  No commits found.";
  return commits.slice(0, n).map(c => `  [${c.repo}] ${c.message}  (${c.date})`).join("\n");
}

function baseSystem(username: string, memory: Record<string, string>): string {
  const mem = Object.entries(memory).map(([k, v]) => `  ${k}: ${v}`).join("\n");
  const memBlock = mem ? `\nKnown context about this developer:\n${mem}` : "";
  return `You are Gitlane, a personal GitHub work assistant for @${username}.
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
