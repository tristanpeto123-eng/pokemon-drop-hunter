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

## £0/month stock scanning with GitHub Actions

The [Free Pokemon Stock Watch](.github/workflows/stock-watch-free.yml) workflow schedules a scan every five minutes (UTC). Standard GitHub-hosted runners are free for public repositories. GitHub can delay or drop scheduled runs, so this is **best effort**, not guaranteed instantaneous stock monitoring.

The scanner makes a second positive check within 12 seconds, and writes alert history to the separate public `monitor-state` branch. Run it manually under **Actions → Free Pokemon Stock Watch → Run workflow**. Retailer robots.txt policies and access restrictions are respected.

**Email requires setup.** See [Brevo API sender instructions](#free-email-sender-brevo-api-no-gmail-app-password) below. Keep credentials in GitHub Secrets and validate the retailer's stock adapter before turning on real emails.

The separate ChatGPT daily-digest automation remains in place and unchanged.

**Safety switch:** Email stays in dry-run mode until the GitHub Actions variable `POKEMON_ENABLE_EMAIL` is explicitly set to `true` after successful retailer stock validation. The first observation establishes a baseline without sending a spurious 'new drop' alert. GitHub stores monitoring observations on a separate public `monitor-state` branch.

## Free email sender: Brevo API (no Gmail App Password)

The five-minute GitHub workflow uses Brevo's transactional email API at `https://api.brevo.com/v3/smtp/email`, **not** Gmail SMTP. Brevo's free plan currently includes up to 300 sends per day, subject to account approval and provider terms. You must create an account and set up a verified sending identity; if using a free Gmail address, Brevo may rewrite the outbound From address. Deliverability is not guaranteed.

1. Visit [Brevo](https://www.brevo.com/) and create a free account. Register/verify a sender under Settings → Senders, Domains, IPs. You can still receive Gmail messages normally. If Brevo requires a custom domain or refuses an unowned sender, you cannot bypass that requirement.
2. Generate a **transactional API key** under SMTP & API → API Keys. Do not use an SMTP key.
3. In this repository's Settings → Secrets and variables → Actions → Secrets, add `POKEMON_EMAIL_TO` (notification recipient), `POKEMON_BREVO_API_KEY` (API key) and `POKEMON_BREVO_SENDER` (exact Brevo-verified sender address). Never place keys in commit history, an issue, or chat.
4. Run **Actions → Test Brevo Email Delivery → Run workflow** to send one email with **[TEST]** in the subject. This manual test intentionally does not enable the stock-alert job.
5. After site-specific stock-detection checks are validated, set the repository Actions **variable** `POKEMON_ENABLE_EMAIL=true` to enable urgent notifications. Leave this unset until validation.

The stock-watch workflow remains in dry-run mode until its email enable variable is `true` and all three secrets exist. The daily digest is separately delivered through the connected ChatGPT Gmail automation; changing the urgent-alert sender does not automatically change the digest's sender.
