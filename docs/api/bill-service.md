# Bill Service API

Draft — may still change. Owner: Nini.

- Money is always **integer cents** (€12.50 = `1250`).
- All requests and responses are JSON.
- Errors return `{"error": "message"}`.
- Paths have **no trailing slash**.

## Health

| Method | Path      | Result                 |
| ------ | --------- | ---------------------- |
| GET    | `/health` | `200 {"status": "ok"}` |

## Tables

| Method | Path                        | Body                  | Result                                                                  |
| ------ | --------------------------- | --------------------- | ----------------------------------------------------------------------- |
| GET    | `/tables`                   |                       | list of tables                                                          |
| POST   | `/tables`                   | `{"name": "Table 4"}` | `201` table                                                             |
| GET    | `/tables/{id}`              |                       | table                                                                   |
| PUT    | `/tables/{id}`              | `{"name": "Table 5"}` | table                                                                   |
| DELETE | `/tables/{id}`              |                       | `204` (`409` if it has any bills)                                    |
| GET    | `/tables/{id}/current-bill` |                       | the open bill for that table (`404` if none). Used by the QR guest page |

Example: `{"id": 1, "name": "Table 4"}`

## Bills

| Method | Path                            | Body              | Result                               |
| ------ | ------------------------------- | ----------------- | ------------------------------------ |
| GET    | `/bills?status=open&table_id=1` |                   | filtered list                        |
| POST   | `/bills`                        | `{"table_id": 1}` | `201`, starts as `draft`, version 1  |
| GET    | `/bills/{id}`                   |                   | bill with its items                  |
| PUT    | `/bills/{id}`                   | `{"table_id": 2}` | bill                                 |
| DELETE | `/bills/{id}`                   |                   | `204` (only drafts, otherwise `409`) |
| POST   | `/bills/{id}/open`              |                   | `draft` → `open` (guests can join)   |
| POST   | `/bills/{id}/close`             |                   | `open` → `closed` (no more changes)  |

Example:

    {
      "id": 12,
      "table_id": 1,
      "status": "open",
      "version": 3,
      "total_cents": 4250,
      "items": [
        {"id": 31, "dish_id": 5, "name": "Chicken curry",
         "quantity": 2, "price_cents": 1250, "total_cents": 2500}
      ]
    }

- `price_cents` is the price of **one** unit; `total_cents` = `price_cents × quantity`.
- Every change to a bill or its items adds 1 to `version`.
- Changing a closed bill returns `409`.

## Bill items

| Method | Path                          | Body                            | Result                                           |
| ------ | ----------------------------- | ------------------------------- | ------------------------------------------------ |
| POST   | `/bills/{id}/items`           | `{"dish_id": 5, "quantity": 2}` | `201` item (name and price copied from the dish) |
| PUT    | `/bills/{id}/items/{item_id}` | `{"quantity": 3}`               | item                                             |
| DELETE | `/bills/{id}/items/{item_id}` |                                 | `204`                                            |

## Dishes (menu)

| Method | Path                       | Body                                             | Result          |
| ------ | -------------------------- | ------------------------------------------------ | --------------- |
| GET    | `/dishes`                  |                                                  | list of dishes  |
| POST   | `/dishes`                  | `{"name": "Chicken curry", "price_cents": 1250}` | `201` dish      |
| GET    | `/dishes/{id}`             |                                                  | dish            |
| PUT    | `/dishes/{id}`             | same as POST                                     | dish            |
| DELETE | `/dishes/{id}`             |                                                  | `204`           |
| PUT    | `/dishes/{id}/ingredients` | `[{"ingredient_id": 2, "amount": 200}]`          | sets the recipe |

Example: `{"id": 5, "name": "Chicken curry", "price_cents": 1250, "ingredients": [{"ingredient_id": 2, "amount": 200}]}`

## Ingredients (stock)

| Method | Path                | Body                                                                     | Result                                |
| ------ | ------------------- | ------------------------------------------------------------------------ | ------------------------------------- |
| GET    | `/ingredients`      |                                                                          | list of ingredients                   |
| POST   | `/ingredients`      | `{"name": "Chicken", "unit": "g", "stock": 5000, "surplus_level": 3000}` | `201` ingredient                      |
| GET    | `/ingredients/{id}` |                                                                          | ingredient                            |
| PUT    | `/ingredients/{id}` | same as POST                                                             | ingredient                            |
| DELETE | `/ingredients/{id}` |                                                                          | `204` (`409` if a dish still uses it) |

## Guest menu (recommendation feature)

| Method | Path    | Result                                                                                                     |
| ------ | ------- | ---------------------------------------------------------------------------------------------------------- |
| GET    | `/menu` | dishes with enough stock for at least one serving, surplus dishes first, each with `"surplus": true/false` |

A dish is **surplus** when one of its ingredients has `stock` above its `surplus_level`.

## Error codes

| Code | Meaning                                             |
| ---- | --------------------------------------------------- |
| 400  | bad input                                           |
| 404  | not found                                           |
| 409  | not allowed right now (e.g. changing a closed bill) |
| 503  | the service can't reach its database                |
