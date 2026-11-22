FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:////data/split.sqlite3

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY split_app ./split_app
COPY migrations ./migrations
COPY wsgi.py start.sh ./

RUN useradd --create-home --uid 1000 appuser \
    && install -d -o appuser -g appuser /data
USER appuser
EXPOSE 8001

CMD ["sh", "start.sh"]
