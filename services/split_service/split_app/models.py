"""Data owned by Split Service; bill and item IDs belong to Bill Service."""

import uuid

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class SplitSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bill_id = models.CharField(max_length=100, unique=True)
    bill_version = models.CharField(max_length=100)
    split_version = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Split for bill {self.bill_id}"


class Participant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(SplitSession, on_delete=models.CASCADE, related_name="participants")
    display_name = models.CharField(max_length=100)
    resume_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.display_name


class Allocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="allocations")
    item_id = models.CharField(max_length=100)
    # One whole item is 1.000000; fractions permit shared items.
    quantity = models.DecimalField(max_digits=15, decimal_places=6, validators=[MinValueValidator(0.000001)])
    needs_review = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["participant", "item_id"], name="unique_participant_item"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="allocation_positive_quantity"),
        ]


class Tip(models.Model):
    class Kind(models.TextChoices):
        PERCENT = "percent", "Percent"
        FIXED = "fixed", "Fixed amount"

    participant = models.OneToOneField(Participant, on_delete=models.CASCADE, related_name="tip", primary_key=True)
    kind = models.CharField(max_length=7, choices=Kind.choices)
    # Percent uses basis points (10000 = 100%); fixed uses integer cents.
    value = models.PositiveIntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=Q(kind="fixed") | Q(kind="percent", value__lte=10000),
            name="tip_percent_at_most_100",
        )]


class Settlement(models.Model):
    participant = models.OneToOneField(Participant, on_delete=models.CASCADE, related_name="settlement", primary_key=True)
    amount_cents = models.PositiveBigIntegerField()
    bill_version = models.CharField(max_length=100)
    split_version = models.PositiveBigIntegerField()
    settled_at = models.DateTimeField(auto_now_add=True)
    needs_review = models.BooleanField(default=False)
