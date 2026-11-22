"""Blueprint and helpers shared by the Split Service routes."""

import uuid

from flask import Blueprint, jsonify, request
from sqlalchemy import update

from ..models import Participant, SplitSession, db

api = Blueprint("split", __name__)


def _error(message, status):
    return jsonify(error=message), status


def _body(request):
    value = request.get_json(silent=True)
    return value if isinstance(value, dict) else None


def _participant(request, session):
    token = request.cookies.get(f"split_resume_{session.id}")
    if not token:
        return None
    try:
        token = uuid.UUID(token)
    except (ValueError, TypeError, AttributeError):
        return None
    return Participant.query.filter_by(session_id=session.id, resume_token=str(token)).first()


def _guest(bill_id):
    split = SplitSession.query.filter_by(bill_id=bill_id).first()
    return split, _participant(request, split) if split else None


def _valid_version(data):
    version = data.get("split_version")
    return type(version) is int and 0 <= version < 2**63 - 1


def _matching_bill(bill, bill_id, data):
    return (
        str(bill.get("id")) == bill_id
        and bill.get("status") == "open"
        and str(bill["version"]) == str(data.get("bill_version"))
    )


def _advance_split(split, expected, **values):
    result = db.session.execute(
        update(SplitSession)
        .where(SplitSession.id == split.id, SplitSession.split_version == expected)
        .values(split_version=SplitSession.split_version + 1, **values)
    )
    return result.rowcount == 1


def _claim_error(message, status=409):
    db.session.rollback()
    return _error(message, status)


def _settlement_data(settlement):
    if settlement is None:
        return None
    return {
        "amount_cents": settlement.amount_cents,
        "bill_version": settlement.bill_version,
        "split_version": settlement.split_version,
        "needs_review": settlement.needs_review,
    }
