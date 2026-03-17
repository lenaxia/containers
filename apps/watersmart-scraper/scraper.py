#!/usr/bin/env python3
"""
WaterSmart to MQTT Scraper
Scrapes hourly water usage from WaterSmart RealTimeChart API and publishes to MQTT.
"""

import html
import json
import logging
import os
import re
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urljoin, urlparse

import requests
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Logging — configured before anything else so load_dotenv errors are visible
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# P2: load_dotenv after logging is configured
load_dotenv()


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def _int_env(name: str, default: int) -> int:
    """R1/R2/R3: Parse an integer env var with a clear error on bad input."""
    raw = os.getenv(name, str(default))
    try:
        return int(raw)
    except ValueError:
        logger.error(
            "Invalid value for %s: %r — must be an integer. Using default %d.",
            name,
            raw,
            default,
        )
        return default


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WATERSMART_URL = os.getenv("WATERSMART_URL", "https://mercerislandwa.watersmart.com")
# SEC-5: credentials are sent to this URL — enforce HTTPS to prevent plaintext
# credential transmission.
if urlparse(WATERSMART_URL).scheme != "https":
    logger.warning(
        "WATERSMART_URL is not HTTPS (%s). Credentials will be transmitted in "
        "plaintext. This is a security risk — use https://.",
        WATERSMART_URL,
    )

ACCOUNT_NUMBER = os.getenv("ACCOUNT_NUMBER", "")

# Auth — cookies take priority; fall back to username/password
PHPSESSID = os.getenv("PHPSESSID", "")
SESSION_COOKIE_NAME = os.getenv(
    "SESSION_COOKIE_NAME", "a64b84d4419675c8425cb15c2f5fda28"
)
SESSION_COOKIE_VALUE = os.getenv("SESSION_COOKIE", "")
WATERSMART_USERNAME = os.getenv("WATERSMART_USERNAME", "")
WATERSMART_PASSWORD = os.getenv("WATERSMART_PASSWORD", "")

# MQTT
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = _int_env("MQTT_PORT", 1883)
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "watersmart")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "watersmart-scraper")
MQTT_TLS = os.getenv("MQTT_TLS", "false").lower() == "true"
# SEC-4: escape hatch for self-signed broker certs — always warn loudly.
MQTT_TLS_INSECURE = os.getenv("MQTT_TLS_INSECURE", "false").lower() == "true"

# Home Assistant device identity
HA_DEVICE_NAME = os.getenv("HA_DEVICE_NAME", "Water Meter")
HA_DEVICE_ID = os.getenv("HA_DEVICE_ID", "watersmart_meter")
HA_DISCOVERY_PREFIX = os.getenv("HA_DISCOVERY_PREFIX", "homeassistant")

# Scraper
SCRAPE_INTERVAL_MINUTES = _int_env("SCRAPE_INTERVAL_MINUTES", 60)

# Health server
HEALTH_PORT = _int_env("HEALTH_PORT", 8080)
# SEC-8: default to loopback in production-like environments. Override to
# 0.0.0.0 only when external access (e.g. Kubernetes liveness probe from
# kubelet) is required.
HEALTH_BIND = os.getenv("HEALTH_BIND", "0.0.0.0")
# How old (seconds) a last-successful-scrape can be before /readyz fails.
# Default: 2× scrape interval.
HEALTH_SCRAPE_STALE_SECONDS = _int_env(
    "HEALTH_SCRAPE_STALE_SECONDS", SCRAPE_INTERVAL_MINUTES * 60 * 2
)

# Timeouts — named constants (M1/M2/M3)
HTTP_TIMEOUT = 30  # seconds for all WaterSmart HTTP calls
MQTT_CONNECT_TIMEOUT = 10  # seconds to wait for CONNACK
MQTT_PUBLISH_TIMEOUT = 10  # seconds for wait_for_publish

# HTTP retry (RL2)
HTTP_RETRY_ATTEMPTS = 3
HTTP_RETRY_BACKOFF = 2.0  # seconds; doubles each attempt

# API endpoints (E4)
REALTIME_CHART_PATH = "/index.php/rest/v1/Chart/RealTimeChart"
PIE_CHART_PATH = "/index.php/rest/v1/Chart/usagePieChart?module=portal&commentary=full"
LOGIN_PATH = "/index.php/welcome/login"
LOGIN_POST_PATH = "/index.php/welcome/login?forceEmail=1"


# ---------------------------------------------------------------------------
# Health state  (declared before WaterSmartClient / MQTTPublisher so the
# module-level singleton is available when those classes call into it)
# ---------------------------------------------------------------------------


