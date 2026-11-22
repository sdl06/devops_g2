"""HTTP client for Bill Service."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen

from flask import current_app


def _bill(bill_id):
    """Return None on upstream failure; never accept a claim from stale cached data."""
    base = current_app.config["BILL_SERVICE_URL"].rstrip("/")
    if not base:
        return None
    try:
        with urlopen(f"{base}/bills/{quote(str(bill_id), safe='')}", timeout=3) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError):
        return None
