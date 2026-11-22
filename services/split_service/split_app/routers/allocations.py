"""Allocation state and claim changes."""

from decimal import Decimal, InvalidOperation

from flask import jsonify, request
from sqlalchemy import update

from .. import bill_service
from ..balances import _allocations
from ..models import Allocation, Participant, Settlement, SplitSession, db
from .common import (
    _advance_split,
    _body,
    _claim_error,
    _error,
    _guest,
    _matching_bill,
    _participant,
    _valid_version,
    api,
)


@api.get('/bills/<bill_id>/allocations')
def allocation_state(bill_id):
    split = SplitSession.query.filter_by(bill_id=bill_id).first()
    if split is None:
        return _error('No split session for this bill.', 404)
    bill = bill_service._bill(bill_id)
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
    bill = bill_service._bill(bill_id)
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
    latest = bill_service._bill(bill_id)
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

    bill = bill_service._bill(bill_id)
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

    latest = bill_service._bill(bill_id)
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
