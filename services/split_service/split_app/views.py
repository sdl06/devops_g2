"""Reviewed Flask views. All API paths omit trailing slashes."""
import json
import secrets
import uuid
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen
from flask import Blueprint, current_app, jsonify, request, session as browser_session
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from .models import db, Allocation, Participant, Settlement, SplitSession, Tip

api = Blueprint('split', __name__)

def _error(message, status):
    return jsonify(error=message), status


def _body(request):
    value = request.get_json(silent=True)
    return value if isinstance(value, dict) else None


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


def _participant(request, session):
    token = request.cookies.get(f"split_resume_{session.id}")
    if not token:
        return None
    try:
        token = uuid.UUID(token)
    except (ValueError, TypeError, AttributeError):
        return None
    return Participant.query.filter_by(session_id=session.id, resume_token=str(token)).first()


def _money(value):
    return int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _balance(participant, bill):
    """Floor fractional cents; give the remainder to the claim completing an item."""
    allocations = list(Allocation.query.join(Participant).filter(Participant.session_id == participant.session_id).order_by(Allocation.updated_at, Allocation.id).all())
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
    tip = db.session.get(Tip, participant.id)
    tip_cents = 0 if tip is None else (tip.value if tip.kind == Tip.Kind.FIXED else _money(Decimal(subtotal) * tip.value / 10000))
    return subtotal, tip_cents, subtotal + tip_cents



def _csrf_response(payload):
    token = browser_session.setdefault('csrf_token', secrets.token_urlsafe(32))
    response = jsonify(**payload, csrf_token=token)
    response.set_cookie('csrftoken', token, secure=current_app.config['SESSION_COOKIE_SECURE'], samesite='Lax')
    return response


@api.get('/bills/<bill_id>')
def bill_entry(bill_id):
    bill = _bill(bill_id)
    if bill is None:
        return _error('Bill Service is unavailable. Try again shortly.', 503)
    if str(bill.get('id')) != bill_id or bill.get('status') != 'open':
        return _error('This bill is not open.', 409)
    return _csrf_response({'bill_id': bill_id, 'bill_version': str(bill['version']), 'status': 'open'})


@api.post('/bills/<bill_id>/participants')
def join_session(bill_id):
    data = _body(request) or {}
    name = data.get('display_name')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        return _error('Enter a name of at most 100 characters.', 400)
    bill = _bill(bill_id)
    if bill is None:
        return _error('Bill Service is unavailable. Try again shortly.', 503)
    if str(bill.get('id')) != bill_id or bill.get('status') != 'open':
        return _error('This bill is not open.', 409)
    split = SplitSession.query.filter_by(bill_id=bill_id).first()
    if split is None:
        split = SplitSession(bill_id=bill_id, bill_version=str(bill['version']))
        db.session.add(split)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            split = SplitSession.query.filter_by(bill_id=bill_id).one()
    participant = _participant(request, split)
    if participant is None:
        participant = Participant(session=split, display_name=name.strip())
        db.session.add(participant)
        db.session.commit()
    response = jsonify(session_id=split.id, participant_id=participant.id, split_version=split.split_version)
    response.set_cookie(f'split_resume_{split.id}', participant.resume_token, httponly=True,
                        secure=current_app.config['SESSION_COOKIE_SECURE'], samesite='Lax')
    return response


@api.get('/bills/<bill_id>/allocations')
def allocation_state(bill_id):
    split = SplitSession.query.filter_by(bill_id=bill_id).first()
    if split is None:
        return _error('No split session for this bill.', 404)
    bill = _bill(bill_id)
    if bill is None:
        return _error('Bill Service is unavailable. Try again shortly.', 503)
    allocations = Allocation.query.join(Participant).filter(Participant.session_id == split.id).all()
    claimed = {}
    for allocation in allocations:
        claimed[allocation.item_id] = claimed.get(allocation.item_id, Decimal(0)) + allocation.quantity
    items = [{'item_id': str(item['id']), 'remaining': str(Decimal(str(item['quantity'])) - claimed.get(str(item['id']), Decimal(0)))} for item in bill['items']]
    claims = [{'item_id': a.item_id, 'participant_id': a.participant_id, 'quantity': str(a.quantity), 'needs_review': a.needs_review} for a in allocations]
    return jsonify(bill_version=str(bill['version']), split_version=split.split_version,
                   bill_changed=split.bill_version != str(bill['version']), items=items, claims=claims)


