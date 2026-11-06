"""Pokémon Drop Hunter: conservative public stock-listing monitor.

No CAPTCHA solving, automated purchasing, login bypass or invitation bypass.
"""
from __future__ import annotations

import json
import logging
import os
import random
import smtplib
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from html import escape
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

LOG = logging.getLogger("pokemon_drop_hunter")
USER_AGENT = os.getenv("USER_AGENT", "PokemonDropHunter/0.1 (+personal, low-rate release monitoring)")
DATA_DIR = Path(os.getenv("DATA_DIR", "."))
STATE_PATH = DATA_DIR / "state.json"
WATCHLIST_PATH = Path(os.getenv("WATCHLIST_PATH", "watchlist.json"))
POLL_SECONDS = max(60, int(os.getenv("POLL_SECONDS", "120")))
EMAIL_TO = os.getenv("EMAIL_TO", "")
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
ROBOTS_CACHE: dict[str, RobotFileParser] = {}

GATE_TEXT = ("captcha", "verify & checkout", "verify & add to cart", "bot protected", "automatic bot verification", "invite to purchase", "invitation only", "login to purchase")
NEGATIVE_TEXT = ("out of stock", "sold out", "notify me", "coming soon", "currently unavailable")
POSITIVE_BUTTON_TEXT = ("add to cart", "add to basket", "buy now", "pre-order", "preorder")


@dataclass(frozen=True)
class StockSignal:
    state: str  # IN_STOCK, OUT_OF_STOCK, UNKNOWN, ACCESS_RESTRICTED
    reason: str


def product_main(soup: BeautifulSoup):
    return soup.select_one("main") or soup.select_one("[role=main]") or soup


def interpret_html(html: str, selectors: dict | None = None) -> StockSignal:
    selectors = selectors or {}
    soup = BeautifulSoup(html, "html.parser")
    main = product_main(soup)
    text = main.get_text(" ", strip=True).lower()
    if any(marker in text for marker in GATE_TEXT):
        return StockSignal("ACCESS_RESTRICTED", "Verification/invitation gate detected")
    for sel in selectors.get("restricted", []):
        if main.select_one(sel):
            return StockSignal("ACCESS_RESTRICTED", "Retailer restriction selector")
    for sel in selectors.get("out_of_stock", []):
        if main.select_one(sel):
            return StockSignal("OUT_OF_STOCK", "Retailer unavailable selector")
    for sel in selectors.get("in_stock", []):
        element = main.select_one(sel)
        if element and not element.has_attr("disabled") and element.get("aria-disabled") != "true":
            return StockSignal("IN_STOCK", "Retailer purchase control confirmed")
    forms = main.select('form[action*="/cart/add"], form[action*="add-to-cart"]')
    for form in forms:
        for button in form.select("button, input[type=submit]"):
            label = (button.get_text(" ", strip=True) or button.get("value", "")).lower()
            if any(x in label for x in POSITIVE_BUTTON_TEXT) and not button.has_attr("disabled") and button.get("aria-disabled") != "true":
                return StockSignal("IN_STOCK", "Enabled product purchase button")
    if any(x in text for x in NEGATIVE_TEXT):
        return StockSignal("OUT_OF_STOCK", "Unavailable marker without purchase control")
    return StockSignal("UNKNOWN", "No reliable product-level stock signal")


def robots_allowed(session: requests.Session, url: str) -> bool:
    target = urlsplit(url)
    if target.scheme != "https" or not target.hostname:
        raise ValueError("Only HTTPS product URLs are allowed")
    host = f"{target.scheme}://{target.netloc}"
    if host not in ROBOTS_CACHE:
        rp = RobotFileParser()
        rp.set_url(host + "/robots.txt")
        try:
            response = session.get(host + "/robots.txt", timeout=12, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            rp.parse(response.text.splitlines())
        except requests.RequestException as exc:
            LOG.warning("Robots policy unavailable for %s (%s); skipping", host, exc)
            return False
        ROBOTS_CACHE[host] = rp
    return ROBOTS_CACHE[host].can_fetch(USER_AGENT, url)


def check_product(session: requests.Session, product: dict) -> StockSignal:
    url = product["url"]
    if not robots_allowed(session, url):
        return StockSignal("ACCESS_RESTRICTED", "robots.txt disallows/unavailable")
    try:
        response = session.get(url, timeout=20, headers={"User-Agent": USER_AGENT, "Accept": "text/html"}, allow_redirects=True)
        if response.status_code in (401, 403, 429):
            return StockSignal("ACCESS_RESTRICTED", f"HTTP {response.status_code} access/rate limit")
        response.raise_for_status()
        if urlsplit(response.url).hostname != urlsplit(url).hostname:
            return StockSignal("UNKNOWN", "Redirected to another host")
        return interpret_html(response.text, product.get("selectors"))
    except requests.RequestException as exc:
        return StockSignal("UNKNOWN", f"HTTP error: {exc.__class__.__name__}")


def read_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp = STATE_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2, sort_keys=True))
    temp.replace(STATE_PATH)


