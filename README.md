# Pokémon Drop Hunter

UK Pokémon Trading Card Game availability monitoring prototype. Tracks selected retailer product pages, looks for confidently purchasable stock, and can email **URGENT — POKÉMON DROP LIVE NOW** without any additional 10-minute delay. If an exact launch time is verified, a separate **10-minute warning** can be triggered.

**Status: prototype. Not production-validated. Email delivery is disabled by default.**

## Features

- Configurable product watchlist (HTTPS URLs only).
- Low-rate polling (120 seconds plus jitter by default; minimum 60 seconds).
- Respects robots.txt; does not bypass CAPTCHA, bot protection, login or invite-only sales.
- Two consecutive positive checks before urgent email; two negative checks reset the restock trigger.
- Duplicate-alert suppression (30-minute cooldown), persisted state, SMTP email with direct retailer links.
- Unknown, restricted and rate-limited pages do not trigger stock claims.
- Exact verified `verified_drop_at` ISO 8601 timestamp can trigger a 10-minute-before alert.
- Seven unit tests in GitHub Actions.

## Deployment

This worker is intended for a **single-instance always-on service** with persistent state. See [DEPLOY.md](DEPLOY.md). Configure environment variables from [.env.example](.env.example) using hosting provider secrets, never commit credentials.

The daily email digest is a separate scheduled ChatGPT automation, not part of this worker.

**Important:** Watchlist pages and selectors have not yet been calibrated against retailer live purchase flows. Running the service does not by itself guarantee accurate availability or immediate email delivery. The 2-minute sweep plus a second confirmation can introduce several minutes' delay.
