import type { NewsItem } from "../services/news";
import type { Labels } from "./i18n";

export function escapeHtml(input: string): string {
  return input
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function stripCodeBlocks(text: string): string {
  return text.replace(/```[\s\S]*?```/g, "");
}

function sanitizeText(text: string, maxLen: number): string {
  const cleaned = stripCodeBlocks(text).replace(/\s+/g, " ").trim();
  if (cleaned.length > maxLen) {
    return cleaned.slice(0, maxLen).trim();
  }
  return cleaned;
}

export function parseActionItems(raw: string | null | undefined): string[] {
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed.map((item) => String(item));
    }
  } catch (_) {
    return [];
  }
  return [];
}

export function formatItemMessage(
  item: NewsItem,
  labels: Labels,
  overrides?: { title?: string; rationale?: string; actions?: string[] }
): string {
  const title = escapeHtml(sanitizeText(overrides?.title ?? item.title ?? labels.noTitle, 140));
  const rationale = escapeHtml(
    sanitizeText(overrides?.rationale ?? item.impact_rationale ?? labels.noRationale, 360)
  );
  const rawScore = item.impact_score ?? 1;
  const impactScore = Math.min(5, Math.max(1, Math.round(rawScore)));
  const actions = (overrides?.actions ?? parseActionItems(item.action_items_json))
    .map((action) => sanitizeText(action, 140))
    .filter((action) => action.length > 0)
    .slice(0, 4);
  const actionsBlock = actions.length
    ? actions.map((action) => `• ${escapeHtml(action)}`).join("\n")
    : `• ${labels.noActions}`;

  return [
    `<b>${title}</b>`,
    `<b>${labels.impact}:</b> ${impactScore}/5`,
    `<b>${labels.why}:</b> ${rationale}`,
    `<b>${labels.actions}:</b>`,
    actionsBlock,
    `<a href="${escapeHtml(item.url ?? "")}">${labels.source}</a>`
  ].join("\n");
}
