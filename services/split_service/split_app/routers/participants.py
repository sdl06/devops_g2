"""Bill entry, guest joining, and session restoration."""

import secrets

from flask import current_app, jsonify, request, session as browser_session
from sqlalchemy.exc import IntegrityError

from .. import bill_service
from ..models import Participant, Settlement, SplitSession, Tip, db
from .common import _body, _error, _guest, _participant, _settlement_data, api


def _csrf_response(payload):
    token = browser_session.setdefault('csrf_token', secrets.token_urlsafe(32))
    response = jsonify(**payload, csrf_token=token)
    response.set_cookie('csrftoken', token, secure=current_app.config['SESSION_COOKIE_SECURE'], samesite='Lax')
    return response


@api.get('/bills/<bill_id>')
def bill_entry(bill_id):
    bill = bill_service._bill(bill_id)
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
    bill = bill_service._bill(bill_id)
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
