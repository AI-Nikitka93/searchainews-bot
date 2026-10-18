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
  target_role:
    | "ai_specialist"
    | "ai_developer"
    | "ai_enthusiast"
    | "ai_beginner"
    | "developer"
    | "pm"
    | "founder"
    | "other";
}

const CF_MODEL = "@cf/meta/llama-3.1-8b-instruct";

const SYSTEM_PROMPT = [
  "You are an expert AI technology analyst.",
  "Evaluate developer/engineering impact for AI engineers, founders, and ML practitioners.",
  "Return strictly a single valid JSON object with EXACTLY these keys:",
  "{\"impact_score\": <integer 1-5>,",
  "\"impact_rationale\": \"<2-3 concise Russian sentences explaining practical importance, tech advances, or production relevance>\",",
  "\"action_items_json\": [\"<actionable Russian item 1>\", \"<actionable Russian item 2>\"],",
  "\"target_role\": \"<ai_specialist|ai_developer|ai_enthusiast|ai_beginner|developer|pm|founder|other>\"}",
  "Do not output markdown code fences, do not output reasoning, only raw JSON."
].join(" ");

function buildUserPrompt(item: PendingItem): string {
  const title = item.title ?? "";
  const url = item.url ?? "";
  const summary = item.raw_summary ?? "";
  const fullText = item.full_text ?? "";
  const body = fullText.trim() ? fullText.slice(0, 3000) : summary.slice(0, 1500);
  return [
    `Title: ${title}`,
    `URL: ${url}`,
    `Content: ${body}`
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

function normalizeResult(payload: any): AnalysisResult {
  let score = Number(payload.impact_score);
  if (!Number.isFinite(score)) {
    score = 3;
  }
  score = Math.max(1, Math.min(5, Math.round(score)));

  const rationale = String(payload.impact_rationale || "").trim();

  let actions: string[] = [];
  if (Array.isArray(payload.action_items_json)) {
    actions = payload.action_items_json;
  } else if (typeof payload.action_items_json === "string") {
    try {
      const parsed = JSON.parse(payload.action_items_json);
      if (Array.isArray(parsed)) actions = parsed;
    } catch {
      actions = [payload.action_items_json];
    }
  }
  actions = actions.map((item) => String(item).trim()).filter(Boolean);
  if (actions.length > 3) {
    actions = actions.slice(0, 3);
  }

  const roleRaw = String(payload.target_role || "").toLowerCase().trim();
  const allowed = new Set([
    "ai_specialist",
    "ai_developer",
    "ai_enthusiast",
    "ai_beginner",
    "developer",
    "pm",
    "founder",
    "other"
  ]);
  const role = (allowed.has(roleRaw) ? roleRaw : "other") as AnalysisResult["target_role"];

  return {
    impact_score: score,
    impact_rationale: rationale,
    action_items_json: actions,
    target_role: role
  };
}

async function callChatCompletions(
  baseUrl: string,
  apiKey: string | null,
  model: string,
  userPrompt: string,
  jsonMode = false
): Promise<string | null> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const cleanKey = apiKey ? apiKey.trim().replace(/[\r\n]+/g, "") : null;
  if (cleanKey) {
    headers["Authorization"] = `Bearer ${cleanKey}`;
  }

  const body: Record<string, unknown> = {
    model,
    temperature: 0.2,
    max_tokens: 600,
    messages: [
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: userPrompt }
    ]
  };

  if (jsonMode) {
    body["response_format"] = { type: "json_object" };
  }

  const response = await fetch(`${baseUrl}/chat/completions`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(12000)
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    throw new Error(`HTTP ${response.status} from ${baseUrl}: ${errorText}`);
  }

  const data = (await response.json()) as {
    choices?: Array<{ message?: { content?: string } }>;
  };
  return data?.choices?.[0]?.message?.content?.trim() || null;
}

