# Split Service frontend quick reference

Local Split Service runs at `http://localhost:8001`. Use your configured API origin
or a same-origin proxy in the deployed app. All paths below omit trailing slashes.
Replace `{bill_id}` with the ID from Bill Service.

## Start here

1. **Resolve the QR link.** If it contains a table ID, get the open bill from
   **Bill Service** with `GET /tables/{table_id}/current-bill`. Bill Service also
   provides item names, prices and quantities via `GET /bills/{bill_id}`.
2. **Open the split.** Call `GET /api/bills/{bill_id}`, keep the returned
   `csrf_token` in memory, and let the browser keep the cookies.
3. **Restore or join.** Call `GET /api/bills/{bill_id}/participants/me`. If it
   returns `403`, show the name form and POST to `/participants` using the full
   URL in the table below. The browser receives a private resume cookie.
4. **Render and refresh.** Fetch allocations and your balance after joining.
   Poll allocations about every 10 seconds. Refresh allocations and balance
   after a claim changes, and refresh balance after changing the tip.
5. **Settle.** Display the current balance and send the amount and versions
   from that exact preview when the guest confirms.

## URLs and payloads

Send `credentials: 'include'` on browser requests. For POST, PUT and DELETE,
send a JSON body with `Content-Type: application/json` and the
`X-CSRFToken` header. The browser sends the resume cookie. Keep
`participant_id` for matching your claims in the UI.

| Method and URL | When to use it | JSON body → success |
| --- | --- | --- |
| `GET /health` | Check whether the service is running. | No body → `200`, `{"status":"ok"}`. |
| `GET /api/bills/{bill_id}` | First Split Service call after opening the bill. | No body → `200`, `bill_id`, `bill_version`, `status`, `csrf_token`. |
| `POST /api/bills/{bill_id}/participants` | Join with a name or resume with an existing cookie. | `{"display_name":"Ana"}` → `200`, `session_id`, `participant_id`, `split_version`. |
| `GET /api/bills/{bill_id}/participants/me` | Restore the guest UI on reload. | No body → `200`, `session_id`, `participant_id`, `display_name`, `tip`, `settlement`. An unset tip or settlement is `null`. |
| `GET /api/bills/{bill_id}/allocations` | Show all claims and what remains. Join first so the split exists. | No body → `200`, `bill_version`, `split_version`, `bill_changed`, `items` (each with `item_id` and `remaining`), and `claims` (each with `allocation_id`, `item_id`, `participant_id`, `quantity`, `needs_review`). |
| `POST /api/bills/{bill_id}/claims` | **Add** a quantity to your claim for an item. | `{"item_id":"31","quantity":"0.5","bill_version":"3","split_version":0}` → `201`, `allocation_id` and updated `split_version`. |
| `PUT /api/bills/{bill_id}/claims/{allocation_id}` | **Replace** your claim with a new total quantity. | `{"quantity":"0.75","bill_version":"3","split_version":1}` → `200`, `allocation_id`, updated `split_version`, `deleted: false`. |
| `DELETE /api/bills/{bill_id}/claims/{allocation_id}` | Release your entire claim. This request takes a JSON body. | `{"bill_version":"3","split_version":2}` → `200`, `allocation_id`, updated `split_version`, `deleted: true`. |
| `POST /api/bills/{bill_id}/tip` | Set or replace your tip. | `{"kind":"fixed","value":200}` for €2.00, or `{"kind":"percent","value":1500}` for 15% → `200`, saved `kind` and `value`. Use fixed `0` for no tip. |
| `GET /api/bills/{bill_id}/balance` | Show what the current guest owes before settlement. | No body → `200`, `subtotal_cents`, `tip_cents`, `total_cents`, `bill_version`, `split_version`. |
| `POST /api/bills/{bill_id}/settlement` | Confirm the displayed amount in the payment simulation. | `{"bill_version":"3","split_version":2,"amount_cents":950}` → `201` on creation or `200` on a matching retry. Returns the saved amount, confirmed versions, `needs_review`, and `settlement: "simulated"`. |
| `GET /api/bills/{bill_id}/progress` | Show staff how much is unallocated or unsettled and whether the bill can close. | No body → `200`, `unallocated_subtotal_cents`, `allocated_unsettled_subtotal_cents`, `needs_review`, `ready_to_close`. Subtotals can be `null` when claims need review. Call through the staff backend with `Authorization: Bearer <STAFF_API_TOKEN>`. |

For claims, copy the versions from the allocation state the guest acted on.
Use `allocation_id` for PUT and DELETE. Quantities are decimal strings such as
`"0.5"` for half of one unit. Money uses integer cents. Settlement advances the
current split version, so refresh allocations or balance after confirming it.
Keep the staff token on the server. Bill Service handles the actual close action.

## Minimal browser example

This uses a same-origin proxy. For a separate API origin, configure credentialed
CORS and verify the browser will send the cookies. Split Service currently uses
`SameSite=Lax` and does not configure CORS itself.

```js
const billUrl = '/api/bills/12';
let csrfToken;

async function split(path = '', method = 'GET', body) {
  const response = await fetch(billUrl + path, {
    method,
    credentials: 'include',
    headers: body === undefined ? {} : {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw Object.assign(new Error(data?.error ?? 'Split Service request failed'), {
      status: response.status,
    });
  }
  return data;
}

({ csrf_token: csrfToken } = await split());

const guest = await split('/participants/me').catch(error => {
  if (error.status !== 403) throw error;
  return null;
});

// If guest is null, show the name form and call this on submit.
const join = displayName => split('/participants', 'POST', { display_name: displayName });

// Use the allocation state the guest was shown when they chose the quantity.
async function addClaim(itemId, quantity, displayedState) {
  await split('/claims', 'POST', {
    item_id: itemId,
    quantity,
    bill_version: displayedState.bill_version,
    split_version: displayedState.split_version,
  });
  return Promise.all([split('/allocations'), split('/balance')]);
}
```

| If the API returns | What the UI should do |
| --- | --- |
| `400` | Show the validation message and let the guest correct the input. |
| `403` | Check whether the guest has joined and whether cookies went through. For a CSRF error, fetch the bill entry again and use its token. |
| `404` | Refresh the claim list. For allocations before joining, join first. |
| `409` | Show the API message. Refresh allocations for a claim conflict or balance for a settlement conflict, then let the guest confirm again. Avoid automatically repeating an additive claim. |
| `503` | Show that the service or bill is temporarily unavailable. Refresh state before resubmitting a write. |

Application errors generally include a human-readable `error` field. See the
[full API reference](split-service.md) and [Bill Service API](bill-service.md)
for additional response examples.
