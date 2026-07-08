# Cloudflare Deployment Notes (Legacy)

This file is historical context from the Python `aiogram` period.

## Current Truth
- The current production bot is the Cloudflare Worker in `cf_worker/`.
- The current deploy guide is `cf_worker/DEPLOY.md`.
- The current runtime uses TypeScript + `grammy` + D1, not Python `aiogram`.

## Why this file still exists
- It explains why the old Python bot could not be deployed to Workers.
- It should not be used as the current release or deploy instruction.

## Historical Note
- The earlier bot was built with Python + `aiogram`.
- Cloudflare Workers does not support that stack directly, which is why the
  project was ported to a Workers-compatible runtime.
