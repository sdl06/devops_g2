import logging
import sys
import time

from fastapi import FastAPI, Request

# Send logs to stdout at INFO level (the brief asks for this, Azure collects it)
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("bill_service")

app = FastAPI(title="Bill Service")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Write one log line per request: method, path, status, duration."""
    start = time.perf_counter()
    status = 500  # used if the request crashes before a response exists
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "method=%s path=%s status=%s duration_ms=%.1f",
            request.method, request.url.path, status, duration_ms,
        )


@app.get("/health")
def health():
    return {"status": "ok"}