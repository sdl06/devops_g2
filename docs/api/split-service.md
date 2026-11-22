# Split Service API

Implemented Flask endpoints, checked against `services/split_service/split_app/views.py`
and `split_app/__init__.py` on 22 November 2026.

## Conventions

- Local base URL: `http://localhost:8001`.
- Paths have **no trailing slash**.
- POST, PUT and DELETE bodies use `Content-Type: application/json`.
- Monetary amounts use integer cents. Quantities use units of an item, not cents.
- Participant, session and allocation IDs are UUID strings. Bill and item IDs come from Bill Service.
- Bill versions are returned as strings; split versions are integers.
- Application errors use `{"error": "message"}`. Flask's default unknown-route and method errors may return HTML.

## Available endpoints

| Method | Path | Success | Purpose |
| --- | --- | --- | --- |
| GET | `/health` | 200 | Process health |
| GET | `/api/bills/{bill_id}` | 200 | Validate open bill and obtain CSRF token |
| POST | `/api/bills/{bill_id}/participants` | 200 | Join or resume this bill's session |
| GET | `/api/bills/{bill_id}/allocations` | 200 | Read current claims and remaining quantities |
| POST | `/api/bills/{bill_id}/claims` | 201 | Add a claim using version checks |
| POST | `/api/bills/{bill_id}/tip` | 200 | Create or replace your tip |
| GET | `/api/bills/{bill_id}/balance` | 200 | Preview your subtotal, tip and total |
| PUT | `/api/bills/{bill_id}/claims/{allocation_id}` | 200 | Replace your claim quantity |
| DELETE | `/api/bills/{bill_id}/claims/{allocation_id}` | 200 | Release your claim |
| POST | `/api/bills/{bill_id}/settlement` | 201 or 200 | Confirm simulated settlement |
| GET | `/api/bills/{bill_id}/progress` | 200 | Read staff checkout progress |
| GET | `/api/bills/{bill_id}/participants/me` | 200 | Restore the current guest |

## Cookies and CSRF

First GET the bill entry endpoint. It returns `csrf_token` and sets the Flask
`session` cookie and a `csrftoken` cookie. Keep these cookies and send the returned
token in the **`X-CSRFToken`** header on every POST, PUT and DELETE.

Joining sets an additional HTTP-only `split_resume_<session_id>` cookie. This
identifies the participant for claims and tips. The server derives the participant
from that cookie; do not send a participant ID in the claim or tip body.

Keep one cookie jar per guest. Clearing cookies loses the ability to resume that
participant; joining again creates another participant. GET requests do not require
CSRF. Missing or invalid CSRF on a write returns 403 before the view runs.

## 1. Health

```http
GET /health
```

Response, 200:

```json
{"status": "ok"}
```

This reports that the process responds; it does not test Bill Service or database connectivity.

## 2. Open the bill entry page

```http
GET /api/bills/12
```

Example response, 200:

```json
{
  "bill_id": "12",
  "bill_version": "3",
  "status": "open",
  "csrf_token": "<token>"
}
```

Returns 409 if the fetched bill does not match or is not open. Returns 503 if Bill
Service cannot be read. This endpoint does not create the split session, return
bill item details, or return the split version. Fetch item details from Bill
Service (`GET /bills/12`) and split state after joining.

## 3. Join or resume

```http
POST /api/bills/12/participants
Content-Type: application/json
X-CSRFToken: <token>

{"display_name": "Ana"}
```

Example response, 200 (also for a newly created participant):

```json
{
  "session_id": "<session UUID>",
  "participant_id": "<participant UUID>",
  "split_version": 0
}
```

The trimmed name must contain 1-100 characters. All guests joining a bill share
one split session. With a valid resume cookie, this resumes the existing
participant; it does not rename them. A name is still required when resuming.

Possible errors: 400 invalid name, 403 CSRF, 409 bill not open, 503 Bill Service
or database unavailable.

## 4. Read allocations

```http
GET /api/bills/12/allocations
```

Example response after a half-item claim:

```json
{
  "bill_version": "3",
  "split_version": 1,
  "bill_changed": false,
  "items": [{"item_id": "31", "remaining": "0.500000"}],
  "claims": [{
    "allocation_id": "<allocation UUID>",
    "item_id": "31",
    "participant_id": "<participant UUID>",
    "quantity": "0.500000",
    "needs_review": false
  }]
}
```

