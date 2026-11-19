from django.shortcuts import render

# Create your views here.
"""Staged Split Service views. Move reviewed functions into views.py one at a time.

Expected Bill Service response: {"id", "version", "status", "items":
[{"id", "quantity", "price_cents"}]}. Agree this contract with its owner.
Reviewed endpoint functions are routed through split_app.urls.
"""

import json
import uuid
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen

from django.conf import settings
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import F, Sum
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import Allocation, Participant, Settlement, SplitSession, Tip


def _error(message, status):
    return JsonResponse({"error": message}, status=status)


def _body(request):
    try:
        value = json.loads(request.body)
        return value if isinstance(value, dict) else None
    except (ValueError, UnicodeDecodeError):
        return None


def _bill(bill_id):
    """Return None on upstream failure; never accept a claim from stale cached data."""
    base = getattr(settings, "BILL_SERVICE_URL", "").rstrip("/")
    if not base:
        return None
    try:
        with urlopen(f"{base}/bills/{quote(str(bill_id), safe='')}/", timeout=3) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError):
        return None


def _participant(request, session):
    token = request.COOKIES.get(f"split_resume_{session.id}")
    if not token:
        return None
    try:
        token = uuid.UUID(token)
    except (ValueError, TypeError, AttributeError):
        return None
    return Participant.objects.filter(session=session, resume_token=token).first()


def _money(value):
    return int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _balance(participant, bill):
    """Floor fractional cents; give the remainder to the claim completing an item."""
    allocations = list(Allocation.objects.filter(participant__session=participant.session).order_by("updated_at", "id"))
    by_item = {}
    for allocation in allocations:
        by_item.setdefault(allocation.item_id, []).append(allocation)
    subtotal = 0
    for item in bill["items"]:
        claims = by_item.pop(str(item["id"]), [])
        price = int(item["price_cents"])
        quantity = Decimal(str(item["quantity"]))
        if price < 0 or quantity <= 0 or sum((a.quantity for a in claims), Decimal(0)) > quantity:
            raise ValueError("Bill item or allocation is invalid")
        amounts = {a.id: int((a.quantity * price).to_integral_value(rounding=ROUND_DOWN)) for a in claims}
        if claims and sum((a.quantity for a in claims), Decimal(0)) == quantity:
            amounts[claims[-1].id] += _money(price * quantity) - sum(amounts.values())
        subtotal += sum(amounts[a.id] for a in claims if a.participant_id == participant.id)
    if by_item:
        raise ValueError("A claimed item is missing from the bill")
    subtotal = int(subtotal)
    tip = Tip.objects.filter(participant=participant).first()
    tip_cents = 0 if tip is None else (tip.value if tip.kind == Tip.Kind.FIXED else _money(Decimal(subtotal) * tip.value / 10000))
    return subtotal, tip_cents, subtotal + tip_cents


@ensure_csrf_cookie
@require_GET
def bill_entry(request, bill_id):
    """Call on QR entry before join POST; gives the browser a CSRF cookie."""
    bill = _bill(bill_id)
    if bill is None:
        return _error("Bill Service is unavailable. Try again shortly.", 503)
    if str(bill.get("id")) != str(bill_id) or bill.get("status") != "open":
        return _error("This bill is not open.", 409)
    return JsonResponse({"bill_id": str(bill_id), "bill_version": str(bill["version"]), "status": "open"})


@require_POST
def join_session(request, bill_id):
    """POST {"display_name": "Ana"}; sets a private resume cookie."""
    data = _body(request)
    name = data.get("display_name", "").strip() if data else ""
    if not name or len(name) > 100:
        return _error("Enter a name of at most 100 characters.", 400)
    bill = _bill(bill_id)
    if bill is None:
        return _error("Bill Service is unavailable. Try again shortly.", 503)
    if str(bill.get("id")) != str(bill_id) or bill.get("status") != "open":
        return _error("This bill is not open.", 409)
    session, _ = SplitSession.objects.get_or_create(bill_id=str(bill_id), defaults={"bill_version": str(bill["version"])})
    participant = _participant(request, session)
    if participant is None:
        participant = Participant.objects.create(session=session, display_name=name)
    response = JsonResponse({"session_id": str(session.id), "participant_id": str(participant.id), "split_version": session.split_version})
    response.set_cookie(f"split_resume_{session.id}", str(participant.resume_token), httponly=True, secure=request.is_secure(), samesite="Lax")
    return response



