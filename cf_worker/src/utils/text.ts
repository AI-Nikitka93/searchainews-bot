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

export function stripCitationArtifacts(text: string): string {
  if (!text) return "";
  return text
    .replace(/【[^】]*】/g, "")
    .replace(/\[\^[\w-]+\]/g, "")
    .replace(/(?:\[\s*\d+(?:\s*[,;–—\-]\s*\d+)*\s*\])+/g, "")
    .replace(/\[(?:citation\s+needed|источник(?:\s+не\s+указан)?)\]/gi, "")
    .replace(/\s+([.,!?;:])/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

export function limitSentences(text: string, maxSentences = 2): string {
  if (!text) return "";
  const cleaned = stripCitationArtifacts(text).replace(/\s+/g, " ").trim();
  const parts = cleaned.split(/(?<=[.!?…])\s+/).filter(Boolean);
  const validSentences = parts
    .map((p) => p.trim())
    .filter((p) => /[.!?…]["»\']?$/.test(p));

  if (validSentences.length > 0) {
    return validSentences.slice(0, maxSentences).join(" ");
  }

  if (parts.length > 0) {
    return parts[0].trim().replace(/[,;:\-–—\s]+$/, "") + ".";
  }
  return cleaned;
}

export function sanitizeText(text: string, maxLen: number, appendEllipsis = true): string {
  const cleaned = stripCitationArtifacts(stripCodeBlocks(text)).replace(/\s+/g, " ").trim();
  if (cleaned.length <= maxLen) {
    return cleaned;
  }
  const sliceLen = appendEllipsis ? Math.max(1, maxLen - 1) : maxLen;
  const head = cleaned.slice(0, sliceLen);
  const lastSpace = head.lastIndexOf(" ");
  const cutoff = lastSpace > 0 ? lastSpace : sliceLen;
  const trimmed = head.slice(0, cutoff).replace(/[,;:\-–—\s]+$/, "").trim();
  return appendEllipsis ? `${trimmed}…` : trimmed;
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
  const title = escapeHtml(sanitizeText(overrides?.title ?? item.title ?? labels.noTitle, 140, true));
  const rawRationale = overrides?.rationale ?? item.impact_rationale ?? labels.noRationale;
  const sentenceRationale = limitSentences(rawRationale, 3);
  const rationale = escapeHtml(
    sentenceRationale.length <= 360
      ? sentenceRationale
      : sanitizeText(sentenceRationale, 360, true)
  );
  const rawScore = item.impact_score ?? 1;
  const impactScore = Math.min(5, Math.max(1, Math.round(rawScore)));
  const actions = (overrides?.actions ?? parseActionItems(item.action_items_json))
    .map((action) => sanitizeText(action, 140, false))
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
