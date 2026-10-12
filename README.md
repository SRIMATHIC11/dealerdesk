# VIKMO DealerDesk : **Track: aiml**


![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white)
![Django REST Framework](https://img.shields.io/badge/DRF-A30000?style=for-the-badge&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-F55036?style=for-the-badge&logo=groq&logoColor=white)
![scikit--learn](https://img.shields.io/badge/scikit--learn-F7931E?style=for-the-badge&logo=scikitlearn&logoColor=white)

A dealer ordering platform for a motorcycle and car parts distributor: a searchable catalogue with live stock, reliable draft and confirmed orders, a tool-calling assistant for dealers, a supplier catalogue sync, and four-week demand forecasts that drive reorder suggestions.

Built with Django 5.2, Django REST Framework, PostgreSQL and React.

## Scope

| Part | What it covers | Status |
|---|---|---|
| A1 Backend core | Products, inventory, dealers, draft orders | Implemented |
| C Dealer assistant | Tool-calling LLM with retrieval, live stock and draft orders | Implemented |
| D Forecasting and reorder | 160-row forecast and live reorder suggestions | Implemented |
| A2 Order engine (optional) | Confirm, dispatch, deliver, cancel, stock safety, idempotency | Implemented |
| B Supplier sync (optional) | Paginated, rate-limited, fault-tolerant catalogue import | Implemented |
| E Dealer portal (optional) | React web interface on top of the API | Implemented |

## Quick start

Requirements: Python 3.11+, PostgreSQL and Git. Node is needed only to modify or rebuild the frontend. No Docker, Redis, vector database or cloud account is required.

```bash
python3 -m venv .venv
source .venv/bin/activate          # fish: source .venv/bin/activate.fish
pip install -r requirements.txt
cp .env.example .env               # then set DATABASE_URL (and GROQ_API_KEY for the assistant)
python manage.py migrate --noinput
python manage.py seed_data
python manage.py seed_data         # safe to run repeatedly
python manage.py runserver 0.0.0.0:8000 --noreload
```

Create an empty PostgreSQL database first, for example `createdb dealerdesk`, and point `DATABASE_URL` at it. If the username or password contains reserved characters, URL-encode them. Migrations create every table.

Open **http://localhost:8000**, choose a dealer in the header, find a part, add it to the basket and create a draft. Confirming an order deducts stock; cancelling a confirmed order restores it exactly once.

A fresh seed loads 600 products, 600 inventory records and 25 dealers, and no orders. Running the seed again never overwrites stock or prices that have changed since.

### Windows

A helper starts an isolated local PostgreSQL cluster on port 55432, leaving any existing PostgreSQL service untouched. Its data and generated credentials stay in the ignored `.local/` folder.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/local_postgres.py start
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe manage.py seed_data
.\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000 --noreload
```

Use `scripts/local_postgres.py status` or `stop` to manage that cluster. Add PostgreSQL's `bin` directory to `PATH` if it is not in the standard location.

## Configuration

Values are read from the process environment, or from a root `.env` file (`python-dotenv`). Real environment variables take precedence.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Required. PostgreSQL connection URL. SQLite is not supported. |
| `GROQ_API_KEY` | Key for the assistant's LLM provider. Without it, the chat endpoint returns a clear 503. |
| `LLM_PROVIDER` | Optional. `groq` for this setup; if unset, an available provider key is detected. |
| `LLM_MODEL` | Optional model override. |
| `SUPPLIER_API_URL` | Supplier API base URL (the local mock uses `http://127.0.0.1:8099`). |
| `SUPPLIER_API_KEY` | Supplier API key (the local mock uses `dev-supplier-key`). |
| `DJANGO_DEBUG` | Defaults to `1`. Use `0` when hosting. |
| `DJANGO_SECRET_KEY` | Private random secret, required when hosting. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames, without scheme or path, when hosting. |

`GEMINI_API_KEY`, `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` select alternative transports. Those have not been verified with live keys. Never commit real keys.

An absent optional integration does not stop migrations, seeding or the other endpoints from working. A missing supplier configuration makes only the sync return 502, without touching the catalogue.

## Dealer assistant

- **Provider:** Groq
- **Model:** `openai/gpt-oss-120b`, called through Groq's tool-calling API

The assistant is a retrieval-augmented, tool-calling system. The model can call three application-owned tools: `search_parts`, `check_stock` and `create_draft_order`.

- **Retrieval.** Weighted lexical search over live product metadata, with SKU and vehicle matching, synonyms and BM25-style scoring. It does not use embeddings.
- **Grounding.** Every price and stock figure in a reply is rendered from PostgreSQL immediately before the reply is returned, never taken from model text or earlier turns.
- **Safe orders.** The assistant can only create drafts, through the same order service as the REST API. It never confirms an order, and a draft never reserves stock.
- **Untrusted catalogue text.** Supplier descriptions are excluded from the model's context, so instructions hidden in catalogue data cannot influence it.
- **Memory.** Conversations persist in PostgreSQL per `session_id`; sessions do not share memory. A short session lease prevents two turns from interleaving.

To check the live provider after setting `GROQ_API_KEY`:

```bash
python manage.py check_assistant                  # greeting, retrieval and grounding
python manage.py check_assistant --create-draft   # also creates one real draft; stock is unchanged
```

Neither command prints credentials. Both paths were verified against Groq on the development machine; that covers the conversations exercised, not every future request or quota condition.

## Forecasting and reorder suggestions

`ml/forecast.csv` holds 160 rows: four weekly forecasts (starting 2026-09-28) for each of the 40 products. It is produced by a reproducible training script, not trained at request time. The model accounts for known promotions, the Diwali-linked festive lift, sparse products and new products, and it was validated chronologically with no use of future data.

On the historical holdout it reached **MAE 6.34, RMSE 10.45 and WAPE 18.61%**, against 25.71% WAPE for the best simple average baseline. This is historical validation and does not predict the score on unseen future weeks.

`GET /api/reorder-suggestions/` reads live inventory on every request and applies the contract's safety-stock formula to the committed forecast.

```bash
python -m ml.validate_forecast    # checks the 160-row file against the data
python -m ml.train_forecast       # regenerates the forecast
```

## Supplier sync

`POST /api/sync/supplier/` imports the supplier catalogue. It fetches every page first, retrying rate limits and temporary failures, and only then applies the changes in one transaction. If the full feed cannot be fetched, nothing changes and the response is 502 `SUPPLIER_UNAVAILABLE`. Invalid rows are skipped and reported, the latest valid duplicate wins, and supplier stock is never copied into available inventory.

Try it with the supplied mock, which includes pagination, rate limiting and temporary failures:

```bash
python supplier_mock/mock_supplier.py            # prints the URL and key
python supplier_mock/mock_supplier.py --outage   # simulates a permanent failure
```

## Frontend

The React portal lives in `frontend/` and is served by Django from `portal/`. Node is only needed to change it (Node 22.12 or newer):

```bash
cd frontend
npm ci
npm run dev           # Vite proxies /api to Django on port 8000
npm run lint
npm run format:check
npm run build         # writes the compiled assets into portal/
```

After a rebuild, restart `runserver --noreload` so the cached page picks up the new asset names, and commit both source and compiled output. Browser tests (`npm run test:e2e`) need Playwright's browser: run `npx playwright install chromium`, or set `PW_BROWSER_CHANNEL` to use an installed one. They create test products and orders in the target database.

## Tests

```bash
pip install -r requirements-dev.txt
python manage.py test --noinput
python manage.py makemigrations --check --dry-run
ruff check .
ruff format --check .
```

The database role needs `CREATEDB`, because Django creates a separate test database.

**Results:** 47 backend tests and five automated browser tests pass. Smoke checks on a clean database pass 10/10 for the AI/ML track, 9/9 for Django and 12/12 for all parts. These local checks do not replace the grader's hidden tests.

The smoke test expects the original seed counts and creates records, so run it on a freshly seeded database:

```bash
python smoke_test.py --base-url http://localhost:8000 --track aiml
python smoke_test.py --base-url http://localhost:8000 --all
```

To repeat the whole check from scratch, this helper creates a uniquely named temporary PostgreSQL database, migrates, seeds twice, starts a temporary server, runs the smoke test and drops only that database. The `--all` option needs the supplier mock running and an LLM key configured:

```bash
python scripts/verify_submission.py --track all
```

## Project structure

```text
dealerdesk/    Django settings, root routes, WSGI
catalogue/     Product and inventory models, APIs, migrations
dealers/       Dealer model, APIs, migrations
orders/        Atomic order services, money snapshots, concurrency tests
assistant/     LLM provider transport, retrieval, prompts, tools, memory
forecasting/   Forecast artifacts and the live reorder API
suppliers/     Paginated fetch and retry, atomic catalogue apply
core/          Errors, pagination, seeding and live-check commands
portal/        Django page and compiled React assets
frontend/      React source, Vite build, lockfile, browser tests
ml/            Training script, validation, 160-row forecast
data/          Supplied CSV data (unchanged)
supplier_mock/ Supplied supplier mock
scripts/       Local PostgreSQL helper and the submission check
manage.py      Entry point
```

## Design notes

- **Services own business rules.** Order, stock and supplier changes happen in service functions. PostgreSQL row locks serialise status changes and stock updates, so stock is never oversold. Unique constraints and a locked daily counter (IST) keep order numbers unique and duplicate requests safe.
- **Exact money.** Amounts use `Decimal`, with GST calculated per line and rounded half-up to the paisa. A draft shows the current price; confirming freezes prices and names.
- **No network calls inside transactions.** Supplier HTTP calls and LLM calls finish before any database transaction that depends on them begins.
- **One error shape.** Every failure, including framework errors, uses the same JSON structure with a stable error code.

## Assumptions and limitations

- There is no authentication, matching the assignment; use synthetic demo data only.
- Retrieval is lexical, so it can miss unusual wording; replies are deliberately constrained to the three tools.
- Supplier stock is never added to available inventory; only the catalogue fields are synced.
- A draft never reserves stock, and the assistant never says it does.
- Live-provider behaviour was verified for Groq only; the other provider transports are implemented but not verified with live keys.
- Hosting is optional and not needed for evaluation. To host the app, run one Django service (it serves the React assets) with a hosted PostgreSQL, and set `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS`. Free tiers can have quotas and cold starts.

