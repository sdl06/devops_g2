"""Run before migrations: wait until the database answers, and (locally) create it.

- Waits up to ~90 s, because SQL Server in Docker and a paused Azure SQL database
  both take a while to accept connections.
- If CREATE_DATABASE=true (only set in docker-compose), creates the database when
  it does not exist yet. On Azure the database is created by the infrastructure setup.
"""

import os
import sys
import time

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

ATTEMPTS = 30
DELAY_SECONDS = 3


def main() -> None:
    url = make_url(os.environ["DATABASE_URL"])
    create = os.environ.get("CREATE_DATABASE", "false").lower() == "true"
    # CREATE DATABASE must run from the "master" database, outside a transaction.
    target = url.set(database="master") if create else url
    engine = create_engine(target, isolation_level="AUTOCOMMIT")

    for attempt in range(1, ATTEMPTS + 1):
        try:
            with engine.connect() as connection:
                if create:
                    name = url.database
                    connection.execute(
                        text(f"IF DB_ID(N'{name}') IS NULL CREATE DATABASE [{name}]")
                    )
            print("Database is ready", flush=True)
            return
        except OperationalError:
            print(f"Waiting for database ({attempt}/{ATTEMPTS})...", flush=True)
            time.sleep(DELAY_SECONDS)

    sys.exit("Database did not become available in time")


if __name__ == "__main__":
    main()
