#!/bin/sh
# Container startup: wait for the database, apply migrations, then start the API.
set -e
python wait_for_db.py
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log
