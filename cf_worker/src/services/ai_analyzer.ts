import type { Env } from "../types";
import { log } from "../utils/logger";

interface PendingItem {
  id: number;
  title: string | null;
  url: string | null;
  raw_summary: string | null;
  full_text: string | null;
}

interface AnalysisResult {
  impact_score: number;
  impact_rationale: string;
  action_items_json: string[];
  target_role: "developer" | "pm" | "founder" | "other";
}

const MODEL = "@cf/meta/llama-3.1-8b-instruct";

const SYSTEM_PROMPT = [
  "You are a strict JSON generator for AI news impact analysis.",
  "Return ONLY a valid JSON object with exactly these keys:",
  "impact_score (integer 1-5), impact_rationale (1-2 sentences),",
  "action_items_json (array of 2-3 short strings),",
  "target_role (developer | pm | founder | other).",
  "No markdown, no code fences, no extra keys, no commentary."
].join(" ");

function buildUserPrompt(item: PendingItem): string {
  const title = item.title ?? "";
  const url = item.url ?? "";
  const summary = item.raw_summary ?? "";
  const fullText = item.full_text ?? "";
  const body = fullText.trim() ? fullText : summary;
  return [
    `Title: ${title}`,
    `URL: ${url}`,
    `Summary: ${summary}`,
    `FullText: ${body}`
  ].join("\n");
}

function extractJson(text: string): string {
  let cleaned = text.trim();
  cleaned = cleaned.replace(/^```(json)?/i, "").replace(/```$/i, "").trim();
  const start = cleaned.indexOf("{");
  const end = cleaned.lastIndexOf("}");
  if (start >= 0 && end > start) {
    return cleaned.slice(start, end + 1).trim();
  }
  return cleaned;
}

function normalizeResult(payload: AnalysisResult): AnalysisResult {
  let score = Number(payload.impact_score);
  if (!Number.isFinite(score)) {
    score = 3;
  }
  score = Math.max(1, Math.min(5, Math.round(score)));

  const rationale = String(payload.impact_rationale || "").trim();

  let actions = Array.isArray(payload.action_items_json) ? payload.action_items_json : [];
  actions = actions.map((item) => String(item).trim()).filter(Boolean);
  if (actions.length > 3) {
    actions = actions.slice(0, 3);
  }

  const roleRaw = String(payload.target_role || "").toLowerCase().trim();
  const allowed = new Set(["developer", "pm", "founder", "other"]);
  const role = (allowed.has(roleRaw) ? roleRaw : "other") as AnalysisResult["target_role"];

  return {
    impact_score: score,
    impact_rationale: rationale,
    action_items_json: actions,
    target_role: role
  };
}

async function analyzeItem(env: Env, item: PendingItem): Promise<AnalysisResult | null> {
  const prompt = buildUserPrompt(item);
  try {
    const response = await env.AI.run(MODEL, {
      messages: [
        { role: "system", content: SYSTEM_PROMPT },
        { role: "user", content: prompt }
      ],
      temperature: 0.2,
      max_tokens: 350
    });
    const raw = response?.response ?? response?.result ?? response;
    const jsonText = extractJson(typeof raw === "string" ? raw : JSON.stringify(raw));
    const parsed = JSON.parse(jsonText) as AnalysisResult;
    return normalizeResult(parsed);
  } catch (error) {
    log.warn("ai_analyze_failed", { id: item.id, error: String(error) });
    return null;
  }
}

export async function analyzePendingItems(env: Env, limit = 5): Promise<{ processed: number; updated: number }> {
  if (!env.AI) {
    log.warn("ai_binding_missing");
    return { processed: 0, updated: 0 };
  }

  const query = env.DB.prepare(
    "SELECT id, title, url, raw_summary, full_text " +
      "FROM items WHERE impact_score IS NULL " +
      "ORDER BY COALESCE(published_at, created_at) DESC, id DESC LIMIT ?"
  );
  const result = await query.bind(limit).all<PendingItem>();
  const items = result.results ?? [];
  let updated = 0;

  for (const item of items) {
    const analysis = await analyzeItem(env, item);
    if (!analysis) {
      continue;
    }
    await env.DB.prepare(
      "UPDATE items SET impact_score=?, impact_rationale=?, action_items_json=?, target_role=? WHERE id=?"
    )
      .bind(
        analysis.impact_score,
        analysis.impact_rationale,
        JSON.stringify(analysis.action_items_json),
        analysis.target_role,
        item.id
      )
      .run();
    updated += 1;
  }

  log.info("ai_analyze_done", { processed: items.length, updated });
  return { processed: items.length, updated };
}