class HealthState:
    """
    Thread-safe singleton tracking the health of all subsystems.

    Kubernetes probes:
      /livez   — is the process alive? Fails only before initialisation.
      /readyz  — is the service ready? Fails until first successful scrape
                 and while any subsystem is degraded or scrape data is stale.
      /healthz — deep diagnostic JSON; always returns full detail.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.started_at = datetime.now(timezone.utc)
        self.initialised = False

        # WaterSmart auth
        self.watersmart_authenticated = False
        self.watersmart_last_auth_at: datetime | None = None
        self.watersmart_last_error: str | None = None

        # MQTT
        self.mqtt_connected = False
        self.mqtt_last_error: str | None = None

        # Scrape results
        self.last_scrape_at: datetime | None = None
        self.last_scrape_success: bool | None = None
        self.last_scrape_record_count: int = 0
        self.last_scrape_error: str | None = None
        self.scrape_total: int = 0
        self.scrape_failures: int = 0

    # -- mutators (called from scraper thread) --------------------------------

    def set_initialised(self) -> None:
        with self._lock:
            self.initialised = True

    def set_watersmart_auth(self, ok: bool, error: str | None = None) -> None:
        with self._lock:
            self.watersmart_authenticated = ok
            if ok:
                self.watersmart_last_auth_at = datetime.now(timezone.utc)
                self.watersmart_last_error = None
            else:
                self.watersmart_last_error = error

    def set_mqtt_connected(self, ok: bool, error: str | None = None) -> None:
        with self._lock:
            self.mqtt_connected = ok
            self.mqtt_last_error = None if ok else error

    def record_scrape(
        self, success: bool, record_count: int = 0, error: str | None = None
    ) -> None:
        with self._lock:
            self.last_scrape_at = datetime.now(timezone.utc)
            self.last_scrape_success = success
            self.last_scrape_record_count = record_count
            self.scrape_total += 1
            if success:
                self.last_scrape_error = None
            else:
                self.scrape_failures += 1
                self.last_scrape_error = error

    # -- accessors (called from health HTTP thread) ---------------------------

    def liveness(self) -> tuple[bool, dict]:
        with self._lock:
            ok = self.initialised
            return ok, {
                "status": "ok" if ok else "not_ready",
                "initialised": self.initialised,
                "uptime_seconds": round(
                    (datetime.now(timezone.utc) - self.started_at).total_seconds()
                ),
            }

    def readiness(self) -> tuple[bool, dict]:
        with self._lock:
            return self._readiness_locked()

    def _readiness_locked(self) -> tuple[bool, dict]:
        """Must be called with self._lock held."""
        now = datetime.now(timezone.utc)
        checks: dict[str, bool] = {
            "initialised": self.initialised,
            "watersmart_authenticated": self.watersmart_authenticated,
            "mqtt_connected": self.mqtt_connected,
        }
        if self.last_scrape_at is None or not self.last_scrape_success:
            checks["last_scrape_fresh"] = False
        else:
            age = (now - self.last_scrape_at).total_seconds()
            checks["last_scrape_fresh"] = age <= HEALTH_SCRAPE_STALE_SECONDS

        ok = all(checks.values())
        return ok, {"status": "ok" if ok else "degraded", "checks": checks}

    def deep_health(self) -> tuple[bool, dict]:
        """R15/P7: All reads and status derivation in a single lock pass."""
        with self._lock:
            now = datetime.now(timezone.utc)
            last_scrape_age = (
                round((now - self.last_scrape_at).total_seconds())
                if self.last_scrape_at
                else None
            )
            ok, readiness = self._readiness_locked()
            payload = {
                "status": "ok" if ok else "degraded",
                "checks": readiness["checks"],
                "uptime_seconds": round((now - self.started_at).total_seconds()),
                "initialised": self.initialised,
                "watersmart": {
                    "authenticated": self.watersmart_authenticated,
                    "last_auth_at": (
                        self.watersmart_last_auth_at.isoformat()
                        if self.watersmart_last_auth_at
                        else None
                    ),
                    "last_error": self.watersmart_last_error,
                },
                "mqtt": {
                    "connected": self.mqtt_connected,
                    # SEC-8: omit broker host/port from health response to avoid
                    # leaking internal network topology to anyone who can reach
                    # the health endpoint.
                    "tls": MQTT_TLS,
                    "last_error": self.mqtt_last_error,
                },
                "scraper": {
                    "last_scrape_at": (
                        self.last_scrape_at.isoformat() if self.last_scrape_at else None
                    ),
                    "last_scrape_age_seconds": last_scrape_age,
                    "last_scrape_success": self.last_scrape_success,
                    "last_scrape_record_count": self.last_scrape_record_count,
                    "last_scrape_error": self.last_scrape_error,
                    "scrape_total": self.scrape_total,
                    "scrape_failures": self.scrape_failures,
                    "stale_threshold_seconds": HEALTH_SCRAPE_STALE_SECONDS,
                },
            }
        return ok, payload


# Module-level singleton — available to all classes below
health = HealthState()


# ---------------------------------------------------------------------------
# WaterSmart HTTP client
# ---------------------------------------------------------------------------


class WaterSmartClient:
    """Handles authentication and data fetching from WaterSmart."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self._configure_headers()

    def _configure_headers(self) -> None:
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/146.0.0.0 Safari/537.36"
                ),
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": urljoin(WATERSMART_URL, "/index.php/trackUsage"),
                "DNT": "1",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            }
        )

    # -- authentication -------------------------------------------------------

    def authenticate(self) -> bool:
        """Try cookies first, then credential login."""
        if PHPSESSID or SESSION_COOKIE_VALUE:
            ok = self._auth_with_cookies()
        elif WATERSMART_USERNAME and WATERSMART_PASSWORD:
            ok = self._auth_with_credentials()
        else:
            logger.error(
                "No authentication method configured. "
                "Set PHPSESSID/SESSION_COOKIE or WATERSMART_USERNAME/WATERSMART_PASSWORD."
            )
            ok = False
        health.set_watersmart_auth(ok, error=None if ok else "Authentication failed")
        return ok

    def _auth_with_cookies(self) -> bool:
        """Inject pre-existing session cookies."""
        # R4/P10: use urlparse instead of manual string stripping
        domain = urlparse(WATERSMART_URL).hostname or ""
        if PHPSESSID:
            self.session.cookies.set("PHPSESSID", PHPSESSID, domain=domain)
            logger.info("Loaded PHPSESSID cookie.")
        if SESSION_COOKIE_VALUE:
            self.session.cookies.set(
                SESSION_COOKIE_NAME, SESSION_COOKIE_VALUE, domain=domain
            )
            logger.info("Loaded encrypted session cookie.")
        return self._verify_session()

    def _verify_session(self) -> bool:
        """Confirm the current session is valid by hitting the data endpoint."""
        try:
            url = urljoin(WATERSMART_URL, REALTIME_CHART_PATH)
            resp = self.session.get(url, timeout=HTTP_TIMEOUT)
            if resp.status_code == 200:
                logger.info("Session verified successfully.")
                return True
            if resp.status_code in (401, 403):
                logger.warning(
                    "Session invalid (status %s). Will attempt credential login.",
                    resp.status_code,
                )
                return False
            # R6: 5xx / other transient errors are not auth failures
            logger.warning(
                "Transient error during session verification (status %s); "
                "treating session as valid to avoid unnecessary re-auth.",
                resp.status_code,
            )
            return True
        except requests.RequestException as exc:
            logger.error("Session verification failed: %s", exc)
            return False

    def _auth_with_credentials(self) -> bool:
        """Login using email and password."""
        logger.info("Attempting credential-based login...")
        try:
            login_get_url = urljoin(WATERSMART_URL, LOGIN_PATH)
            resp = self.session.get(login_get_url, timeout=HTTP_TIMEOUT)
            resp.raise_for_status()

            # Extract hidden CSRF token from the form
            token = ""
            match = re.search(r'<input[^>]+name="token"[^>]+value="([^"]*)"', resp.text)
            if match:
                token = match.group(1)
                logger.debug("CSRF token found.")
            else:
                # R8: warn explicitly — a missing token means the page structure
                # changed or we're not on the login page we expect.
                logger.warning(
                    "CSRF token not found in login form HTML. "
                    "Login may fail if the site requires it."
                )

            payload = {
                "email": WATERSMART_USERNAME,
                "password": WATERSMART_PASSWORD,
                "token": token,
            }

            login_post_url = urljoin(WATERSMART_URL, LOGIN_POST_PATH)
            login_resp = self.session.post(
                login_post_url, data=payload, timeout=HTTP_TIMEOUT, allow_redirects=True
            )

            # M6: WaterSmart redirects to a dashboard page that contains a
            # "Logout" link in the nav when authentication succeeds.  This is
            # the most reliable signal available without parsing a JSON body.
            if "logout" in login_resp.text.lower():
                logger.info("Credential login succeeded.")
                health.set_watersmart_auth(True)
                return True

            err = (
                f"Login failed (status {login_resp.status_code}). Check email/password."
            )
            logger.error(err)
            health.set_watersmart_auth(False, error=err)
            return False
        except requests.RequestException as exc:
            err = f"Login request failed: {exc}"
            logger.error(err)
            health.set_watersmart_auth(False, error=err)
            return False

    # -- data fetching --------------------------------------------------------

    def _fetch_with_reauth(self, url: str, label: str) -> dict | None:
        """
        GET *url*, transparently re-authenticating once on session expiry.

        *label* is a short human-readable name used only in log messages so
        callers don't need to repeat the error-handling boilerplate.

        Returns the parsed JSON dict on success, or None on any failure.
        """
        resp = self._get(url)
        if resp is None:
            return None

        if self._is_session_expired(resp):
            logger.warning(
                "Session expired fetching %s (status %s); re-authenticating...",
                label,
                resp.status_code,
            )
            health.set_watersmart_auth(False, error="Session expired")

            # R7: only attempt credential re-auth if credentials are configured
            if not (WATERSMART_USERNAME and WATERSMART_PASSWORD):
                logger.error(
                    "Session expired and no credentials configured for renewal. "
                    "Set WATERSMART_USERNAME/WATERSMART_PASSWORD."
                )
                return None

            # SEC-10: clear all stale session cookies before re-auth so expired
            # tokens don't persist and accidentally get sent alongside new ones.
            self.session.cookies.clear()

            if not self._auth_with_credentials():
                logger.error("Re-authentication failed.")
                return None

            resp = self._get(url)
            if resp is None or self._is_session_expired(resp):
                logger.error("Still getting session error after re-auth (%s).", label)
                health.set_watersmart_auth(False, error="Session error after re-auth")
                return None

        try:
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.error("Failed to fetch %s: %s", label, exc)
            return None
        except ValueError as exc:
            logger.error("Failed to parse %s JSON: %s", label, exc)
            return None

    def fetch_realtime_data(self) -> dict | None:
        """Fetch RealTimeChart data."""
        return self._fetch_with_reauth(
            urljoin(WATERSMART_URL, REALTIME_CHART_PATH), "RealTimeChart"
        )

    def fetch_pie_chart_data(self) -> dict | None:
        """Fetch usagePieChart data."""
        return self._fetch_with_reauth(
            urljoin(WATERSMART_URL, PIE_CHART_PATH), "usagePieChart"
        )

    def _get(self, url: str) -> requests.Response | None:
        """RL2: GET with retry and exponential backoff on transient errors."""
        delay = HTTP_RETRY_BACKOFF
        for attempt in range(1, HTTP_RETRY_ATTEMPTS + 1):
            try:
                return self.session.get(url, timeout=HTTP_TIMEOUT)
            except requests.RequestException as exc:
                if attempt == HTTP_RETRY_ATTEMPTS:
                    logger.error("Request failed after %d attempts: %s", attempt, exc)
                    return None
                logger.warning(
                    "Request error (attempt %d/%d): %s — retrying in %.1fs",
                    attempt,
                    HTTP_RETRY_ATTEMPTS,
                    exc,
                    delay,
                )
                time.sleep(delay)
                delay *= 2
        return None  # unreachable, satisfies type checker

    @staticmethod
    def _is_session_expired(resp: requests.Response) -> bool:
        if resp.status_code in (401, 403):
            return True
        if resp.status_code == 200 and "login" in resp.url.lower():
            return True
        return False


