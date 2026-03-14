# Cloudflare Deployment Notes (Telegram Bot)

## Status
- The current bot is built with Python + aiogram.
- Cloudflare Workers does NOT support running aiogram or aiohttp.
- For 24/7 free Cloudflare hosting, the bot must be ported to a Workers-compatible stack (TypeScript + grammy + D1).

## Recommended Cloudflare Stack (Free)
- Cloudflare Workers (webhook-only)
- D1 for storage
- grammy for Telegram

## What must be re-implemented
1. Webhook handler (no polling).
2. Users table in D1.
3. /start, role selection, /latest commands.
4. Broadcaster via Cron Trigger or Queue consumer.

## Why this is required
Cloudflare Workers runs JS/TS (and limited Python Workers) and does not allow installing aiogram dependencies.
