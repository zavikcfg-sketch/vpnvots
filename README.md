# vpnsell

Telegram bot for selling VLESS VPN subscriptions, backed by the **H1Cloud VLESS node API**.

The bot lets users buy tariff plans, activate a free trial, view their
subscriptions with copy-paste links and QR codes, and renew. Provisioning
(create / renew / limits / links) happens on the H1Cloud node over its HTTPS API.

Payments are wired to **2328.io** (crypto). Customers top up their internal
balance with crypto; a signed webhook credits the balance, and the buy/renew
flow spends from it. An admin can still credit balances manually. Disable
payments by leaving `PAY_ENABLED=false`.

## Features

- 🛒 Buy plans (configurable via the `PLANS` env var)
- 🎁 One-time free trial
- 🔑 "My subscriptions" with subscription URL, raw VLESS keys, and QR code
- 🔄 Renew an existing subscription
- 💰 Internal balance (admin credits manually for now)
- ⚙️ Admin panel: stats, credit balance, node health check
- 🔗 Referral payload support (`/start ref_<id>`) stored for later use

## Project layout

```
bot.py                     entrypoint (python bot.py)
vpnsell/
  config.py                env/.env settings + Plan parsing
  db.py                    async SQLite (users, subscriptions, orders)
  h1cloud.py               async H1Cloud VLESS API client
  payments.py              2328.io API client + HMAC signing
  poller.py                background task polling 2328.io for paid invoices
  vpn_service.py           provisioning: ties DB <-> node
  texts.py                 Russian user-facing text + formatting
  keyboards.py             inline keyboards
  qr.py                    subscription QR-code PNG
  bot/
    app.py                 dispatcher wiring + polling + payment poller
    handlers.py            user handlers (menu/buy/subs/trial/renew)
    topup.py               balance top-up via 2328.io
    admin.py               admin handlers
```

## Setup

1. Install dependencies (Python 3.11+):

   ```bash
   python -m venv .venv
   .venv/Scripts/activate      # Windows
   # source .venv/bin/activate # Linux/macOS
   pip install -r requirements.txt
   ```

2. Configure:

   ```bash
   cp .env.example .env
   ```

   Fill in at least:

   - `BOT_TOKEN` — from @BotFather
   - `ADMIN_IDS` — your Telegram user ID (comma-separated for several admins)
   - `H1_API_URL` — node API base **with** the `/api` suffix, e.g.
     `https://1.2.3.4:25626/api`
   - `H1_API_TOKEN` — from `vpn api token` on the node
   - `SUB_PUBLIC_URL` — subscription URL template, `{uuid}` is substituted,
     e.g. `https://1.2.3.4:25627/sub/{uuid}`
   - `H1_VERIFY_SSL=false` if the node uses a self-signed certificate

3. Run:

   ```bash
   python bot.py
   ```

## Configuring plans

`PLANS` is `id:title:days:price:traffic_gb:devices`, plans separated by `;`.
`traffic_gb` / `devices` of `0` mean unlimited. Example:

```
PLANS=m1:1 месяц:30:149:0:3;m3:3 месяца:90:399:0:3;m12:1 год:365:1199:0:5
```

The trial is configured separately via `TRIAL_DAYS`, `TRIAL_TRAFFIC_GB`,
`TRIAL_DEVICES` (set `TRIAL_DAYS=0` to disable).

## How provisioning maps to the node API

| Bot action      | Node API call                                   |
|-----------------|-------------------------------------------------|
| Buy / trial     | `POST /create` (or `PATCH /edit` if name exists)|
| Renew           | `PATCH /edit` with `days` (added to expiry)     |
| Show links      | `GET /clients/{name}` → `links` / `link`        |
| Admin health    | `GET /health`                                   |

Client names on the node are `tg<telegram_id>_<plan_or_trial>`, sanitized to
the node's allowed charset. The subscription URL handed to the user is built
from `SUB_PUBLIC_URL` using the client UUID returned by the node.

## Crypto payments (2328.io)

Customers top up their **internal balance** with crypto, then spend it on plans.
This keeps the money path in one place (the balance) and reuses the whole
buy/renew flow.

### Enable it

In `.env`:

```
PAY_ENABLED=true
PAY_PROJECT_UUID=<your project UUID from 2328.io>
PAY_API_KEY=<your API key from 2328.io>
PAY_CURRENCY=RUB
PAY_TTL_SECONDS=3600
PAY_POLL_INTERVAL=30
TOPUP_AMOUNTS=100,300,500,1000
```

No public URL, port, or TLS is needed — the bot only makes **outbound** calls
to 2328.io.

### How it flows

1. User taps 💰 Баланс → ➕ Пополнить → picks an amount.
2. Bot calls `POST /v1/payment` (HMAC-SHA256 signed) and stores a `pending`
   row in `payments`, keyed by the returned `uuid` with our own `order_id`.
3. User pays via the hosted checkout (the "Оплатить" button).
4. A **background poller** asks `POST /v1/payment/info` for every uncredited
   payment every `PAY_POLL_INTERVAL` seconds. On `paid`/`overpaid` it credits
   the balance **exactly once** (idempotent by `uuid`) and notifies the user.
5. "🔄 Проверить оплату" lets the user force an immediate check instead of
   waiting for the next poll — it credits through the same idempotent path.
6. Invoices older than `PAY_TTL_SECONDS` (+10 min grace) are marked `expired`
   and dropped from polling, so dead invoices don't pile up API calls.

### Polling vs webhooks

This build uses **polling**, not webhooks — chosen because it needs no public
HTTPS endpoint. Trade-off: a payment is recognised within one poll interval
(default 30s) rather than instantly. Lower `PAY_POLL_INTERVAL` (min 10s) for
faster pickup at the cost of more API calls; 2328.io allows 10 req/s per
project, so keep the interval sane if you expect many concurrent invoices.

### Security notes

- Crediting is idempotent by payment `uuid`, so an overlapping poll and a
  manual "check payment" tap can't double-credit.
- The API key is only ever used server-side. Keep `.env` out of git (it is in
  `.gitignore`).

### Manual balance top-up (admin)

Independently of crypto, an admin can credit any user from ⚙️ Админка →
💳 Начислить баланс (`USER_ID СУММА`). Useful for refunds or comps.

## Notes

- SQLite runs in WAL mode; all DB calls are wrapped with `asyncio.to_thread`
  and serialized with a lock, so they don't block the event loop.
- If node provisioning fails, the user is told and **no balance is deducted**.