def email_message(subject: str, title: str, product: dict, detail: str) -> EmailMessage:
    url, name = product["url"], product["name"]
    if urlsplit(url).scheme != "https":
        raise ValueError("Expected HTTPS product link")
    msg = EmailMessage()
    msg["From"] = os.getenv("SMTP_FROM") or os.getenv("SMTP_USER", "")
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject
    msg.set_content(f"{title}\n{name}\n{detail}\n\nDirect retailer link: {url}\n\nStock is not guaranteed.")
    msg.add_alternative(f"""<html><body style='font-family:Arial,sans-serif;max-width:620px;line-height:1.6'>
    <div style='background:#841b28;color:white;padding:20px'><h1>{escape(title)}</h1></div>
    <div style='padding:20px'><h2>{escape(name)}</h2><p>{escape(detail)}</p>
    <a href='{escape(url, quote=True)}' style='background:#1767b4;color:white;padding:12px 20px;display:inline-block'>OPEN RETAILER PRODUCT PAGE</a>
    <p><small>Public listing observation only. Availability may change.</small></p></div></body></html>""", subtype="html")
    return msg


def send(msg: EmailMessage) -> bool:
    if not EMAIL_ENABLED:
        LOG.info("DRY RUN: would email %s | %s", EMAIL_TO or "(unset recipient)", msg["Subject"])
        return False
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user, password = os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD")
    if not user or not password or not EMAIL_TO:
        LOG.error("Missing SMTP_USER, SMTP_PASSWORD or EMAIL_TO")
        return False
    try:
        with smtplib.SMTP(host, port, timeout=25) as client:
            client.starttls()
            client.login(user, password)
            client.send_message(msg)
        LOG.info("SMTP accepted email: %s", msg["Subject"])
        return True
    except (OSError, smtplib.SMTPException) as exc:
        LOG.error("SMTP send failed: %s", exc)
        return False


def check_drop_schedule(product: dict, entry: dict, now: datetime) -> None:
    exact = product.get("verified_drop_at")
    if not exact or entry.get("countdown_sent_for") == exact:
        return
    try:
        deadline = datetime.fromisoformat(exact)
        if deadline.tzinfo is None:
            LOG.warning("Unzoned launch time ignored for %s", product["id"])
            return
    except ValueError:
        return
    remaining = (deadline - now).total_seconds()
    if 0 < remaining <= 600:
        when = deadline.astimezone(ZoneInfo("Europe/London")).strftime("%d %b %Y %H:%M %Z")
        msg = email_message(f"POKÉMON DROP IN 10 MINUTES | {product['name']}", "CONFIRMED DROP APPROACHING", product, f"Verified launch: {when}. About {int(remaining // 60) + 1} minutes away.")
        if send(msg):
            entry["countdown_sent_for"] = exact


def evaluate(product: dict, entry: dict, signal: StockSignal, now: datetime) -> None:
    entry["last_checked_at"] = now.isoformat()
    entry["latest_signal"] = signal.state
    entry["latest_reason"] = signal.reason
    if signal.state in ("UNKNOWN", "ACCESS_RESTRICTED"):
        entry["positive_checks"] = 0
        return
    if signal.state == "OUT_OF_STOCK":
        entry["positive_checks"] = 0
        entry["negative_checks"] = entry.get("negative_checks", 0) + 1
        if entry["negative_checks"] >= 2:
            entry["known_stock"] = False
        return
    entry["negative_checks"] = 0
    entry["positive_checks"] = entry.get("positive_checks", 0) + 1
    if entry.get("known_stock") is True or entry["positive_checks"] < 2:
        return
    previous = entry.get("last_alerted_at")
    if previous:
        try:
            if now - datetime.fromisoformat(previous) < timedelta(minutes=30):
                return
        except ValueError:
            pass
    msg = email_message(f"URGENT — POKÉMON DROP LIVE NOW | {product['name']}", "URGENT — LIVE NOW", product, "A purchasable stock signal is now visible. No countdown delay; open the retailer page promptly.")
    if send(msg):
        entry["last_alerted_at"] = now.isoformat()
        entry["known_stock"] = True


def run_once(session: requests.Session, products: list[dict], state: dict) -> None:
    now = datetime.now(timezone.utc)
    for i, product in enumerate(products):
        if not product.get("enabled", True):
            continue
        entry = state.setdefault(product["id"], {})
        check_drop_schedule(product, entry, now)
        try:
            signal = check_product(session, product)
            evaluate(product, entry, signal, now)
            LOG.info("%s: %s (%s)", product["name"], signal.state, signal.reason)
        except Exception:
            LOG.exception("Check failed for %s", product["id"])
        save_state(state)
        if i < len(products) - 1:
            time.sleep(2)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not WATCHLIST_PATH.exists():
        sys.exit(f"Watchlist missing: {WATCHLIST_PATH}")
    products = json.loads(WATCHLIST_PATH.read_text())
    if not isinstance(products, list) or len({p["id"] for p in products}) != len(products):
        sys.exit("Expected a JSON list with unique product IDs")
    LOG.info("Watching %d pages every ~%d seconds; email_enabled=%s", len(products), POLL_SECONDS, EMAIL_ENABLED)
    with requests.Session() as session:
        while True:
            run_once(session, products, read_state())
            time.sleep(POLL_SECONDS + random.uniform(0, min(30, POLL_SECONDS / 5)))


if __name__ == "__main__":
    main()