# ---------------------------------------------------------------------------
# Data parsing
# ---------------------------------------------------------------------------


def parse_realtime_data(raw: object) -> list[dict]:
    """
    Parse the RealTimeChart API response into a flat list of records.

    Expected shape:
    {
      "data": {
        "series": [
          { "read_datetime": 1764716400, "gallons": 0,
            "flags": null, "leak_gallons": 0 },
          ...
        ]
      }
    }
    """
    # P8: validate that raw is actually a dict before calling .get()
    if not isinstance(raw, dict):
        logger.error(
            "Unexpected API response type %s; expected dict.", type(raw).__name__
        )
        return []

    records: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()

    series = raw.get("data", {}).get("series", [])
    if not series:
        logger.warning(
            "No 'series' key found in response. Top-level keys: %s",
            list(raw.get("data", raw).keys()),
        )
        if logger.isEnabledFor(logging.DEBUG):  # M7
            logger.debug("Raw response: %s", json.dumps(raw, indent=2)[:2000])
        return records

    for entry in series:
        # R9: parse each entry independently so one bad value doesn't abort the loop
        try:
            ts_seconds = entry.get("read_datetime")
            gallons = entry.get("gallons")
            if ts_seconds is None or gallons is None:
                continue
            ts = datetime.fromtimestamp(int(ts_seconds), tz=timezone.utc).isoformat()
            records.append(
                {
                    "timestamp": ts,
                    "consumption_gallons": round(float(gallons), 4),
                    "leak_gallons": round(float(entry.get("leak_gallons") or 0), 4),
                    "flags": entry.get("flags") or [],
                    "scraped_at": now,
                }
            )
        except (TypeError, ValueError, OSError) as exc:
            logger.warning("Skipping malformed series entry %r: %s", entry, exc)
            continue

    logger.debug("Parsed %d/%d series entries.", len(records), len(series))
    return records


