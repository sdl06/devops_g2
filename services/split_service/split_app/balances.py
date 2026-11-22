"""Allocation totals and tip calculations in integer cents."""

from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from .models import Allocation, Participant, Tip, db


def _money(value):
    return int(Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _allocations(session_id):
    return (
        Allocation.query.join(Participant)
        .filter(Participant.session_id == session_id)
        .order_by(Allocation.updated_at, Allocation.id)
        .all()
    )


def _split_amounts(bill, allocations):
    """Floor each claim and assign any remainder on completion of the item."""
    by_item = {}
    for allocation in allocations:
        by_item.setdefault(allocation.item_id, []).append(allocation)
    subtotals = {}
    unallocated = 0
    fully_allocated = True
    for item in bill["items"]:
        claims = by_item.pop(str(item["id"]), [])
        price = int(item["price_cents"])
        quantity = Decimal(str(item["quantity"]))
        claimed = sum((a.quantity for a in claims), Decimal(0))
        if price < 0 or quantity <= 0 or claimed > quantity:
            raise ValueError("Bill item or allocation is invalid")
        amounts = [int((a.quantity * price).to_integral_value(rounding=ROUND_DOWN)) for a in claims]
        item_total = _money(price * quantity)
        if claims and claimed == quantity:
            amounts[-1] += item_total - sum(amounts)
        else:
            fully_allocated = False
        unallocated += item_total - sum(amounts)
        for allocation, amount in zip(claims, amounts):
            subtotals[allocation.participant_id] = (
                subtotals.get(allocation.participant_id, 0) + amount
            )
    if by_item:
        raise ValueError("A claimed item is missing from the bill")
    return subtotals, (unallocated, fully_allocated)


def _with_tip(subtotal, tip):
    tip_cents = (
        0
        if tip is None
        else (
            tip.value
            if tip.kind == Tip.Kind.FIXED
            else _money(Decimal(subtotal) * tip.value / 10000)
        )
    )
    return subtotal, tip_cents, subtotal + tip_cents


def _balance(participant, bill):
    allocations = _allocations(participant.session_id)
    if any(a.needs_review for a in allocations):
        raise ValueError("Allocations need review")
    subtotals, _ = _split_amounts(bill, allocations)
    return _with_tip(subtotals.get(participant.id, 0), db.session.get(Tip, participant.id))
