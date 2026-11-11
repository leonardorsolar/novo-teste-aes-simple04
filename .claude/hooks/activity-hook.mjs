#!/usr/bin/env node
// Hook do Claude Code: registra o que a sessão faz no feed da página Activity (.aes/activity.json).
// Uso (em .claude/settings.json):  node scripts/activity-hook.mjs <SessionStart|Stop|PostToolUse>
// Lê o JSON do hook no stdin. Nunca falha nem imprime nada: um hook com erro não pode atrapalhar a sessão.
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { dirname, join, relative, isAbsolute } from "node:path";

const MAX = 500;          // mesmo limite de js/activity.js
const DEDUPE_MS = 60_000; // mesma edição de arquivo em menos de 1 min não vira outro evento
const ACTOR = "Claude";

function readStdin() {
  try { return JSON.parse(readFileSync(0, "utf8") || "{}"); } catch { return {}; }
}

function shorten(text, n = 140) {
  const t = String(text || "").replace(/\s+/g, " ").trim();
  return t.length > n ? t.slice(0, n - 1) + "…" : t;
}

// Última resposta do assistente no transcript (JSONL), para usar de resumo no "Stop".
function lastAssistantText(transcriptPath) {
  try {
    const lines = readFileSync(transcriptPath, "utf8").trim().split("\n");
    for (let i = lines.length - 1; i >= 0; i--) {
      const row = JSON.parse(lines[i]);
      const msg = row.message;
      if (row.type !== "assistant" || !msg || !Array.isArray(msg.content)) continue;
      const text = msg.content.filter((c) => c.type === "text").map((c) => c.text).join(" ");
      if (text.trim()) return shorten(text);
    }
  } catch { /* sem resumo */ }
  return undefined;
}

function buildEvent(kind, input, root) {
  if (kind === "SessionStart") {
    return { action: "claude.session_started", title: input.source || "", summary: undefined };
  }
  if (kind === "Stop") {
    return { action: "claude.responded", title: "", summary: lastAssistantText(input.transcript_path) };
  }
  if (kind === "PostToolUse") {
    const tool = input.tool_name;
    const ti = input.tool_input || {};
    if (tool === "Edit" || tool === "Write" || tool === "MultiEdit") {
      const file = ti.file_path;
      if (!file) return null;
      const rel = isAbsolute(file) ? relative(root, file) : file;
      if (rel.startsWith("..") || rel.startsWith(".aes/activity.json")) return null; // fora do projeto ou o próprio feed
      return { action: tool === "Write" ? "claude.file_written" : "claude.file_edited", title: rel, summary: undefined };
    }
    if (tool === "Bash" && /\bgit\s+commit\b/.test(String(ti.command || ""))) {
      let subject = "";
      try { subject = execFileSync("git", ["log", "-1", "--pretty=%s"], { cwd: root, encoding: "utf8", timeout: 3000 }).trim(); } catch { /* ignora */ }
      return { action: "claude.committed", title: shorten(subject, 100), summary: undefined };
    }
  }
  return null;
}

function main() {
  const kind = process.argv[2];
  const input = readStdin();
  const root = process.env.CLAUDE_PROJECT_DIR || input.cwd || process.cwd();
  const built = buildEvent(kind, input, root);
  if (!built) return;

  const file = join(root, ".aes", "activity.json");
  let events = [];
  try {
    const data = JSON.parse(readFileSync(file, "utf8"));
    if (Array.isArray(data.events)) events = data.events;
  } catch { /* arquivo ainda não existe */ }

  const now = Date.now();
  const dup = events.find((e) => e.action === built.action && e.title === built.title && e.actor === ACTOR
    && now - Date.parse(e.timestamp) < DEDUPE_MS && built.action.startsWith("claude.file_"));
  if (dup) return;

  const ev = { id: randomUUID(), kind: "deed", action: built.action, title: built.title, actor: ACTOR, timestamp: new Date(now).toISOString() };
  if (built.summary) ev.summary = built.summary;
  events = [ev, ...events].slice(0, MAX);

  mkdirSync(dirname(file), { recursive: true });
  const tmp = file + "." + process.pid + ".tmp";
  writeFileSync(tmp, JSON.stringify({ version: 1, events }, null, 2));
  renameSync(tmp, file); // troca atômica: o navegador nunca lê o arquivo pela metade
}

try { main(); } catch { /* nunca atrapalha a sessão */ }
process.exit(0);