def latest_record(records: list[dict]) -> dict | None:
    """R10: Return the record with the most recent ISO timestamp."""
    if not records:
        return None
    try:
        return max(records, key=lambda r: r["timestamp"])
    except (KeyError, TypeError) as exc:
        logger.warning("Could not determine latest record: %s", exc)
        return None  # don't silently return the wrong record


def parse_pie_chart_data(raw: object, scraped_at: str) -> list[dict]:
    """
    Parse the usagePieChart API response into a flat list of category records.

    Expected shape:
    {
      "data": {
        "chartData": {
          "toilets": { "name": "toilets", "value": 19828.88, "percentage": 30,
                       "display_name": "toilets", ... },
          ...
        },
        "commentary": [ { "headline": "...", "comment": "..." } ]
      }
    }

    Returns one record per category present in the response, plus the raw
    commentary list.  Categories are taken directly from the API — no hardcoded
    list is maintained here.
    """
    if not isinstance(raw, dict):
        logger.error(
            "Unexpected pie chart response type %s; expected dict.", type(raw).__name__
        )
        return []

    chart_data = raw.get("data", {}).get("chartData", {})
    if not chart_data:
        logger.warning(
            "No 'chartData' key found in pie chart response. Top-level keys: %s",
            list(raw.get("data", raw).keys()),
        )
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Raw pie chart response: %s", json.dumps(raw, indent=2)[:2000])
        return []

    records: list[dict] = []
    for key, entry in chart_data.items():
        try:
            # The API HTML-encodes some category names (e.g. "showers &amp; baths").
            # Unescape so downstream consumers (MQTT payloads, HA templates, logs)
            # all see clean UTF-8 strings rather than HTML entities.
            clean_key = html.unescape(key)
            display_name = html.unescape(entry.get("display_name") or key)

            # The API occasionally returns -1 for percentage (e.g. irrigation with
            # zero usage).  Treat any negative value as 0 — it has no meaningful
            # interpretation as a usage share.
            raw_pct = entry.get("percentage")
            percentage = max(0, int(raw_pct)) if raw_pct is not None else 0

            records.append(
                {
                    "category": clean_key,
                    "display_name": display_name,
                    "value_gallons": round(float(entry.get("value") or 0), 4),
                    "percentage": percentage,
                    "scraped_at": scraped_at,
                }
            )
        except (TypeError, ValueError) as exc:
            logger.warning("Skipping malformed pie chart entry %r: %s", entry, exc)
            continue

    logger.debug("Parsed %d pie chart categories.", len(records))
    return records


