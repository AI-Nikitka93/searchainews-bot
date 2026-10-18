import type { Env } from "../types";
import { log } from "../utils/logger";
import { upsertItems } from "./ingest";
import type { IngestItem } from "./ingest";

interface EdgeFeed {
  id: string;
  name: string;
  url: string;
  fallbackUrl?: string;
  maxItems: number;
}

const EDGE_FEEDS: EdgeFeed[] = [
  {
    id: "huggingface_blog",
    name: "Hugging Face Blog",
    url: "https://huggingface.co/blog/feed.xml",
    maxItems: 8
  },
  {
    id: "huggingface_trending",
    name: "Hugging Face Trending",
    url: "https://zernel.github.io/huggingface-trending-feed/feed.xml",
    maxItems: 8
  },
  {
    id: "huggingface_daily_papers",
    name: "Hugging Face Daily Papers",
    url: "https://raw.githubusercontent.com/huangboming/huggingface-daily-paper-feed/refs/heads/main/feed.xml",
    maxItems: 8
  },
  {
    id: "openai_news",
    name: "OpenAI News",
    url: "https://openai.com/news/rss.xml",
    maxItems: 8
  },
  {
    id: "simon_willison_ai",
    name: "Simon Willison AI",
    url: "https://simonwillison.net/tags/ai.atom",
    maxItems: 8
  },
  {
    id: "ahead_of_ai",
    name: "Ahead of AI (Sebastian Raschka)",
    url: "https://magazine.sebastianraschka.com/feed",
    maxItems: 6
  },
  {
    id: "import_ai",
    name: "Import AI (Jack Clark)",
    url: "https://importai.net/feed",
    maxItems: 6
  },
  {
    id: "turing_post",
    name: "Turing Post",
    url: "https://turingpost.substack.com/feed",
    maxItems: 6
  },
  {
    id: "bair_blog",
    name: "Berkeley BAIR Blog",
    url: "https://bair.berkeley.edu/blog/feed.xml",
    fallbackUrl: "https://bairblog.github.io/feed.xml",
    maxItems: 6
  },
  {
    id: "arxiv_cs_ai",
    name: "ArXiv cs.AI",
    url: "https://rss.arxiv.org/rss/cs.ai",
    maxItems: 10
  },
  {
    id: "arxiv_cs_lg",
    name: "ArXiv cs.LG",
    url: "https://rss.arxiv.org/rss/cs.lg",
    maxItems: 10
  }
];

