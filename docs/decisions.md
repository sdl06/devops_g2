# Decision records

Each record: context, decision, alternatives considered, consequences.

---

## Bill Service: FastAPI

**Context.** The brief allows Flask or FastAPI (or Express) for each service. The Bill Service
is mostly CRUD with many request bodies to validate, and the frontend developers needed a
reliable list of endpoints early.

**Decision.** Build the Bill Service with FastAPI, SQLAlchemy 2 and Alembic. The Split Service
uses Flask.

**Alternatives.** Flask for both services (one framework for the team), Express.

**Consequences.** Request bodies are validated from Pydantic schemas, so bad input is rejected
with `400` before our code runs. FastAPI generates an interactive API page at `/docs`, which the
frontend used for integration. The two services use different frameworks, which costs nothing
because they only communicate over HTTP/JSON; CI steps are the same for both (install,
`ruff`, `pytest`, Docker build).

---

## Bill data integrity: integer cents, copied prices and a version number

**Context.** Several guests split one bill while staff may still correct it. Totals must always
add up exactly, and the Split Service must notice when a bill changed under it.

**Decision.**
1. All money is stored and sent as integer cents (`price_cents`, `total_cents`).
2. A bill item copies the dish's `name` and `price_cents` when it is added.
3. Every change to a bill or its items increments `bills.version` (one `save()` helper in
   `app/routers/bills.py`), and bills follow `draft → open → closed`, with closed bills read-only.

**Alternatives.** Decimal or float amounts; bill items that reference the current dish price;
timestamps instead of a version counter; locking items once a guest claims them.

**Consequences.** No rounding errors, and old bills never change when the menu does. The Split
Service compares `version` to decide which claims to keep, so the Bill Service does not need to
know about claims (no calls from Bill to Split). A staff edit after guests claimed items is
allowed; the Split Service asks the affected guests to claim again.
