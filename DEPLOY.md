# Deployment instructions — Railway

1. Connect this GitHub repository to Railway and deploy a Docker-backed **always-on background worker**. The Dockerfile executes `python -u monitor.py`.
2. Use **one replica**. Set environment variables `POLL_SECONDS=120`, `DATA_DIR=/data`, `WATCHLIST_PATH=watchlist.json`, `EMAIL_ENABLED=false`, and `EMAIL_TO` to the recipient's address. Use Railway protected variables, not source files.
3. Attach a persistent Railway volume mounted at `/data`. Without it, duplicate-suppression history may vanish at restart.
4. Inspect logs. Pages blocked by robots.txt, CAPTCHAs, 403/429 responses or invitation gates must remain restricted. Do not circumvent controls.
5. Create and verify site-specific stock adapters/allowed sources for every retailer in the watchlist. Run controlled unavailable-to-available tests before production email.
6. Add SMTP details securely (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_FROM`, `SMTP_PASSWORD`) or switch to an authorised transactional-email provider. For Gmail, an app password is required where supported; the ChatGPT Gmail connector does not automatically authenticate a deployed worker.
7. Only after a successful end-to-end alert test change `EMAIL_ENABLED=true`.

Daily digests are handled by a separate ChatGPT automation and are not part of this Docker worker. Watchlist entries must use product-level URLs, and exact launch times must be verified before setting `verified_drop_at`.