Poll about every 10 seconds for display updates and fetch again after a conflict.
Decimal strings may have different numbers of trailing zeros. `remaining` is the
bill item's quantity minus all claims in this split session. `bill_changed`
compares Bill Service's version with the split session's stored bill version;
it signals a change, not completed reconciliation. After staff corrections,
remaining quantities can be negative if existing claims exceed the corrected bill.

This GET currently requires no participant cookie. The split session must exist
(join first), otherwise it returns 404. Upstream or database failure returns 503.

## 5. Add an item claim

```http
POST /api/bills/12/claims
Content-Type: application/json
X-CSRFToken: <token>

{
  "item_id": "31",
  "quantity": "0.5",
  "bill_version": "3",
  "split_version": 0
}
```

Example response, 201:

```json
{"allocation_id": "<allocation UUID>", "split_version": 1}
```

- `quantity` must be positive and finite, less than 1 billion, with at most six decimal places. Prefer a decimal string.
- `split_version` must be a nonnegative JSON integer taken from the latest allocation state (or join response).
- `bill_version` must match Bill Service's current version.
- The item must belong to this bill and the requested quantity must fit what remains.
- This **adds** to the guest's existing claim for that item. Use PUT to replace it or DELETE to release it.

The version increment and claim save share a database transaction. Two requests
using the same split version cannot both succeed, even when claiming different
items. On 409, fetch allocation state again and ask the guest to review and
resubmit. Do not automatically repeat the same POST: there is no idempotency key,
and a successful request repeated with a fresh version adds another quantity.

Possible errors: 400 invalid body/claim, 403 CSRF or no matching participant,
404 no split session, 409 stale versions, missing item, insufficient remainder,
closed bill or already settled participant, 503 unavailable Bill Service/database.
An unsuccessful claim transaction leaves both allocations and split version unchanged.

## 6. Set or edit a tip

```http
POST /api/bills/12/tip
Content-Type: application/json
X-CSRFToken: <token>

{"kind": "fixed", "value": 200}
```

Response, 200:

```json
{"kind": "fixed", "value": 200}
```

`fixed` uses cents: `200` means EUR 2.00. `percent` uses basis points:

```json
{"kind": "percent", "value": 1500}
```

This means 15%. Percent values range from 0 to 10000 (100%). Fixed values range
from 0 to 2147483647. Values must be JSON integers. Set a fixed value of 0 to remove
the monetary tip. Posting again replaces this guest's previous choice; it does not
add another tip. Tips do not change the split version.

Possible errors: 400 invalid tip, 403 CSRF or participant not joined, 409 participant
already settled, 503 database unavailable. This endpoint does not fetch Bill Service
or check the bill's current open status.

## 7. Edit or release a claim

Use the `allocation_id` returned by the claim POST or the allocation list. Send
the guest's cookies and CSRF header on both operations.

| Operation | Example JSON body |
| --- | --- |
| PUT `/api/bills/12/claims/{allocation_id}` | `{"bill_version":"3","split_version":1,"quantity":"0.75"}` |
| DELETE `/api/bills/12/claims/{allocation_id}` | `{"bill_version":"3","split_version":1}` |

Both return 200 with `allocation_id`, the updated `split_version`, and a
`deleted` boolean. PUT treats the quantity as the new total for your claim. It
checks the new total against other guests' claims. DELETE also lets you release
a claim for a removed item when the bill is still open. A missing claim or one
owned by another guest returns 404. A stale version, unavailable quantity, or
existing settlement returns 409. Refresh allocations before retrying.

## 8. Preview your balance

GET `/api/bills/12/balance` with your resume cookie. Example 200 response:

```json
{"subtotal_cents": 750, "tip_cents": 200, "total_cents": 950, "bill_version": "3", "split_version": 2}
```

The response uses current Bill Service prices. If claims need review after a
correction, the endpoint returns 409. Use this response to show the amount
before asking the guest to confirm settlement.

## 9. Confirm simulated settlement

POST `/api/bills/12/settlement` with your cookies, CSRF header and the values the
guest confirmed from the balance response:

```json
{"bill_version": "3", "split_version": 2, "amount_cents": 950}
```

The first success returns 201 and records the verified amount. An identical
retry returns 200 if the saved confirmation still matches and needs no review.

```json
{"settlement": "simulated", "amount_cents": 950, "bill_version": "3", "split_version": 2, "needs_review": false}
```

