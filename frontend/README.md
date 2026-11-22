# Guest UI (Member 3)

React + Vite mobile-first guest checkout. Integrates with existing Bill Service and Split Service.

## Run
1. Start Bill Service at localhost:8000 and Split Service at localhost:8001 (with a shared working database/backend setup).
2. `cd services/guest_ui`
3. `npm install`
4. `npm run dev`
5. Open `http://localhost:8080/?bill_id=12` or `http://localhost:8080/?table_id=3` (replace with an existing open bill/table).

Vite proxies `/bills` and `/tables` to Bill Service and `/api` to Split Service, preserving same-origin cookies. For deployment, configure equivalent reverse-proxy routes.

## Guest demo
Join by name; claim a full or fractional item; update or release your claim; choose a tip; review the server-calculated balance; confirm simulated settlement. Open two browsers with separate cookie jars to demonstrate claim conflicts. A 409 refreshes the bill and requires user reconfirmation. Polls every 10 seconds.

## Notes
The repository snapshot has no frontend and its root Compose file does not start Split Service. Start the backends separately or extend Compose. The guest UI does not perform real payments. Do not expose staff tokens in the browser.
