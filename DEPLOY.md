# Deployment instructions — Railway

1. Connect this GitHub repository to Railway and deploy a Docker-backed **always-on background worker**. The Dockerfile executes `python -u monitor.py`.
2. Use **one replica**. Set environment variables `POLL_SECONDS=120`, `DATA_DIR=/data`, `WATCHLIST_PATH=watchlist.json`, `EMAIL_ENABLED=false`, and `EMAIL_TO` to the recipient's address. Use Railway protected variables, not source files.
3. Attach a persistent Railway volume mounted at `/data`. Without it, duplicate-suppression history may vanish at restart.
4. Inspect logs. Pages blocked by robots.txt, CAPTCHAs, 403/429 responses or invitation gates must remain restricted. Do not circumvent controls.
5. Create and verify site-specific stock adapters/allowed sources for every retailer in the watchlist. Run controlled unavailable-to-available tests before production email.
6. Add Brevo transactional API credentials securely (`BREVO_API_KEY` and `BREVO_SENDER`) for a verified sender; this worker does not require Gmail SMTP or Gmail App Passwords.
7. Only after a successful end-to-end alert test change `EMAIL_ENABLED=true`.

Daily digests are handled by a separate ChatGPT automation and are not part of this Docker worker. Watchlist entries must use product-level URLs, and exact launch times must be verified before setting `verified_drop_at`.

## Free hosting option: GitHub Actions

Use [Free Pokemon Stock Watch](.github/workflows/stock-watch-free.yml) instead of Railway. See README for configuring GitHub repository secrets. The scheduled scans are best-effort and may be delayed. Do not activate emails until website stock parsing has been verified.

The GitHub Action is dry-run by default, even after secrets are added. Set repository Actions variable `POKEMON_ENABLE_EMAIL=true` only once all product-page stock detections are verified.

For GitHub Actions and the optional Railway Docker worker, use the Brevo API sender setup in README.md. Email is disabled by default.