def _claim_error(message, status=409):
    db.session.rollback()
    return _error(message, status)


@api.post('/bills/<bill_id>/claims')
def claim_item(bill_id):
    data = _body(request)
    if data is None:
        return _error('Invalid JSON.', 400)
    split = SplitSession.query.filter_by(bill_id=bill_id).first()
    if split is None:
        return _error('No split session for this bill.', 404)
    participant = _participant(request, split)
    if participant is None:
        return _error('Join this bill first.', 403)
    try:
        quantity = Decimal(str(data['quantity']))
        expected = data['split_version']
        item_id = str(data['item_id'])
        if type(expected) is not int or expected < 0 or not quantity.is_finite() or quantity <= 0 or quantity.as_tuple().exponent < -6 or quantity >= 10**9:
            raise ValueError
    except (KeyError, ValueError, TypeError, InvalidOperation):
        return _error('Invalid claim.', 400)
    bill = _bill(bill_id)
    if bill is None:
        return _error('Bill Service is unavailable. Try again shortly.', 503)
    if str(bill.get('id')) != bill_id or bill.get('status') != 'open' or str(bill.get('version')) != str(data.get('bill_version')):
        return _error('Bill changed. Refresh and choose again.', 409)
    item = next((i for i in bill['items'] if str(i['id']) == item_id), None)
    if item is None:
        return _error('Item changed. Refresh and choose again.', 409)
    # This conditional UPDATE and allocation write share one transaction.
    advanced = db.session.execute(update(SplitSession).where(SplitSession.id == split.id, SplitSession.split_version == expected).values(split_version=SplitSession.split_version + 1, bill_version=str(bill['version'])))
    if advanced.rowcount != 1:
        return _claim_error('Someone changed the split. Refresh and choose again.')
    if db.session.get(Settlement, participant.id):
        return _claim_error('Reopen settlement before changing a claim.')
    claims = Allocation.query.join(Participant).filter(Participant.session_id == split.id, Allocation.item_id == item_id).all()
    if sum((a.quantity for a in claims), Decimal(0)) + quantity > Decimal(str(item['quantity'])):
        return _claim_error('This share is no longer available. Refresh and choose again.')
    latest = _bill(bill_id)
    if latest is None:
        return _claim_error('Bill Service is unavailable. Try again shortly.', 503)
    if str(latest.get('version')) != str(bill['version']) or latest.get('status') != 'open':
        return _claim_error('Bill changed. Refresh and choose again.')
    allocation = Allocation.query.filter_by(participant_id=participant.id, item_id=item_id).first()
    if allocation is None:
        allocation = Allocation(participant_id=participant.id, item_id=item_id, quantity=quantity)
        db.session.add(allocation)
    else:
        allocation.quantity += quantity
    db.session.commit()
    return jsonify(allocation_id=allocation.id, split_version=expected + 1), 201


@api.post('/bills/<bill_id>/tip')
def set_tip(bill_id):
    split = SplitSession.query.filter_by(bill_id=bill_id).first()
    participant = _participant(request, split) if split else None
    if participant is None:
        return _error('Join this bill first.', 403)
    data = _body(request) or {}
    kind, value = data.get('kind'), data.get('value')
    if kind not in Tip.Kind.values or type(value) is not int or value < 0 or value > 2147483647 or (kind == 'percent' and value > 10000):
        return _error('Invalid tip.', 400)
    if db.session.get(Settlement, participant.id):
        return _error('Reopen settlement before changing a tip.', 409)
    tip = db.session.get(Tip, participant.id)
    if tip is None:
        tip = Tip(participant_id=participant.id)
        db.session.add(tip)
    tip.kind, tip.value = kind, value
    db.session.commit()
    return jsonify(kind=kind, value=value)