The response contains the **confirmed** split version. Creating a settlement
advances the current split version, which you can get from the balance or
allocation endpoints. A changed amount or version returns 409. A guest with a
settlement record cannot edit their claims or tip. This operation simulates
settlement only.

## 10. Read staff progress

GET `/api/bills/12/progress` with `Authorization: Bearer <STAFF_API_TOKEN>`.
Set that environment variable on Split Service and keep its value on the staff
backend. Missing or invalid credentials return 401. An unset token returns 503.

```json
{
  "unallocated_subtotal_cents": 0,
  "allocated_unsettled_subtotal_cents": 0,
  "needs_review": false,
  "ready_to_close": true
}
```

Subtotals exclude tips. Readiness requires an open bill, full item allocation,
settlement of the corresponding guest balances and no review flags. Invalid
allocations can make both subtotals null and always block readiness. A settlement
that no longer matches the bill version or current balance also triggers review.
Bill Service owns the close action.

## 11. Restore the current guest

GET `/api/bills/12/participants/me` with your resume cookie. A missing or
unrecognized cookie returns 403.

```json
{
  "session_id": "<session UUID>",
  "participant_id": "<participant UUID>",
  "display_name": "Ana",
  "tip": {"kind": "fixed", "value": 200},
  "settlement": null
}
```

An unset tip is null. Once settled, `settlement` contains the recorded amount,
bill version, confirmed split version and stored `needs_review` flag.

## Complete curl example

Requires `curl`, `jq`, a running Split Service, and an open bill with a claimable
item. Replace bill `12` and item `31` with real IDs. Run commands in the same shell.

```sh
BASE_URL=http://localhost:8001
COOKIE_JAR=$(mktemp)

# Keep Flask's session cookie as well as the returned CSRF token.
ENTRY=$(curl --fail-with-body -sS -c "$COOKIE_JAR" "$BASE_URL/api/bills/12")
CSRF_TOKEN=$(printf '%s' "$ENTRY" | jq -r '.csrf_token')

# Join; save the new resume cookie into the same jar.
curl --fail-with-body -sS -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
  -H 'Content-Type: application/json' -H "X-CSRFToken: $CSRF_TOKEN" \
  -d '{"display_name":"Ana"}' "$BASE_URL/api/bills/12/participants"

STATE=$(curl --fail-with-body -sS -b "$COOKIE_JAR" "$BASE_URL/api/bills/12/allocations")
CLAIM=$(printf '%s' "$STATE" | jq \
  '{item_id:"31", quantity:"0.5", bill_version:.bill_version, split_version:.split_version}')
curl --fail-with-body -sS -b "$COOKIE_JAR" \
  -H 'Content-Type: application/json' -H "X-CSRFToken: $CSRF_TOKEN" \
  -d "$CLAIM" "$BASE_URL/api/bills/12/claims"

curl --fail-with-body -sS -b "$COOKIE_JAR" \
  -H 'Content-Type: application/json' -H "X-CSRFToken: $CSRF_TOKEN" \
  -d '{"kind":"percent","value":1500}' "$BASE_URL/api/bills/12/tip"

rm "$COOKIE_JAR"
```

## Browser example

For a frontend served through the same origin (for example through a proxy):

```js
const entryResponse = await fetch('/api/bills/12', { credentials: 'include' });
if (!entryResponse.ok) throw new Error(await entryResponse.text());
const entry = await entryResponse.json();

const joinResponse = await fetch('/api/bills/12/participants', {
  method: 'POST',
  credentials: 'include',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': entry.csrf_token,
  },
  body: JSON.stringify({ display_name: 'Ana' }),
});
if (!joinResponse.ok) throw new Error(await joinResponse.text());
const participant = await joinResponse.json();
```

For different frontend/backend origins, configure credentialed CORS before using
absolute backend URLs. CORS is not configured by the current service. Cookies use
`SameSite=Lax`, so deployment on different sites also needs an agreed cookie policy.

## Backend configuration

See `services/split_service/README.md` for installation and migrations. Set
`BILL_SERVICE_URL` to Nini's origin (for example `http://localhost:8000`) and use a
stable `SECRET_KEY`. The service calls `GET {BILL_SERVICE_URL}/bills/{id}` without
a trailing slash, using a three-second timeout. Enable `COOKIE_SECURE=true` with HTTPS.
