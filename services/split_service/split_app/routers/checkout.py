"""Tips, balances, simulated settlement, and staff progress."""

import secrets
from decimal import InvalidOperation

from flask import current_app, jsonify, request
from sqlalchemy import update

from .. import bill_service
from ..balances import _allocations, _balance, _split_amounts, _with_tip
from ..models import Settlement, SplitSession, Tip, db
from .common import (
    _advance_split,
    _body,
    _claim_error,
    _error,
    _guest,
    _matching_bill,
    _participant,
    _settlement_data,
    _valid_version,
    api,
)


@api.post("/bills/<bill_id>/tip")
def set_tip(bill_id):
    split = SplitSession.query.filter_by(bill_id=bill_id).first()
    participant = _participant(request, split) if split else None
    if participant is None:
        return _error("Join this bill first.", 403)
    data = _body(request) or {}
    kind, value = data.get("kind"), data.get("value")
    if (
        kind not in Tip.Kind.values
        or type(value) is not int
        or value < 0
        or value > 2147483647
        or (kind == "percent" and value > 10000)
    ):
        return _error("Invalid tip.", 400)
    db.session.execute(
        update(SplitSession)
        .where(SplitSession.id == split.id)
        .values(split_version=SplitSession.split_version)
    )
    if db.session.get(Settlement, participant.id):
        return _error("Reopen settlement before changing a tip.", 409)
    tip = db.session.get(Tip, participant.id)
    if tip is None:
        tip = Tip(participant_id=participant.id)
        db.session.add(tip)
    tip.kind, tip.value = kind, value
    db.session.commit()
    return jsonify(kind=kind, value=value)


@api.get("/bills/<bill_id>/balance")
def guest_balance(bill_id):
    split, participant = _guest(bill_id)
    if participant is None:
        return _error("Join this bill first.", 403)
    bill = bill_service._bill(bill_id)
    if bill is None:
        return _error("Bill Service is unavailable.", 503)
    try:
        subtotal, tip, total = _balance(participant, bill)
    except (KeyError, ValueError, InvalidOperation):
        return _error("Bill corrections need review.", 409)
    result = jsonify(
        subtotal_cents=subtotal,
        tip_cents=tip,
        total_cents=total,
        bill_version=str(bill["version"]),
        split_version=split.split_version,
    )
    result.headers["Cache-Control"] = "no-store"
    return result


@api.post("/bills/<bill_id>/settlement")
def confirm_settlement(bill_id):
    split, participant = _guest(bill_id)
    if participant is None:
        return _error("Join this bill first.", 403)
    data = _body(request) or {}
    amount = data.get("amount_cents")
    if not _valid_version(data) or type(amount) is not int or amount < 0:
        return _error("Supply a valid split version and amount in cents.", 400)
    bill = bill_service._bill(bill_id)
    if bill is None:
        return _error("Bill Service is unavailable.", 503)
    if not _matching_bill(bill, bill_id, data):
        return _error("Bill changed. Refresh your balance.", 409)

    version = data["split_version"]
    advanced = _advance_split(split, version)
    existing = db.session.get(Settlement, participant.id)
    if not advanced or existing:
        result = _settlement_data(existing)
        if (
            result
            and not result["needs_review"]
            and result["amount_cents"] == amount
            and result["bill_version"] == str(bill["version"])
            and result["split_version"] == version
        ):
            try:
                _, _, current_total = _balance(participant, bill)
            except (KeyError, ValueError, InvalidOperation):
                return _claim_error("Bill corrections need review.")
            if current_total == amount:
                db.session.rollback()
                return jsonify(settlement="simulated", **result)
        return _claim_error("Split changed or settlement already exists. Refresh your balance.")

    latest = bill_service._bill(bill_id)
    if latest is None:
        return _claim_error("Bill Service is unavailable.", 503)
    if not _matching_bill(latest, bill_id, data):
        return _claim_error("Bill changed. Refresh your balance.")
    try:
        _, _, total = _balance(participant, latest)
    except (KeyError, ValueError, InvalidOperation):
        return _claim_error("Bill corrections need review.")
    if total != amount:
        return _claim_error("Amount changed. Refresh your balance.")
    settlement = Settlement(
        participant_id=participant.id,
        amount_cents=total,
        bill_version=str(latest["version"]),
        split_version=version,
    )
    db.session.add(settlement)
    db.session.commit()
    return jsonify(settlement="simulated", **_settlement_data(settlement)), 201


@api.get("/bills/<bill_id>/progress")
def staff_progress(bill_id):
    expected = current_app.config["STAFF_API_TOKEN"]
    if not expected:
        return _error("Staff access is not configured.", 503)
    supplied = request.headers.get("Authorization", "")
    if not secrets.compare_digest(supplied.encode(), f"Bearer {expected}".encode()):
        return _error("Staff credentials required.", 401)
    bill = bill_service._bill(bill_id)
    if bill is None:
        return _error("Bill Service is unavailable.", 503)
    split = SplitSession.query.filter_by(bill_id=bill_id).first()
    allocations = _allocations(split.id) if split else []
    try:
        subtotals, (unallocated, fully_allocated) = _split_amounts(bill, allocations)
    except (KeyError, ValueError, InvalidOperation):
        return jsonify(
            ready_to_close=False,
            needs_review=True,
            unallocated_subtotal_cents=None,
            allocated_unsettled_subtotal_cents=None,
        )
    needs_review = any(a.needs_review for a in allocations)
    unsettled_subtotal = 0
    all_settled = True
    for participant in split.participants if split else []:
        subtotal = subtotals.get(participant.id, 0)
        _, _, total = _with_tip(subtotal, db.session.get(Tip, participant.id))
        settlement = db.session.get(Settlement, participant.id)
        valid = (
            settlement is not None
            and not settlement.needs_review
            and settlement.bill_version == str(bill["version"])
            and settlement.amount_cents == total
        )
        if settlement and not valid:
            needs_review = True
        if not valid:
            unsettled_subtotal += subtotal
            if participant.id in subtotals or total != 0:
                all_settled = False
    return jsonify(
        unallocated_subtotal_cents=unallocated,
        allocated_unsettled_subtotal_cents=unsettled_subtotal,
        needs_review=needs_review,
        ready_to_close=bool(
            split
            and bill["status"] == "open"
            and fully_allocated
            and all_settled
            and not needs_review
        ),
    )
