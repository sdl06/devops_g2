cd ~/devops_g2
git checkout main
git pull
git checkout -b docs/bill-service# AI usage

One row per significant piece of AI-assisted work.

| Date | Member | Work | Tool | How AI was used | What the member did / checked |
|---|---|---|---|---|---|
| 2026-11-20 | Nini | Bill Service API contract (`docs/api/bill-service.md`) | Claude | Drafted the endpoint list and response formats from our proposal and the Split Service code | Agreed field names, integer cents and the version rule with the Split Service owner; adjusted to match his code |
| 2026-11-20 | Nini | Bill Service skeleton (`/health`, request logging) | Claude | Generated and explained the FastAPI app and logging middleware | Set up the environment, ran it locally, checked the log line format |
| 2026-11-20 | Nini | Database models and first migration | Claude | Generated the SQLAlchemy models and explained the Alembic setup | Ran SQL Server in Docker, generated and applied the migration, verified the tables |
| 2026-11-21 | Nini | Endpoints: tables, bills, items, dishes, ingredients, `/menu` | Claude | Helped with writing the routers, schemas and the menu ranking rule | Tested every flow through `/docs` against the local database |
| 2026-11-22 | Nini | Bill Service tests (43 tests, 99% coverage) | Claude | Helped in writing the pytest suite and test fixtures | Ran the suite locally, reviewed what each test covers |
| 2026-11-22 | Nini | Dockerfile, startup script, CORS, compose entry | Claude | Wrote the Dockerfile, `start.sh`, `wait_for_db.py` and CORS config | Built and ran the container with `docker compose`, checked startup logs and `/health` |
| 2026-11-22 | Nini | Ruff lint/format fixes | Claude | Applied the team `ruff.toml` rules and the `DbSession` dependency style | Ran `ruff check`, `ruff format --check` and the tests |
| 2026-11-22 | Nini | Bill Service docs (`docs/data-model.md`, decision records) | Claude | Helped with drafting the diagram and decision records from the code | Checked the diagram against the migration, edited the wording |