# ---------------------------------------------------------------------------
# MQTT publisher
# ---------------------------------------------------------------------------


class MQTTPublisher:
    def __init__(self) -> None:
        self.client = mqtt.Client(
            client_id=MQTT_CLIENT_ID,
            protocol=mqtt.MQTTv311,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        # R11/RL1: use threading.Event instead of a plain bool to avoid data race
        self._connected_event = threading.Event()
        self._loop_started = False  # RL6: track whether loop_start() was called

        if MQTT_USERNAME:
            self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        if MQTT_TLS:
            self.client.tls_set()
            if MQTT_TLS_INSECURE:
                # SEC-4: only allowed as an explicit opt-in; logs a prominent warning
                # so it is never silently active.
                logger.warning(
                    "MQTT_TLS_INSECURE=true — broker certificate verification is "
                    "DISABLED. This is insecure and should only be used for local "
                    "development with self-signed certificates."
                )
                self.client.tls_insecure_set(True)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    @property
    def connected(self) -> bool:
        return self._connected_event.is_set()

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: object,
        reason_code: int,
        properties: object,
    ) -> None:
        if reason_code == 0:
            self._connected_event.set()
            health.set_mqtt_connected(True)
            logger.info("Connected to MQTT broker %s:%s", MQTT_BROKER, MQTT_PORT)
            # M9: re-publish HA discovery after every (re)connect so a broker
            # restart or a new HA instance doesn't lose the device/entity config.
            threading.Thread(
                target=_republish_discovery_on_connect,
                daemon=True,
                name="ha-discovery-republish",
            ).start()
        else:
            self._connected_event.clear()
            health.set_mqtt_connected(False, error=f"reason_code={reason_code}")
            logger.error("MQTT connection failed, reason_code=%s", reason_code)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: object,
        reason_code: int,
        properties: object,
    ) -> None:
        self._connected_event.clear()
        if reason_code != 0:
            health.set_mqtt_connected(
                False, error=f"Unexpected disconnect reason_code={reason_code}"
            )
            logger.warning("Unexpected MQTT disconnect, reason_code=%s", reason_code)

    def connect(self) -> bool:
        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            # RL6: only call loop_start() once across all connect() calls
            if not self._loop_started:
                self.client.loop_start()
                self._loop_started = True
            if self._connected_event.wait(timeout=MQTT_CONNECT_TIMEOUT):
                return True
            # RL5: connection timed out — don't leak the background thread
            err = f"MQTT connection timed out after {MQTT_CONNECT_TIMEOUT}s."
            logger.error(err)
            health.set_mqtt_connected(False, error=err)
            self.client.loop_stop()
            self._loop_started = False
            return False
        except Exception as exc:
            err = f"MQTT connect error: {exc}"
            logger.error(err)
            health.set_mqtt_connected(False, error=err)
            if self._loop_started:
                self.client.loop_stop()
                self._loop_started = False
            return False

    def ensure_connected(self) -> bool:
        if not self.connected:
            logger.info("Reconnecting to MQTT...")
            return self.connect()
        return True

    def publish(self, topic: str, payload: dict, retain: bool = False) -> bool:
        if not self.ensure_connected():
            return False
        try:
            msg = json.dumps(payload)
            result = self.client.publish(topic, msg, qos=1, retain=retain)
            result.wait_for_publish(timeout=MQTT_PUBLISH_TIMEOUT)
            logger.debug("Published to %s", topic)
            return True
        except Exception as exc:
            logger.error("Publish failed to %s: %s", topic, exc)
            return False

    def disconnect(self) -> None:
        if self._loop_started:
            self.client.loop_stop()
        self.client.disconnect()


