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
    allocations = _allocations(participant.session_id)
    if any(a.needs_review for a in allocations):
        raise ValueError('Allocations need review')
    subtotals, _ = _split_amounts(bill, allocations)
    return _with_tip(subtotals.get(participant.id, 0), db.session.get(Tip, participant.id))


def _allocations(session_id):
    return Allocation.query.join(Participant).filter(
        Participant.session_id == session_id
    ).order_by(Allocation.updated_at, Allocation.id).all()


def _split_amounts(bill, allocations):
    """Floor each claim and assign any remainder on completion of the item."""
    by_item = {}
    for allocation in allocations:
        by_item.setdefault(allocation.item_id, []).append(allocation)
    subtotals = {}
    unallocated = 0
    fully_allocated = True
    for item in bill['items']:
        claims = by_item.pop(str(item['id']), [])
        price = int(item['price_cents'])
        quantity = Decimal(str(item['quantity']))
        claimed = sum((a.quantity for a in claims), Decimal(0))
        if price < 0 or quantity <= 0 or claimed > quantity:
            raise ValueError('Bill item or allocation is invalid')
        amounts = [int((a.quantity * price).to_integral_value(rounding=ROUND_DOWN)) for a in claims]
        item_total = _money(price * quantity)
        if claims and claimed == quantity:
            amounts[-1] += item_total - sum(amounts)
        else:
            fully_allocated = False
        unallocated += item_total - sum(amounts)
        for allocation, amount in zip(claims, amounts):
            subtotals[allocation.participant_id] = subtotals.get(allocation.participant_id, 0) + amount
    if by_item:
        raise ValueError('A claimed item is missing from the bill')
    return subtotals, (unallocated, fully_allocated)


def _with_tip(subtotal, tip):
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
    claims = [{'allocation_id': a.id, 'item_id': a.item_id, 'participant_id': a.participant_id, 'quantity': str(a.quantity), 'needs_review': a.needs_review} for a in allocations]
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
        if not _valid_version(data) or not quantity.is_finite() or quantity <= 0 or quantity.as_tuple().exponent < -6 or quantity >= 10**9:
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
    db.session.execute(update(SplitSession).where(SplitSession.id == split.id).values(
        split_version=SplitSession.split_version
    ))
    if db.session.get(Settlement, participant.id):
        return _error('Reopen settlement before changing a tip.', 409)
    tip = db.session.get(Tip, participant.id)
    if tip is None:
        tip = Tip(participant_id=participant.id)
        db.session.add(tip)
    tip.kind, tip.value = kind, value
    db.session.commit()
    return jsonify(kind=kind, value=value)


def _guest(bill_id):
    split = SplitSession.query.filter_by(bill_id=bill_id).first()
    return split, _participant(request, split) if split else None


def _valid_version(data):
    version = data.get('split_version')
    return type(version) is int and 0 <= version < 2**63 - 1


def _matching_bill(bill, bill_id, data):
    return (str(bill.get('id')) == bill_id and bill.get('status') == 'open'
            and str(bill['version']) == str(data.get('bill_version')))


def _advance_split(split, expected, **values):
    result = db.session.execute(update(SplitSession).where(
        SplitSession.id == split.id, SplitSession.split_version == expected
    ).values(split_version=SplitSession.split_version + 1, **values))
    return result.rowcount == 1


def _settlement_data(settlement):
    if settlement is None:
        return None
    return dict(amount_cents=settlement.amount_cents, bill_version=settlement.bill_version,
                split_version=settlement.split_version, needs_review=settlement.needs_review)


@api.get('/bills/<bill_id>/participants/me')
def current_participant(bill_id):
    split, participant = _guest(bill_id)
    if participant is None:
        return _error('Join this bill first.', 403)
    tip = db.session.get(Tip, participant.id)
    result = jsonify(session_id=split.id, participant_id=participant.id,
                     display_name=participant.display_name,
                     tip=dict(kind=tip.kind, value=tip.value) if tip else None,
                     settlement=_settlement_data(db.session.get(Settlement, participant.id)))
    result.headers['Cache-Control'] = 'no-store'
    return result


@api.get('/bills/<bill_id>/balance')
def guest_balance(bill_id):
    split, participant = _guest(bill_id)
    if participant is None:
        return _error('Join this bill first.', 403)
    bill = _bill(bill_id)
    if bill is None:
        return _error('Bill Service is unavailable.', 503)
    try:
        subtotal, tip, total = _balance(participant, bill)
    except (KeyError, ValueError, InvalidOperation):
        return _error('Bill corrections need review.', 409)
    result = jsonify(subtotal_cents=subtotal, tip_cents=tip, total_cents=total,
                     bill_version=str(bill['version']), split_version=split.split_version)
    result.headers['Cache-Control'] = 'no-store'
    return result