async function analyzeItem(env: Env, item: PendingItem): Promise<AnalysisResult | null> {
  const prompt = buildUserPrompt(item);
  const start = Date.now();

  // Tier 1: Groq multi-key fallback cascade
  const groqKeys: string[] = [];
  if (env.GROQ_API_KEYS) {
    groqKeys.push(...env.GROQ_API_KEYS.split(",").map((k) => k.trim()).filter(Boolean));
  }
  if (env.GROQ_API_KEY && !groqKeys.includes(env.GROQ_API_KEY)) {
    groqKeys.unshift(env.GROQ_API_KEY);
  }

  const groqBaseUrl = env.GROQ_BASE_URL || "https://api.groq.com/openai/v1";
  const groqModels = [
    env.GROQ_MODEL || "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b"
  ];

  for (const key of groqKeys) {
    for (const model of groqModels) {
      try {
        const raw = await callChatCompletions(groqBaseUrl, key, model, prompt, true);
        if (raw) {
          const jsonText = extractJson(raw);
          const parsed = JSON.parse(jsonText);
          const result = normalizeResult(parsed);
          log.info("ai_analyze_success", {
            id: item.id,
            provider: "groq",
            model,
            duration_ms: Date.now() - start
          });
          return result;
        }
      } catch (err: unknown) {
        log.warn("groq_analyze_attempt_failed", {
          model,
          keyPrefix: key.slice(0, 8),
          error: String(err)
        });
      }
    }
  }

  // Tier 2: OpenRouter API
  if (env.OPENROUTER_API_KEY) {
    const orBaseUrl = env.OPENROUTER_BASE_URL || "https://openrouter.ai/api/v1";
    const orModels = [
      env.OPENROUTER_MODEL || "openrouter/free",
      "meta-llama/llama-3.3-70b-instruct:free",
      "liquid/lfm-7b"
    ];

    for (const model of orModels) {
      try {
        const raw = await callChatCompletions(orBaseUrl, env.OPENROUTER_API_KEY, model, prompt, false);
        if (raw) {
          const jsonText = extractJson(raw);
          const parsed = JSON.parse(jsonText);
          const result = normalizeResult(parsed);
          log.info("ai_analyze_success", {
            id: item.id,
            provider: "openrouter",
            model,
            duration_ms: Date.now() - start
          });
          return result;
        }
      } catch (err: unknown) {
        log.warn("openrouter_analyze_attempt_failed", { model, error: String(err) });
      }
    }
  }

  // Tier 3: Cloudflare Workers AI
  if (env.AI) {
    try {
      const response = await (env.AI as any).run(CF_MODEL, {
        messages: [
          { role: "system", content: SYSTEM_PROMPT },
          { role: "user", content: prompt }
        ],
        temperature: 0.2,
        max_tokens: 450
      });
      const rawPayload = response as { response?: string; result?: string } | string;
      const raw =
        typeof rawPayload === "string" ? rawPayload : rawPayload?.response ?? rawPayload?.result ?? response;
      const jsonText = extractJson(typeof raw === "string" ? raw : JSON.stringify(raw));
      const parsed = JSON.parse(jsonText);
      const result = normalizeResult(parsed);
      log.info("ai_analyze_success", {
        id: item.id,
        provider: "cloudflare_ai",
        duration_ms: Date.now() - start
      });
      return result;
    } catch (error: unknown) {
      log.warn("cf_ai_analyze_failed", { id: item.id, error: String(error) });
    }
  }

  // Tier 4: Pollinations.ai (Keyless safety net)
  try {
    const raw = await callChatCompletions(
      "https://text.pollinations.ai/openai",
      null,
      "openai-fast",
      prompt,
      false
    );
    if (raw) {
      const jsonText = extractJson(raw);
      const parsed = JSON.parse(jsonText);
      const result = normalizeResult(parsed);
      log.info("ai_analyze_success", {
        id: item.id,
        provider: "pollinations",
        duration_ms: Date.now() - start
      });
      return result;
    }
  } catch (error: unknown) {
    log.warn("pollinations_analyze_failed", { id: item.id, error: String(error) });
  }

  return null;
}

export async function analyzePendingItems(
  env: Env,
  limit = 5
): Promise<{ processed: number; updated: number }> {
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