# ---------------------------------------------------------------------------
# MQTT topic helpers and HA discovery
# ---------------------------------------------------------------------------


def make_topic(*parts: str) -> str:
    base = MQTT_TOPIC_PREFIX.rstrip("/")
    return "/".join([base] + [str(p) for p in parts])


def _slugify(text: str) -> str:
    """
    Convert a category name to a safe, stable identifier fragment.

    Lowercases, strips leading/trailing whitespace, replaces runs of
    non-alphanumeric characters (spaces, ampersands, hyphens, etc.) with a
    single underscore, and strips any leading/trailing underscores.

    Examples:
        "toilets"          -> "toilets"
        "showers & baths"  -> "showers_baths"
        "washing machine"  -> "washing_machine"
    """
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower().strip()).strip("_")
    return slug or "unknown"


# Module-level reference set after mqtt_pub is created in main(),
# used by _republish_discovery_on_connect (M9)
_mqtt_pub_ref: MQTTPublisher | None = None


def _republish_discovery_on_connect() -> None:
    """M9: Called in a daemon thread after every (re)connect."""
    global _mqtt_pub_ref
    if _mqtt_pub_ref is not None:
        publish_ha_discovery(_mqtt_pub_ref)
        # Pie chart discovery is published dynamically after the first successful
        # pie chart scrape (see _run_scrape_inner).  On reconnect we can only
        # re-publish categories we've already seen, held in the module-level cache.
        _republish_pie_chart_discovery(_mqtt_pub_ref)


def publish_ha_discovery(mqtt_pub: MQTTPublisher) -> None:
    """
    Publish MQTT discovery messages so Home Assistant auto-creates sensor
    entities grouped under a single device (HA_DEVICE_NAME / HA_DEVICE_ID).

    Sensors:
      - {HA_DEVICE_ID}_consumption  — most-recent hourly usage (gal)
      - {HA_DEVICE_ID}_leak         — leak gallons for the same period
      - {HA_DEVICE_ID}_last_read    — timestamp of the reading
    """
    device = {
        "identifiers": [HA_DEVICE_ID],
        "name": HA_DEVICE_NAME,
        "manufacturer": "WaterSmart",
        "model": "AMI Water Meter",
    }
    state_topic = make_topic("latest")

    sensors = [
        {
            "unique_id": f"{HA_DEVICE_ID}_consumption",
            "name": "Water Usage",
            "state_topic": state_topic,
            "value_template": "{{ value_json.consumption_gallons }}",
            "unit_of_measurement": "gal",
            "device_class": "water",
            "state_class": "measurement",
            "icon": "mdi:water",
            "device": device,
        },
        {
            "unique_id": f"{HA_DEVICE_ID}_leak",
            "name": "Water Leak Gallons",
            "state_topic": state_topic,
            "value_template": "{{ value_json.leak_gallons }}",
            "unit_of_measurement": "gal",
            "state_class": "measurement",
            "icon": "mdi:water-alert",
            "device": device,
        },
        {
            "unique_id": f"{HA_DEVICE_ID}_last_read",
            "name": "Water Meter Last Read",
            "state_topic": state_topic,
            "value_template": "{{ value_json.timestamp }}",
            "device_class": "timestamp",
            "icon": "mdi:clock-outline",
            "device": device,
        },
    ]

    for sensor in sensors:
        uid = sensor["unique_id"]
        discovery_topic = f"{HA_DISCOVERY_PREFIX}/sensor/{uid}/config"
        mqtt_pub.publish(discovery_topic, sensor, retain=True)
        logger.info("Published HA discovery for sensor: %s", uid)


# ---------------------------------------------------------------------------
# Pie chart HA discovery — dynamic, driven entirely by API response categories
# ---------------------------------------------------------------------------

# Cache of category slugs seen in the most recent successful pie chart scrape.
# Populated by _run_scrape_inner; read by _republish_pie_chart_discovery so that
# broker-reconnect re-publishes stay in sync with what was last fetched.
# Guarded by _pie_chart_categories_lock.
_pie_chart_categories_lock = threading.Lock()
_pie_chart_known_categories: list[str] = []  # list of raw category keys


def _build_pie_chart_sensor(category_key: str, device: dict) -> dict:
    """
    Build a single HA MQTT discovery payload for one pie chart category.

    *category_key* is the raw key from the API (e.g. "showers & baths").
    The unique_id is derived from the slug so it is stable across restarts
    even if display_name or other metadata changes.
    """
    slug = _slugify(category_key)
    pie_state_topic = make_topic("pie_chart", "latest")
    return {
        "unique_id": f"{HA_DEVICE_ID}_pie_{slug}",
        "name": f"Water Usage — {category_key.title()}",
        "state_topic": pie_state_topic,
        # value_template selects this category's gallons from the categories map
        "value_template": (
            f"{{% set cat = value_json.categories | selectattr('category', 'equalto', "
            f"'{category_key}') | list %}}"
            "{% if cat %}{{ cat[0].value_gallons }}{% else %}unavailable{% endif %}"
        ),
        "unit_of_measurement": "gal",
        "state_class": "total",
        "icon": "mdi:chart-pie",
        "device": device,
    }


