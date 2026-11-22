FROM python:3.12-slim

# No .pyc files in the image; logs go straight to stdout.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install pinned dependencies first, so this layer is cached between builds.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only what the service needs to run (no tests, no .env, no .venv).
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini wait_for_db.py start.sh ./

# Run as a normal user, not root.
RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000
CMD ["sh", "start.sh"]