@api.route('/bills/<bill_id>/claims/<allocation_id>', methods=['PUT', 'DELETE'])
def change_claim(bill_id, allocation_id):
    split, participant = _guest(bill_id)
    if participant is None:
        return _error('Join this bill first.', 403)
    data = _body(request) or {}
    if not _valid_version(data):
        return _error('Supply a valid split version.', 400)
    replacing = request.method == 'PUT'
    if replacing:
        try:
            quantity = Decimal(str(data['quantity']))
            if (not quantity.is_finite() or not 0 < quantity < 10**9
                    or quantity.as_tuple().exponent < -6):
                raise ValueError
        except (KeyError, ValueError, InvalidOperation):
            return _error('Invalid claim quantity.', 400)

    bill = _bill(bill_id)
    if bill is None:
        return _error('Bill Service is unavailable.', 503)
    if not _matching_bill(bill, bill_id, data):
        return _error('Bill changed. Refresh and choose again.', 409)
    version = data['split_version']
    owned_claim = Allocation.query.filter_by(id=allocation_id, participant_id=participant.id)
    if owned_claim.first() is None:
        return _error('Claim not found.', 404)
    if not _advance_split(split, version, bill_version=str(bill['version'])):
        return _claim_error('Split changed. Refresh and choose again.')
    allocation = owned_claim.first()
    if allocation is None:
        return _claim_error('Claim not found.', 404)
    if db.session.get(Settlement, participant.id):
        return _claim_error('Reopen settlement before changing a claim.')

    latest = _bill(bill_id)
    if latest is None:
        return _claim_error('Bill Service is unavailable.', 503)
    if not _matching_bill(latest, bill_id, data):
        return _claim_error('Bill changed. Refresh and choose again.')
    if replacing:
        item = next((item for item in latest['items'] if str(item['id']) == allocation.item_id), None)
        if item is None:
            return _claim_error('This item was removed. Delete the claim to release it.')
        others = sum((a.quantity for a in _allocations(split.id)
                      if a.item_id == allocation.item_id and a.id != allocation.id), Decimal(0))
        if others + quantity > Decimal(str(item['quantity'])):
            return _claim_error('This share is no longer available.')
        allocation.quantity = quantity
    else:
        db.session.delete(allocation)
    db.session.commit()
    return jsonify(allocation_id=allocation_id, split_version=version + 1, deleted=not replacing)


@api.post('/bills/<bill_id>/settlement')
def confirm_settlement(bill_id):
    split, participant = _guest(bill_id)
    if participant is None:
        return _error('Join this bill first.', 403)
    data = _body(request) or {}
    amount = data.get('amount_cents')
    if not _valid_version(data) or type(amount) is not int or amount < 0:
        return _error('Supply a valid split version and amount in cents.', 400)
    bill = _bill(bill_id)
    if bill is None:
        return _error('Bill Service is unavailable.', 503)
    if not _matching_bill(bill, bill_id, data):
        return _error('Bill changed. Refresh your balance.', 409)

    version = data['split_version']
    advanced = _advance_split(split, version)
    existing = db.session.get(Settlement, participant.id)
    if not advanced or existing:
        result = _settlement_data(existing)
        if (result and not result['needs_review'] and result['amount_cents'] == amount
                and result['bill_version'] == str(bill['version'])
                and result['split_version'] == version):
            try:
                _, _, current_total = _balance(participant, bill)
            except (KeyError, ValueError, InvalidOperation):
                return _claim_error('Bill corrections need review.')
            if current_total == amount:
                db.session.rollback()
                return jsonify(settlement='simulated', **result)
        return _claim_error('Split changed or settlement already exists. Refresh your balance.')

    latest = _bill(bill_id)
    if latest is None:
        return _claim_error('Bill Service is unavailable.', 503)
    if not _matching_bill(latest, bill_id, data):
        return _claim_error('Bill changed. Refresh your balance.')
    try:
        _, _, total = _balance(participant, latest)
    except (KeyError, ValueError, InvalidOperation):
        return _claim_error('Bill corrections need review.')
    if total != amount:
        return _claim_error('Amount changed. Refresh your balance.')
    settlement = Settlement(participant_id=participant.id, amount_cents=total,
                            bill_version=str(latest['version']), split_version=version)
    db.session.add(settlement)
    db.session.commit()
    return jsonify(settlement='simulated', **_settlement_data(settlement)), 201


@api.get('/bills/<bill_id>/progress')
def staff_progress(bill_id):
    expected = current_app.config['STAFF_API_TOKEN']
    if not expected:
        return _error('Staff access is not configured.', 503)
    supplied = request.headers.get('Authorization', '')
    if not secrets.compare_digest(supplied.encode(), f'Bearer {expected}'.encode()):
        return _error('Staff credentials required.', 401)
    bill = _bill(bill_id)
    if bill is None:
        return _error('Bill Service is unavailable.', 503)
    split = SplitSession.query.filter_by(bill_id=bill_id).first()
    allocations = _allocations(split.id) if split else []
    try:
        subtotals, (unallocated, fully_allocated) = _split_amounts(bill, allocations)
    except (KeyError, ValueError, InvalidOperation):
        return jsonify(ready_to_close=False, needs_review=True,
                       unallocated_subtotal_cents=None, allocated_unsettled_subtotal_cents=None)
    needs_review = any(a.needs_review for a in allocations)
    unsettled_subtotal = 0
    all_settled = True
    for participant in split.participants if split else []:
        subtotal = subtotals.get(participant.id, 0)
        _, _, total = _with_tip(subtotal, db.session.get(Tip, participant.id))
        settlement = db.session.get(Settlement, participant.id)
        valid = (settlement is not None and not settlement.needs_review
                 and settlement.bill_version == str(bill['version'])
                 and settlement.amount_cents == total)
        if settlement and not valid:
            needs_review = True
        if not valid:
            unsettled_subtotal += subtotal
            if participant.id in subtotals or total != 0:
                all_settled = False
    return jsonify(unallocated_subtotal_cents=unallocated,
                   allocated_unsettled_subtotal_cents=unsettled_subtotal,
                   needs_review=needs_review, ready_to_close=bool(
                       split and bill['status'] == 'open' and fully_allocated
                       and all_settled and not needs_review))