function unescapeXml(text: string): string {
  return text
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#x2F;/g, "/")
    .replace(/&#(\d+);/g, (_, code) => String.fromCharCode(Number(code)));
}

function stripHtml(html: string): string {
  const unwrapped = html.replace(/<!\[CDATA\[([\s\S]*?)\]\]>/gi, "$1");
  const withoutTags = unwrapped.replace(/<[^>]*>/g, " ");
  return unescapeXml(withoutTags).replace(/\s+/g, " ").trim();
}

function parseFeedItems(xmlText: string, feed: EdgeFeed): IngestItem[] {
  const items: IngestItem[] = [];

  // Determine if RSS (<item>) or Atom (<entry>)
  const isAtom = xmlText.includes("<entry") && !xmlText.includes("<item");
  const blockRegex = isAtom
    ? /<entry[\s\S]*?<\/entry>/gi
    : /<item[\s\S]*?<\/item>/gi;

  const matches = xmlText.match(blockRegex) || [];
  const cutoffTime = Date.now() - 48 * 60 * 60 * 1000; // 48 hours

  for (const block of matches) {
    if (items.length >= feed.maxItems) {
      break;
    }

    // Title
    const titleMatch = block.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
    let title = titleMatch ? stripHtml(titleMatch[1]) : "";
    if (!title) {
      continue;
    }

    // Link
    let url = "";
    if (isAtom) {
      const hrefMatch = block.match(/<link[^>]*href=["']([^"']+)["']/i);
      if (hrefMatch) {
        url = hrefMatch[1].trim();
      }
    }
    if (!url) {
      const linkMatch = block.match(/<link[^>]*>([\s\S]*?)<\/link>/i);
      if (linkMatch) {
        url = stripHtml(linkMatch[1]);
      }
    }
    if (!url) {
      const guidMatch = block.match(/<guid[^>]*>([\s\S]*?)<\/guid>/i) || block.match(/<id[^>]*>([\s\S]*?)<\/id>/i);
      if (guidMatch) {
        const candidate = stripHtml(guidMatch[1]);
        if (candidate.startsWith("http://") || candidate.startsWith("https://")) {
          url = candidate;
        }
      }
    }
    if (!url || (!url.startsWith("http://") && !url.startsWith("https://"))) {
      continue;
    }

    // Published date
    const dateMatch =
      block.match(/<pubDate[^>]*>([\s\S]*?)<\/pubDate>/i) ||
      block.match(/<published[^>]*>([\s\S]*?)<\/published>/i) ||
      block.match(/<updated[^>]*>([\s\S]*?)<\/updated>/i) ||
      block.match(/<dc:date[^>]*>([\s\S]*?)<\/dc:date>/i);

    let publishedAt = new Date().toISOString();
    if (dateMatch) {
      const parsedDate = new Date(stripHtml(dateMatch[1]));
      if (!isNaN(parsedDate.getTime())) {
        if (parsedDate.getTime() < cutoffTime) {
          // Skip items older than 48 hours
          continue;
        }
        publishedAt = parsedDate.toISOString();
      }
    }

    // Summary / Description
    const summaryMatch =
      block.match(/<description[^>]*>([\s\S]*?)<\/description>/i) ||
      block.match(/<summary[^>]*>([\s\S]*?)<\/summary>/i) ||
      block.match(/<content[^>]*>([\s\S]*?)<\/content>/i);

    let rawSummary = summaryMatch ? stripHtml(summaryMatch[1]) : "";
    if (rawSummary.length > 800) {
      rawSummary = rawSummary.slice(0, 800) + "...";
    }

    items.push({
      source_id: feed.id,
      title,
      url,
      raw_summary: rawSummary || title,
      published_at: publishedAt
    });
  }

  return items;
}

export async function runEdgeScraper(env: Env): Promise<{ feedsProcessed: number; itemsSaved: number }> {
  if (env.ENABLE_EDGE_SCRAPER === "false") {
    log.info("edge_scraper_disabled");
    return { feedsProcessed: 0, itemsSaved: 0 };
  }

  const start = Date.now();
  let totalSaved = 0;
  let feedsProcessed = 0;

  for (const feed of EDGE_FEEDS) {
    try {
      const headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, text/html;q=0.9, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
      };

      let response: Response;
      try {
        response = await fetch(feed.url, {
          headers,
          signal: AbortSignal.timeout(6000)
        });
      } catch (primaryErr: unknown) {
        if (feed.fallbackUrl) {
          log.warn("edge_scrape_feed_primary_failed_trying_fallback", { feed: feed.id, error: String(primaryErr) });
          response = await fetch(feed.fallbackUrl, {
            headers,
            signal: AbortSignal.timeout(6000)
          });
        } else {
          throw primaryErr;
        }
      }

      if (!response.ok && feed.fallbackUrl) {
        log.warn("edge_scrape_feed_http_error_trying_fallback", { feed: feed.id, status: response.status });
        response = await fetch(feed.fallbackUrl, {
          headers,
          signal: AbortSignal.timeout(6000)
        });
      }

      if (!response.ok) {
        log.warn("edge_scrape_feed_http_error", { feed: feed.id, status: response.status });
        continue;
      }

      const xmlText = await response.text();
      const parsedItems = parseFeedItems(xmlText, feed);

      if (parsedItems.length > 0) {
        const saved = await upsertItems(env, parsedItems);
        totalSaved += saved;
      }

      feedsProcessed += 1;
    } catch (e: unknown) {
      log.warn("edge_scrape_feed_failed", { feed: feed.id, error: String(e) });
    }
  }

  log.info("edge_scrape_complete", {
    feedsProcessed,
    totalSaved,
    duration_ms: Date.now() - start
  });

  return { feedsProcessed, itemsSaved: totalSaved };
}
