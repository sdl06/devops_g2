# Split Service

Flask API with SQLAlchemy persistence and Alembic migrations. Bill Service owns bills and items; this service stores sessions, participants, allocations, tips and simulated settlements.

## Local setup

Run from `services/split_service`:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY='replace-with-a-persistent-random-secret'
export BILL_SERVICE_URL='http://localhost:8000'
flask --app split_app db upgrade
flask --app split_app run --port 8001
```

`DATABASE_URL` defaults to a new local `split.sqlite3` file. Set it to a SQLAlchemy database URL for deployment, and install the corresponding database driver (Azure SQL requires an ODBC driver and `pyodbc`). `COOKIE_SECURE=true` enables HTTPS-only cookies. Keep `SECRET_KEY` stable across workers and restarts; the development fallback is ephemeral.

Production entry point: `gunicorn --bind 0.0.0.0:8001 wsgi:app`.

The new Alembic schema starts fresh; it does not import records from a Django database. The existing local `db.sqlite3` was empty and is left untouched. A deployment with existing Django data needs a separate data transfer before switching databases.

## Routes

All routes have **no trailing slash**:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Process health |
| GET | `/api/bills/{bill_id}` | Bill entry; issues CSRF token |
| POST | `/api/bills/{bill_id}/participants` | Join or resume |
| GET | `/api/bills/{bill_id}/allocations` | Claims and remaining quantities; poll every 10 seconds |
| POST | `/api/bills/{bill_id}/claims` | Version-checked item claim |
| POST | `/api/bills/{bill_id}/tip` | Set or edit own tip |

First GET the bill entry. Keep the response cookies and send its `csrf_token` as `X-CSRFToken` on POSTs. The separate HTTP-only `split_resume_<session id>` cookie identifies the participant. Browser requests must include credentials. Cross-origin deployment also requires an agreed CORS/cookie configuration with the frontend owner.

Bill Service requests use `GET {BILL_SERVICE_URL}/bills/{id}` with a three-second timeout, following `docs/api/bill-service.md`.

Claims send `item_id`, `quantity`, `bill_version`, and `split_version`. A conditional SQL UPDATE advances the split version only when the expected version matches. The update and allocation save share one transaction. A conflicting request gets 409; refresh before retrying. Bill Service failure gets 503 and leaves the claim unchanged.

Bill Service and Split Service have separate databases. A second bill check narrows the race with staff edits, but cannot make the two databases atomic. Bill correction and settlement reconciliation still need the agreed team policy.

See the [Split Service API guide](../../docs/api/split-service.md) for balance, claim edits, settlement, progress and guest restoration. Set `STAFF_API_TOKEN` to enable the staff progress endpoint.

## Verification

```sh
python -m unittest discover -s tests -v
flask --app split_app db check
```
