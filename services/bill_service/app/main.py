import logging
import os
import sys
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .routers import bills, dishes, ingredients, tables

# Send logs to stdout at INFO level (the brief asks for this, Azure collects it)
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("bill_service")

app = FastAPI(title="Bill Service")

# Only the UI's own address may call this service from a browser.
# CORS_ORIGINS is a comma-separated list, e.g. "https://sdd-3a-g2-ui.azurestaticapps.net".
cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)


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


app.include_router(tables.router)
app.include_router(bills.router)
app.include_router(dishes.router)
app.include_router(ingredients.router)


# ---------- error format: always {"error": "message"} ----------
@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    first = exc.errors()[0]
    field = ".".join(str(part) for part in first["loc"] if part != "body")
    return JSONResponse({"error": f"{field}: {first['msg']}"}, status_code=400)


@app.exception_handler(OperationalError)
async def database_down(request: Request, exc: OperationalError):
    return JSONResponse({"error": "Database is unavailable. Try again shortly."}, status_code=503)