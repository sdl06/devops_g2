"""Split-owned records; bill and item IDs refer to Bill Service."""
import uuid
from datetime import UTC, datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
def new_id():
    return str(uuid.uuid4())
def now():
    return datetime.now(UTC)

class SplitSession(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=new_id)
    bill_id = db.Column(db.String(100), unique=True, nullable=False)
    bill_version = db.Column(db.String(100), nullable=False)
    split_version = db.Column(db.BigInteger, default=0, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=now, onupdate=now, nullable=False)
    participants = db.relationship('Participant', back_populates='session', cascade='all, delete-orphan')
    __table_args__ = (db.CheckConstraint('split_version >= 0'),)

class Participant(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=new_id)
    session_id = db.Column(db.String(36), db.ForeignKey('split_session.id'), nullable=False, index=True)
    display_name = db.Column(db.String(100), nullable=False)
    resume_token = db.Column(db.String(36), unique=True, nullable=False, default=new_id)
    joined_at = db.Column(db.DateTime(timezone=True), default=now, nullable=False)
    session = db.relationship('SplitSession', back_populates='participants')
    allocations = db.relationship('Allocation', back_populates='participant', cascade='all, delete-orphan')

class Allocation(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=new_id)
    participant_id = db.Column(db.String(36), db.ForeignKey('participant.id'), nullable=False, index=True)
    item_id = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Numeric(15, 6), nullable=False)
    needs_review = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=now, onupdate=now, nullable=False)
    participant = db.relationship('Participant', back_populates='allocations')
    __table_args__ = (db.UniqueConstraint('participant_id', 'item_id', name='unique_participant_item'), db.CheckConstraint('quantity > 0', name='allocation_positive_quantity'))

class Tip(db.Model):
    class Kind:
        FIXED = 'fixed'
        PERCENT = 'percent'
        values = ('fixed', 'percent')
    participant_id = db.Column(db.String(36), db.ForeignKey('participant.id'), primary_key=True)
    kind = db.Column(db.String(7), nullable=False)
    value = db.Column(db.Integer, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=now, onupdate=now, nullable=False)
    __table_args__ = (db.CheckConstraint("value >= 0 AND (kind = 'fixed' OR (kind = 'percent' AND value <= 10000))", name='valid_tip'),)

class Settlement(db.Model):
    participant_id = db.Column(db.String(36), db.ForeignKey('participant.id'), primary_key=True)
    amount_cents = db.Column(db.BigInteger, nullable=False)
    bill_version = db.Column(db.String(100), nullable=False)
    split_version = db.Column(db.BigInteger, nullable=False)
    settled_at = db.Column(db.DateTime(timezone=True), default=now, nullable=False)
    needs_review = db.Column(db.Boolean, default=False, nullable=False)
    __table_args__ = (db.CheckConstraint('amount_cents >= 0 AND split_version >= 0'),)
