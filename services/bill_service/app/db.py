import os
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ["DATABASE_URL"]

# pool_pre_ping checks the connection before using it.
# Needed because Azure SQL pauses itself when idle.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    """Every table class inherits from this."""


def get_db():
    """Give each request its own database session, and close it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Use as a parameter type: `db: DbSession` gives the endpoint a database session.
DbSession = Annotated[Session, Depends(get_db)]