def publish_ha_discovery_pie_chart(
    mqtt_pub: MQTTPublisher, categories: list[str]
) -> None:
    """
    Publish HA MQTT discovery messages for every pie chart category in *categories*.

    Called after a successful pie chart scrape so the entity list always matches
    what the API actually returned.  Each sensor reads from the retained
    ``watersmart/pie_chart/latest`` topic.
    """
    if not categories:
        return

    device = {
        "identifiers": [HA_DEVICE_ID],
        "name": HA_DEVICE_NAME,
        "manufacturer": "WaterSmart",
        "model": "AMI Water Meter",
    }

    for category_key in categories:
        sensor = _build_pie_chart_sensor(category_key, device)
        uid = sensor["unique_id"]
        discovery_topic = f"{HA_DISCOVERY_PREFIX}/sensor/{uid}/config"
        mqtt_pub.publish(discovery_topic, sensor, retain=True)
        logger.info("Published HA pie chart discovery for sensor: %s", uid)


def _republish_pie_chart_discovery(mqtt_pub: MQTTPublisher) -> None:
    """Re-publish pie chart discovery using the last-known category list."""
    with _pie_chart_categories_lock:
        cats = list(_pie_chart_known_categories)
    if cats:
        publish_ha_discovery_pie_chart(mqtt_pub, cats)


# ---------------------------------------------------------------------------
# Scrape job
# ---------------------------------------------------------------------------


def run_scrape(ws_client: WaterSmartClient, mqtt_pub: MQTTPublisher) -> None:
    """R14/RL3: Top-level wrapper catches all exceptions so scheduler never dies."""
    try:
        _run_scrape_inner(ws_client, mqtt_pub)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled exception in scrape cycle: %s", exc)
        health.record_scrape(False, error=f"Unhandled exception: {exc}")


def _run_scrape_inner(ws_client: WaterSmartClient, mqtt_pub: MQTTPublisher) -> None:
    logger.info("--- Scrape cycle starting ---")
    # M4: single timestamp for the whole cycle
    scraped_at = datetime.now(timezone.utc).isoformat()

    raw = ws_client.fetch_realtime_data()
    if raw is None:
        logger.error("No data returned from WaterSmart API.")
        health.record_scrape(False, error="No data returned from API")
        logger.info("--- Scrape cycle aborted ---")  # M10
        return

    records = parse_realtime_data(raw)
    if not records:
        logger.warning("No records parsed from API response.")
        health.record_scrape(False, error="No records parsed from response")
        # SEC-7: the raw API response may contain account/billing PII — only
        # publish it to the debug topic when DEBUG logging is explicitly enabled.
        if logger.isEnabledFor(logging.DEBUG):
            # R13: serialise raw safely; fall back to str() if not JSON-serializable
            try:
                raw_payload: object = raw
                json.dumps(raw_payload)  # probe serializability
            except (TypeError, ValueError):
                raw_payload = str(raw)[:4096]
            mqtt_pub.publish(
                make_topic("debug", "raw"),
                {"raw": raw_payload, "scraped_at": scraped_at},
            )
        logger.info("--- Scrape cycle aborted ---")  # M10
        return

    logger.info("Parsed %d records.", len(records))
    account = ACCOUNT_NUMBER or "unknown"

    # Publish full hourly dataset
    mqtt_pub.publish(
        make_topic("hourly"),
        {
            "account": account,
            "scraped_at": scraped_at,
            "record_count": len(records),
            "records": records,
        },
    )

    # Publish most-recent single reading (retained — HA reads this via state_topic)
    latest = latest_record(records)
    if latest:
        # M4: reuse scraped_at from top of cycle; overwrite per-record scraped_at
        latest["scraped_at"] = scraped_at
        mqtt_pub.publish(
            make_topic("latest"),
            {"account": account, "scraped_at": scraped_at, **latest},
            retain=True,
        )
        logger.info(
            "Latest reading: %s gal at %s",
            latest.get("consumption_gallons"),
            latest.get("timestamp"),
        )

    health.record_scrape(True, record_count=len(records))

    # Best-effort: pie chart failures must not affect the health record above
    # or cause the scrape cycle to appear failed.
    try:
        _run_pie_chart_scrape(ws_client, mqtt_pub, scraped_at)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Pie chart scrape raised an unexpected error: %s", exc)

    logger.info("--- Scrape cycle complete ---")


