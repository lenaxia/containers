# MercerMeterMaid

A Dockerized Python microservice that scrapes hourly water usage from the
[WaterSmart](https://mercerislandwa.watersmart.com) utility portal and publishes
it to MQTT with Home Assistant auto-discovery support. No browser automation —
pure HTTP with a `requests.Session`.

Built specifically for the **Mercer Island, WA** WaterSmart instance
(`mercerislandwa.watersmart.com`, account `00202650003`), but the auth and
scrape logic is generic enough to work against any WaterSmart deployment — only
the `WATERSMART_URL` and `SESSION_COOKIE_NAME` need to change.

---

## Table of contents

1. [How it works](#how-it-works)
2. [Repository layout](#repository-layout)
3. [Quick start](#quick-start)
4. [Authentication](#authentication)
5. [MQTT topics and payloads](#mqtt-topics-and-payloads)
6. [Home Assistant integration](#home-assistant-integration)
7. [Health endpoints](#health-endpoints)
8. [Full configuration reference](#full-configuration-reference)
9. [Docker and Kubernetes deployment](#docker-and-kubernetes-deployment)
10. [Architecture and implementation notes](#architecture-and-implementation-notes)
11. [WaterSmart API reference](#watersmart-api-reference)
12. [Security model](#security-model)
13. [Known limitations and quirks](#known-limitations-and-quirks)
14. [Development setup](#development-setup)

---

## How it works

```
WaterSmart portal          scraper.py                  MQTT broker
─────────────────    ──────────────────────────    ──────────────────
GET /login      ──▶  extract CSRF token        ──▶
POST /login     ──▶  store session cookies     ──▶
GET /RealTimeChart ▶ parse series[] JSON       ──▶  watersmart/latest   (retained)
                                               ──▶  watersmart/hourly
                                               ──▶  homeassistant/sensor/.../config (retained)
```

1. **Startup**: scraper authenticates (credentials preferred, cookies fallback),
   connects to MQTT, publishes HA auto-discovery config messages, then runs the
   first scrape immediately.
2. **Every 60 minutes** (configurable): fetches `RealTimeChart` API, parses the
   `data.series[]` array into records, publishes `latest` (retained) and
   `hourly` (non-retained).
3. **Session expiry**: if the API returns 401/403 or silently redirects to the
   login page, all session cookies are cleared and a fresh credential login is
   performed — once. If that also fails, the scrape cycle is aborted and the
   health state reflects the error.
4. **Health server**: a minimal `HTTPServer` runs on port 8080 throughout,
   serving `/livez`, `/readyz`, and `/healthz` for liveness/readiness probes.

---

## Repository layout

```
MercerMeterMaid/
├── scraper.py              # Entire application — single file, ~990 lines
├── Dockerfile              # python:3.11-slim, runs as non-root uid 1000
├── docker-compose.yml      # Scraper service only — no broker included
├── requirements.txt        # requests, paho-mqtt, python-dotenv
├── .env.example            # All env vars documented with defaults
└── mosquitto/              # Reference Mosquitto config (not used by compose)
    └── config/
        └── mosquitto.conf
```

**`scraper.py` internal structure** (top-to-bottom):

| Section | Lines | Purpose |
|---------|-------|---------|
| Imports | 1–21 | stdlib + `requests`, `paho-mqtt`, `python-dotenv` |
| Logging setup | 27–35 | `basicConfig` before `load_dotenv()` so startup errors are visible |
| Config helpers | 43–55 | `_int_env()` — safe integer env-var parsing with fallback |
| Configuration | 62–127 | All `os.getenv()` calls; named timeout/retry constants |
| `HealthState` | 135–278 | Thread-safe singleton; all probe logic lives here |
| `WaterSmartClient` | 285–503 | HTTP session, auth, retry, data fetch |
| `parse_realtime_data` | 510–567 | Converts raw API JSON to `list[dict]` |
| `latest_record` | 570–578 | `max()` by ISO timestamp |
| `MQTTPublisher` | 585–690 | paho-mqtt v2 wrapper, `threading.Event` for connect state |
| Topic helpers + HA discovery | 697–770 | `make_topic()`, `publish_ha_discovery()` |
| `run_scrape` / `_run_scrape_inner` | 778–845 | Top-level scrape cycle with exception guard |
| Health HTTP server | 852–902 | `_ReuseAddrHTTPServer`, `HealthHandler` |
| `main()` | 909–967 | Wires everything together, `threading.Timer` loop, signal handlers |

---

## Quick start

### 1. Copy and fill in the env file

```bash
cp .env.example .env
```

Minimum required variables:

```bash
# One of the two auth methods (see Authentication section)
WATERSMART_USERNAME=you@example.com
WATERSMART_PASSWORD=yourpassword

# Your MQTT broker
MQTT_BROKER=192.168.1.x
```

### 2. Run with Docker Compose

```bash
docker compose up -d
docker compose logs -f watersmart-scraper
```

Expected startup output:

```
2026-03-17 05:35:31,000 [INFO] WaterSmart MQTT Scraper starting up.
2026-03-17 05:35:31,001 [INFO] Target: https://mercerislandwa.watersmart.com
2026-03-17 05:35:31,001 [INFO] MQTT: 192.168.5.6:1883 (topic prefix: watersmart)
2026-03-17 05:35:31,001 [INFO] HA device: Water Meter (id: watersmart_meter)
2026-03-17 05:35:31,001 [INFO] Scrape interval: 60 minutes
2026-03-17 05:35:31,003 [INFO] Health server listening on :8080  (/livez /readyz /healthz)
2026-03-17 05:35:32,996 [INFO] Attempting credential-based login...
2026-03-17 05:35:35,040 [INFO] Credential login succeeded.
2026-03-17 05:35:35,045 [INFO] Connected to MQTT broker 192.168.5.6:1883
2026-03-17 05:35:35,059 [INFO] Published HA discovery for sensor: watersmart_meter_consumption
2026-03-17 05:35:35,064 [INFO] Published HA discovery for sensor: watersmart_meter_leak
2026-03-17 05:35:35,070 [INFO] Published HA discovery for sensor: watersmart_meter_last_read
2026-03-17 05:35:35,064 [INFO] --- Scrape cycle starting ---
2026-03-17 05:35:35,296 [INFO] Parsed 2467 records.
2026-03-17 05:35:35,332 [INFO] Latest reading: 7.48 gal at 2026-03-16T08:00:00+00:00
2026-03-17 05:35:35,332 [INFO] --- Scrape cycle complete ---
```

### 3. Run locally (without Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in values
python scraper.py
```

---

## Authentication

Two methods are supported. **Credential login is recommended** for long-running
deployments because cookies expire in roughly 24 hours.

### Method A — Username / password (recommended)

```bash
WATERSMART_USERNAME=you@example.com
WATERSMART_PASSWORD=yourpassword
```

**Login flow** (reverse-engineered from the WaterSmart portal):

1. `GET /index.php/welcome/login` — scraper extracts the hidden CSRF `token`
   field from the HTML form with a regex.
2. `POST /index.php/welcome/login?forceEmail=1` — form-encoded body:
   `email=`, `password=`, `token=`. The `?forceEmail=1` query parameter is
   required; omitting it causes a redirect loop.
3. Success is detected by checking whether the response body contains the word
   `"logout"` (case-insensitive). WaterSmart redirects to the dashboard on
   success, which always has a Logout link in the nav. There is no JSON
   confirmation body.
4. The `requests.Session` stores the resulting `PHPSESSID` and encrypted session
   cookies automatically for all subsequent requests.

**Automatic session renewal**: if a data fetch returns 401, 403, or silently
redirects to the login page (status 200, URL contains `"login"`), the scraper:
- Clears all session cookies
- Calls `_auth_with_credentials()` once
- Retries the data fetch
- Aborts the scrape cycle and marks health degraded if re-auth also fails

### Method B — Session cookies (short-lived)

```bash
PHPSESSID=abc123...
SESSION_COOKIE=def456...
SESSION_COOKIE_NAME=a64b84d4419675c8425cb15c2f5fda28
```

Obtain values from browser DevTools:
1. Log into the portal in your browser.
2. Open DevTools → Network tab → click any XHR request to the site.
3. Find the `Cookie:` request header.
4. Copy `PHPSESSID=<value>` and the long hex cookie `<name>=<value>`.

The long hex cookie name (`a64b84d4419675c8425cb15c2f5fda28`) is the encrypted
session cookie. Its name is fixed per WaterSmart deployment — for Mercer Island
it is `a64b84d4419675c8425cb15c2f5fda28`. Set `SESSION_COOKIE_NAME` if your
deployment uses a different name.

Cookie auth priority: if `PHPSESSID` **or** `SESSION_COOKIE` is set, cookie
auth is attempted first and credential auth is skipped. If cookies are invalid,
the scraper falls back to credentials only if `WATERSMART_USERNAME` and
`WATERSMART_PASSWORD` are also set.

---

## MQTT topics and payloads

All topics are prefixed with `MQTT_TOPIC_PREFIX` (default: `watersmart`).

### `{prefix}/latest` — retained

Published after every successful scrape. Contains the single most-recent
reading, selected by finding the record with the highest ISO `timestamp` value.
Retained so Home Assistant always has a value after a broker restart.

```json
{
  "account": "00202650003",
  "scraped_at": "2026-03-17T05:35:35+00:00",
  "timestamp": "2026-03-16T08:00:00+00:00",
  "consumption_gallons": 7.48,
  "leak_gallons": 0.0,
  "flags": [],
  "scraped_at": "2026-03-17T05:35:35+00:00"
}
```

### `{prefix}/hourly` — non-retained

Published after every successful scrape. Contains all records returned by the
API (typically ~2400+ entries covering ~100 days of hourly data).

```json
{
  "account": "00202650003",
  "scraped_at": "2026-03-17T05:35:35+00:00",
  "record_count": 2467,
  "records": [
    {
      "timestamp": "2026-03-16T08:00:00+00:00",
      "consumption_gallons": 7.48,
      "leak_gallons": 0.0,
      "flags": [],
      "scraped_at": "2026-03-17T05:35:35+00:00"
    },
    ...
  ]
}
```

### `{prefix}/debug/raw` — non-retained, DEBUG only

Published **only** when `LOG_LEVEL=DEBUG` is set **and** the API response
parses to zero records. Contains the raw API response for diagnosis. Gated
behind DEBUG to avoid publishing potentially sensitive account/billing data
to the broker under normal operation.

### `homeassistant/sensor/{uid}/config` — retained

HA auto-discovery config messages. Published once on every MQTT (re)connect.
See [Home Assistant integration](#home-assistant-integration) for details.

---

## Home Assistant integration

The scraper publishes MQTT discovery messages on every (re)connect to the broker,
so Home Assistant will auto-create three sensor entities grouped under a single
device.

### Auto-created entities

| Entity | `unique_id` | Value template | Unit | Device class |
|--------|-------------|----------------|------|--------------|
| Water Usage | `{HA_DEVICE_ID}_consumption` | `value_json.consumption_gallons` | gal | `water` |
| Water Leak Gallons | `{HA_DEVICE_ID}_leak` | `value_json.leak_gallons` | gal | — |
| Water Meter Last Read | `{HA_DEVICE_ID}_last_read` | `value_json.timestamp` | — | `timestamp` |

All three read from the `{prefix}/latest` state topic (retained).

### Device grouping

All entities appear under a single HA device:
- **Name**: `HA_DEVICE_NAME` (default: `Water Meter`)
- **Identifier**: `HA_DEVICE_ID` (default: `watersmart_meter`)
- **Manufacturer**: `WaterSmart`
- **Model**: `AMI Water Meter`

### Discovery topic format

```
{HA_DISCOVERY_PREFIX}/sensor/{HA_DEVICE_ID}_{sensor_name}/config
```

Example: `homeassistant/sensor/watersmart_meter_consumption/config`

The discovery prefix must match what is configured in Home Assistant's MQTT
integration (default: `homeassistant`).

### Re-discovery on reconnect

HA discovery messages are published every time the MQTT `on_connect` callback
fires — including after a broker restart or network interruption. This ensures
the device/entity config is never permanently lost.

---

## Health endpoints

The scraper runs a minimal HTTP server on `HEALTH_PORT` (default: `8080`),
bound to `HEALTH_BIND` (default: `0.0.0.0`). No authentication. The server
uses `SO_REUSEADDR` to survive rapid container restarts.

### `GET /livez`

Is the process alive and past initial startup?

- **200** once `health.set_initialised()` has been called (after first MQTT
  connect, before first scrape)
- **503** before that point

```json
{"status": "ok", "initialised": true, "uptime_seconds": 17}
```

### `GET /readyz`

Are all subsystems healthy and is scrape data fresh?

Fails (503) if **any** of these are false:
- `initialised` — startup complete
- `watersmart_authenticated` — last auth attempt succeeded
- `mqtt_connected` — MQTT broker connected
- `last_scrape_fresh` — last successful scrape was within `HEALTH_SCRAPE_STALE_SECONDS`
  (default: `2 × SCRAPE_INTERVAL_MINUTES × 60`)

```json
{
  "status": "ok",
  "checks": {
    "initialised": true,
    "watersmart_authenticated": true,
    "mqtt_connected": true,
    "last_scrape_fresh": true
  }
}
```

### `GET /healthz`

Full diagnostic payload. Always returns 200/503 matching readiness, plus all
detail fields.

```json
{
  "status": "ok",
  "checks": { ... },
  "uptime_seconds": 42,
  "initialised": true,
  "watersmart": {
    "authenticated": true,
    "last_auth_at": "2026-03-17T05:35:32.701462+00:00",
    "last_error": null
  },
  "mqtt": {
    "connected": true,
    "tls": false,
    "last_error": null
  },
  "scraper": {
    "last_scrape_at": "2026-03-17T05:35:32.948367+00:00",
    "last_scrape_age_seconds": 15,
    "last_scrape_success": true,
    "last_scrape_record_count": 2467,
    "last_scrape_error": null,
    "scrape_total": 1,
    "scrape_failures": 0,
    "stale_threshold_seconds": 7200
  }
}
```

Note: the MQTT broker host/port is intentionally **omitted** from `/healthz`
to avoid leaking internal network topology to anything that can reach the
unauthenticated health port.

### Kubernetes probe configuration

```yaml
livenessProbe:
  httpGet:
    path: /livez
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /readyz
    port: 8080
  initialDelaySeconds: 15
  periodSeconds: 60
  failureThreshold: 3
```

Set `HEALTH_BIND=0.0.0.0` (default) so the kubelet can reach the port.
If you are not using Kubernetes and do not want the health port exposed,
set `HEALTH_BIND=127.0.0.1`.

---

## Full configuration reference

All configuration is via environment variables. Copy `.env.example` to `.env`
and fill in values. The `.env` file is loaded by `python-dotenv` at startup;
all variables can also be passed directly as Docker env vars.

### WaterSmart

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `WATERSMART_URL` | `https://mercerislandwa.watersmart.com` | No | Base URL of the WaterSmart portal. Must be `https://` — a warning is logged if not. |
| `ACCOUNT_NUMBER` | `""` | No | Utility account number. Included in MQTT payloads as `"account"` for reference only — not used in API calls. |

### Authentication

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `WATERSMART_USERNAME` | `""` | Yes* | Login email address. |
| `WATERSMART_PASSWORD` | `""` | Yes* | Login password. |
| `PHPSESSID` | `""` | Yes* | PHP session cookie value (alternative to credentials). |
| `SESSION_COOKIE` | `""` | Yes* | Encrypted session cookie value (alternative to credentials). |
| `SESSION_COOKIE_NAME` | `a64b84d4419675c8425cb15c2f5fda28` | No | Name of the encrypted session cookie. The default is specific to `mercerislandwa.watersmart.com`. |

\* At least one auth method must be configured: either `WATERSMART_USERNAME` +
`WATERSMART_PASSWORD`, or `PHPSESSID` and/or `SESSION_COOKIE`.

Auth priority: cookie auth is attempted first if either `PHPSESSID` or
`SESSION_COOKIE` is set. Credential auth is used if neither cookie is set, or
as a fallback when the cookie session expires.

### MQTT

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `MQTT_BROKER` | `localhost` | Yes | Broker hostname or IP address. |
| `MQTT_PORT` | `1883` | No | Broker TCP port. Use `8883` for TLS. |
| `MQTT_USERNAME` | `""` | No | MQTT username. |
| `MQTT_PASSWORD` | `""` | No | MQTT password. |
| `MQTT_TOPIC_PREFIX` | `watersmart` | No | Prefix for all published topics. |
| `MQTT_CLIENT_ID` | `watersmart-scraper` | No | MQTT client identifier. Must be unique on the broker. |
| `MQTT_TLS` | `false` | No | Set `true` to enable TLS. Strongly recommended when `MQTT_USERNAME` is set. Uses the system CA bundle to verify the broker certificate. |
| `MQTT_TLS_INSECURE` | `false` | No | Set `true` to disable broker certificate verification. **Only for self-signed certs in local/dev environments.** Logs a prominent WARNING when active. Never use in production. |

### Home Assistant

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `HA_DEVICE_NAME` | `Water Meter` | No | Display name for the device in Home Assistant. |
| `HA_DEVICE_ID` | `watersmart_meter` | No | Unique identifier for the HA device and entity IDs. Changing this will create duplicate entities in HA until the old ones are manually removed. |
| `HA_DISCOVERY_PREFIX` | `homeassistant` | No | Must match the MQTT discovery prefix configured in HA (Settings → Devices & Services → MQTT). |

### Scraper behaviour

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `SCRAPE_INTERVAL_MINUTES` | `60` | No | How often to poll the API, in minutes. The API updates hourly — polling more often is harmless but redundant. |

### Health server

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `HEALTH_PORT` | `8080` | No | TCP port for the health HTTP server. |
| `HEALTH_BIND` | `0.0.0.0` | No | Bind address. Use `0.0.0.0` for Kubernetes kubelet probes. Use `127.0.0.1` to restrict access to localhost only. |
| `HEALTH_SCRAPE_STALE_SECONDS` | `SCRAPE_INTERVAL_MINUTES × 120` | No | How many seconds after the last successful scrape before `/readyz` returns 503. Default is 2× the scrape interval (7200s for the 60-minute default). |

### Logging

The log level is controlled by Python's standard `LOG_LEVEL` convention. Set
via the `logging.basicConfig(level=...)` call in the script — currently
hardcoded to `INFO`. To enable debug output, change `level=logging.INFO` to
`level=logging.DEBUG` or add:

```bash
# In Docker
environment:
  - PYTHONUNBUFFERED=1
```

Debug output enables:
- CSRF token extraction confirmation
- Per-record parse counts
- Raw API response dump (first 2000 chars) when the response cannot be parsed
- Raw API payload publish to `watersmart/debug/raw` when zero records parsed

---

## Docker and Kubernetes deployment

### Docker Compose (existing broker)

The `docker-compose.yml` contains only the scraper service — no broker is
included. Point `MQTT_BROKER` at your existing broker (e.g. Home Assistant's
Mosquitto add-on).

```yaml
services:
  watersmart-scraper:
    build: .
    env_file: .env
    restart: unless-stopped
```

The container exposes port `8080` for health probes. To expose it to the host:

```yaml
services:
  watersmart-scraper:
    build: .
    env_file: .env
    restart: unless-stopped
    ports:
      - "8080:8080"
```

### Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY scraper.py .
RUN useradd -m -u 1000 scraper && chown -R scraper:scraper /app
USER scraper
EXPOSE 8080
CMD ["python", "-u", "scraper.py"]
```

Runs as non-root UID 1000. `-u` disables stdout buffering so logs appear
immediately in `docker logs`.

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: watersmart-scraper
spec:
  replicas: 1          # must be 1 — multiple replicas would duplicate MQTT publishes
  selector:
    matchLabels:
      app: watersmart-scraper
  template:
    metadata:
      labels:
        app: watersmart-scraper
    spec:
      containers:
      - name: scraper
        image: watersmart-scraper:latest
        envFrom:
        - secretRef:
            name: watersmart-secrets
        ports:
        - containerPort: 8080
          name: health
        livenessProbe:
          httpGet:
            path: /livez
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /readyz
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 60
          failureThreshold: 3
```

Store credentials in a Kubernetes Secret:

```bash
kubectl create secret generic watersmart-secrets \
  --from-literal=WATERSMART_USERNAME=you@example.com \
  --from-literal=WATERSMART_PASSWORD=yourpassword \
  --from-literal=MQTT_BROKER=192.168.1.x \
  --from-literal=MQTT_USERNAME=mqttuser \
  --from-literal=MQTT_PASSWORD=mqttpass
```

---

## Architecture and implementation notes

### Threading model

The process runs four concurrent threads:

| Thread | Purpose |
|--------|---------|
| `MainThread` | Runs `main()`, blocks on `stop_event.wait()`, handles SIGTERM/SIGINT |
| `health-server` (daemon) | `HTTPServer.serve_forever()` — handles health probe requests |
| paho network loop (daemon) | `client.loop_start()` — handles MQTT I/O, fires callbacks |
| `scrape-timer` (daemon) | `threading.Timer` — triggers `run_scrape()` every N minutes |

`HealthState` is the shared state object. All mutations are guarded by a single
`threading.Lock`. All reads (`liveness()`, `readiness()`, `deep_health()`)
acquire the same lock, including `_readiness_locked()` which is called inside
`deep_health()` with the lock already held.

### MQTT connection lifecycle

- `MQTTPublisher` wraps paho-mqtt v2 (`CallbackAPIVersion.VERSION2`).
- Connection state is tracked with `threading.Event` (`_connected_event`) rather
  than a plain bool to avoid data races with the paho thread.
- `loop_start()` is called only once (`_loop_started` guard) to prevent duplicate
  paho background threads on reconnect.
- `_on_connect` spawns a daemon thread to re-publish HA discovery messages after
  every (re)connect, ensuring HA always has current discovery config.
- On MQTT connect timeout, `loop_stop()` is called to clean up the background
  thread before returning failure.

### HTTP retry and session management

- All `GET` requests go through `_get()` which retries up to 3 times with
  2-second initial backoff doubling each attempt (2s, 4s, 8s).
- Session expiry is detected two ways: HTTP 401/403 status, or HTTP 200 with a
  response URL containing `"login"` (WaterSmart silently redirects expired
  sessions rather than returning 4xx).
- 5xx and other non-auth errors from `_verify_session()` are treated as
  transient and do not trigger re-authentication.
- Before credential re-auth, `session.cookies.clear()` is called to ensure no
  expired tokens are sent alongside new ones.

### Scrape cycle

`run_scrape()` is a thin wrapper that catches all exceptions so the
`threading.Timer` loop cannot be killed by an unhandled error. The actual work
is in `_run_scrape_inner()`.

One UTC timestamp (`scraped_at`) is computed at the start of each cycle and
reused throughout — all records in a single cycle have the same `scraped_at`
value, and the `latest` payload also uses it rather than computing a new one.

Record parsing (`parse_realtime_data()`) is per-entry fault-tolerant: one
malformed entry logs a warning and is skipped; the rest of the series is still
processed.

### Scheduler

`schedule` library has been replaced with `stdlib threading.Timer` (recursive
self-scheduling). This removes one dependency and eliminates the issue of
`schedule` silently swallowing exceptions from jobs.

### Signal handling

`SIGTERM` and `SIGINT` both set `stop_event`. The main thread wakes, cancels
the pending timer, disconnects MQTT gracefully, and exits. This is required for
clean `docker stop` and `kubectl delete pod` behavior.

---

## WaterSmart API reference

The following endpoints were reverse-engineered from browser traffic to
`mercerislandwa.watersmart.com`. All paths are relative to `WATERSMART_URL`.

### `GET /index.php/rest/v1/Chart/RealTimeChart`

Returns hourly usage data for the authenticated account. No query parameters
required — the account is inferred from the session.

**Request headers** (required to avoid 403):
```
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...
X-Requested-With: XMLHttpRequest
Referer: https://mercerislandwa.watersmart.com/index.php/trackUsage
```

**Response shape**:
```json
{
  "data": {
    "series": [
      {
        "read_datetime": 1742022000,
        "gallons": 7.48,
        "leak_gallons": 0,
        "flags": null
      }
    ]
  }
}
```

- `read_datetime`: Unix timestamp in **seconds** (UTC). Represents the start of
  the one-hour window.
- `gallons`: water consumption for that hour, as a float. May be `0` for hours
  with no usage.
- `leak_gallons`: gallons attributed to a leak detector for that hour. Usually
  `0`.
- `flags`: array of flag strings or `null`. Typically `null` or `[]` under
  normal conditions.

The API typically returns ~2400+ entries covering roughly 100 days of history.
It does not support pagination or date range filtering — you always get the full
dataset.

**Session expiry behaviour**: a 200 response with a redirect to the login page
(response URL contains `"login"`) indicates session expiry. The server does not
return 401 or 403 in this case.

### `GET /index.php/welcome/login`

Returns the HTML login page. The scraper parses the CSRF `token` field:

```html
<input type="hidden" name="token" value="abc123...">
```

### `POST /index.php/welcome/login?forceEmail=1`

Form-encoded login. The `?forceEmail=1` parameter is required.

```
email=you@example.com&password=yourpassword&token=abc123...
```

On success: HTTP 200 redirect to the dashboard. The response body contains
`"logout"` (case-insensitive) in the navigation bar HTML.

On failure: HTTP 200 (the site does not use 401/403 for login failures). The
response body does not contain `"logout"`.

---

## Security model

### Credential storage

- Credentials are read from environment variables (or `.env` file) at startup.
- They are stored as module-level Python strings for the process lifetime.
- **Credentials are never written to disk** by the scraper.
- Credentials do not appear in log output under any normal operating condition.
- `.env` must never be committed to version control (add to `.gitignore`).

### Transport security

- **WaterSmart**: always HTTPS. The scraper warns at startup if `WATERSMART_URL`
  is not `https://`. TLS certificate verification is on by default via
  `requests` (system CA bundle).
- **MQTT**: unencrypted by default (common for local broker deployments). Set
  `MQTT_TLS=true` to enable TLS with broker cert verification. If your broker
  uses a self-signed certificate, set `MQTT_TLS_INSECURE=true` — this disables
  cert verification and logs a WARNING on every startup.

### Health endpoint

- The health server has no authentication.
- It binds to `HEALTH_BIND` (default `0.0.0.0`). If the health port should not
  be reachable externally, set `HEALTH_BIND=127.0.0.1`.
- The `/healthz` response intentionally omits the MQTT broker host/port to
  avoid leaking internal network topology.
- The `debug/raw` MQTT topic (which may contain account/billing data from the
  API) is only published when `LOG_LEVEL=DEBUG` is explicitly set.

### Session cookies

- Session cookies are stored in `requests.Session.cookies` (in-memory only).
- Before credential re-authentication, all cookies are cleared with
  `session.cookies.clear()` to prevent expired tokens from being sent alongside
  new ones.

---

## Known limitations and quirks

### WaterSmart API returns all history, not just recent data

The `RealTimeChart` endpoint returns the full historical dataset (~2400+ records)
on every call. There is no way to request only the latest reading via the API.
The scraper takes the maximum-timestamp record as the "latest" value.

### The hourly MQTT payload is large

A full `watersmart/hourly` publish is ~300–400 KB of JSON. If your MQTT broker
has a max message size configured (Mosquitto default is unlimited; some brokers
default to 256 KB), this may fail silently. Monitor `mqtt.last_error` in
`/healthz` if the hourly topic stops updating.

### Cookie session names vary by deployment

The encrypted session cookie name (`a64b84d4419675c8425cb15c2f5fda28`) is
specific to the Mercer Island WaterSmart instance. Other WaterSmart deployments
will have a different hex string. Set `SESSION_COOKIE_NAME` accordingly.

### Login success detection is fragile

Login success is detected by searching for the word `"logout"` in the response
body. This relies on the dashboard navigation containing a logout link. If
WaterSmart redesigns their nav, this heuristic could break. The CSRF token
extraction regex (`name="token"` before `value="..."`) would similarly break if
the attribute order changes in the HTML.

### No rate limiting awareness

The scraper makes no attempt to detect or honour rate limiting. Hourly polling
is conservative, but if the API starts returning 429 responses these are treated
as transient errors and retried.

### Replicas must be 1

Running multiple replicas would cause duplicate MQTT publishes, duplicate HA
discovery messages, and duplicate scrape cycles hitting the WaterSmart portal.
The deployment must be `replicas: 1`.

---

## Development setup

```bash
git clone <repo>
cd MercerMeterMaid

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Fill in WATERSMART_USERNAME, WATERSMART_PASSWORD, MQTT_BROKER at minimum

python scraper.py
```

### Linting

```bash
pip install ruff
ruff check scraper.py
```

### Checking health endpoints while running

```bash
curl -s http://localhost:8080/livez | python -m json.tool
curl -s http://localhost:8080/readyz | python -m json.tool
curl -s http://localhost:8080/healthz | python -m json.tool
```

### Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `requests` | 2.31.0 | HTTP session, cookie management, HTTPS to WaterSmart |
| `paho-mqtt` | 2.0.0 | MQTT client (v2 API with `CallbackAPIVersion.VERSION2`) |
| `python-dotenv` | 1.0.1 | `.env` file loading |

Note: `schedule` was an earlier dependency and has been removed. The scrape
loop now uses `threading.Timer` from the standard library.