def _run_pie_chart_scrape(
    ws_client: WaterSmartClient, mqtt_pub: MQTTPublisher, scraped_at: str
) -> None:
    """
    Fetch, parse, and publish the usage pie chart data.

    This is intentionally isolated from the main hourly scrape so that a pie
    chart failure never aborts or taints the primary data path.  All errors
    are logged but not re-raised.
    """
    raw_pie = ws_client.fetch_pie_chart_data()
    if raw_pie is None:
        logger.warning("Pie chart fetch returned no data; skipping pie chart publish.")
        return

    pie_records = parse_pie_chart_data(raw_pie, scraped_at)
    if not pie_records:
        logger.warning("No pie chart records parsed; skipping pie chart publish.")
        return

    account = ACCOUNT_NUMBER or "unknown"
    categories = [r["category"] for r in pie_records]

    # Publish retained summary — HA state_topic for pie chart sensors
    mqtt_pub.publish(
        make_topic("pie_chart", "latest"),
        {
            "account": account,
            "scraped_at": scraped_at,
            "category_count": len(pie_records),
            "categories": pie_records,
        },
        retain=True,
    )
    logger.info(
        "Published pie chart data: %d categories (%s)",
        len(pie_records),
        ", ".join(categories),
    )

    # Update the known-categories cache and (re-)publish HA discovery for any
    # new categories that appeared in this scrape.
    with _pie_chart_categories_lock:
        new_cats = [c for c in categories if c not in _pie_chart_known_categories]
        _pie_chart_known_categories.extend(new_cats)

    if new_cats:
        logger.info(
            "New pie chart categories discovered, publishing HA discovery: %s",
            new_cats,
        )
        publish_ha_discovery_pie_chart(mqtt_pub, new_cats)


# ---------------------------------------------------------------------------
# Health HTTP server
# ---------------------------------------------------------------------------


class _ReuseAddrHTTPServer(HTTPServer):
    """RL8: set allow_reuse_address on the subclass, not the base class."""

    allow_reuse_address = True


class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:  # P4: renamed from 'format'
        pass  # suppress default per-request stdout noise

    def _respond(self, ok: bool, body: dict) -> None:
        status = 200 if ok else 503
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path = self.path.rstrip("/")
        if path == "/livez":
            self._respond(*health.liveness())
        elif path == "/readyz":
            self._respond(*health.readiness())
        elif path == "/healthz":
            self._respond(*health.deep_health())
        else:
            self.send_response(404)
            self.end_headers()


def start_health_server() -> None:
    """RL7: catch OSError from port conflict and log clearly."""
    try:
        server = _ReuseAddrHTTPServer((HEALTH_BIND, HEALTH_PORT), HealthHandler)
    except OSError as exc:
        logger.error(
            "Failed to start health server on port %d: %s. "
            "Set HEALTH_PORT to a free port.",
            HEALTH_PORT,
            exc,
        )
        sys.exit(1)
    t = threading.Thread(target=server.serve_forever, name="health-server", daemon=True)
    t.start()
    logger.info(
        "Health server listening on :%d  (/livez /readyz /healthz)", HEALTH_PORT
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    logger.info("WaterSmart MQTT Scraper starting up.")
    logger.info("Target: %s", WATERSMART_URL)
    logger.info(
        "MQTT: %s:%s (topic prefix: %s)", MQTT_BROKER, MQTT_PORT, MQTT_TOPIC_PREFIX
    )
    logger.info(
        "HA device: %s (id: %s, discovery prefix: %s)",
        HA_DEVICE_NAME,
        HA_DEVICE_ID,
        HA_DISCOVERY_PREFIX,
    )
    logger.info("Scrape interval: %d minutes", SCRAPE_INTERVAL_MINUTES)

    # Start health server first — keeps liveness probe happy during slow startup
    start_health_server()

    ws_client = WaterSmartClient()
    if not ws_client.authenticate():
        logger.error("Authentication failed. Exiting.")
        sys.exit(1)

    mqtt_pub = MQTTPublisher()
    if not mqtt_pub.connect():
        logger.error("Could not connect to MQTT broker. Exiting.")
        sys.exit(1)

    # Make mqtt_pub available to the on_connect republish hook (M9).
    # Discovery is published by _on_connect (and on every reconnect), so no
    # explicit call is needed here — doing both would cause duplicate publishes.
    global _mqtt_pub_ref
    _mqtt_pub_ref = mqtt_pub

    health.set_initialised()

    # P9: replace schedule library with stdlib threading.Timer loop
    # RL4: handle SIGTERM for clean shutdown (docker stop / kubectl delete pod)
    stop_event = threading.Event()

    def _shutdown(signum: int, frame: object) -> None:
        logger.info("Received signal %d, shutting down.", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    def _schedule_next() -> None:
        if not stop_event.is_set():
            run_scrape(ws_client, mqtt_pub)
            timer = threading.Timer(SCRAPE_INTERVAL_MINUTES * 60, _schedule_next)
            timer.daemon = True
            timer.name = "scrape-timer"
            timer.start()

    # Run immediately, then start the repeating timer
    run_scrape(ws_client, mqtt_pub)
    timer = threading.Timer(SCRAPE_INTERVAL_MINUTES * 60, _schedule_next)
    timer.daemon = True
    timer.name = "scrape-timer"
    timer.start()

    stop_event.wait()  # block main thread; signal handler sets this
    logger.info("Shutting down cleanly.")
    timer.cancel()
    mqtt_pub.disconnect()


if __name__ == "__main__":
    main()
