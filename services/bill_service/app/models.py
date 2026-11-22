from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class DiningTable(Base):
    # Called "dining_tables" because "Table" is a reserved name in SQLAlchemy.
    # The API still calls them /tables.
    __tablename__ = "dining_tables"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)


class Bill(Base):
    __tablename__ = "bills"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'open', 'closed')", name="ck_bill_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("dining_tables.id"))
    status: Mapped[str] = mapped_column(String(10), default="draft")
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    items: Mapped[list["BillItem"]] = relationship(
        back_populates="bill", cascade="all, delete-orphan"
    )

    @property
    def total_cents(self) -> int:
        return sum(item.total_cents for item in self.items)


class BillItem(Base):
    __tablename__ = "bill_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_item_quantity"),
        CheckConstraint("price_cents >= 0", name="ck_item_price"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    bill_id: Mapped[int] = mapped_column(ForeignKey("bills.id", ondelete="CASCADE"))
    # If a dish is deleted later, old bills keep the item (name and price are copied).
    dish_id: Mapped[int | None] = mapped_column(ForeignKey("dishes.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int]
    price_cents: Mapped[int]  # price of ONE unit

    bill: Mapped[Bill] = relationship(back_populates="items")

    @property
    def total_cents(self) -> int:
        return self.price_cents * self.quantity


class Dish(Base):
    __tablename__ = "dishes"
    __table_args__ = (CheckConstraint("price_cents >= 0", name="ck_dish_price"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    price_cents: Mapped[int]

    ingredients: Mapped[list["DishIngredient"]] = relationship(
        back_populates="dish", cascade="all, delete-orphan"
    )


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    unit: Mapped[str] = mapped_column(String(20))  # e.g. "g", "ml", "pcs"
    stock: Mapped[int] = mapped_column(default=0)
    surplus_level: Mapped[int] = mapped_column(default=0)


class DishIngredient(Base):
    """The recipe: how much of each ingredient one serving of a dish uses."""

    __tablename__ = "dish_ingredients"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_recipe_amount"),)

    dish_id: Mapped[int] = mapped_column(
        ForeignKey("dishes.id", ondelete="CASCADE"), primary_key=True
    )
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id"), primary_key=True
    )
    amount: Mapped[int]

    dish: Mapped[Dish] = relationship(back_populates="ingredients")
    ingredient: Mapped[Ingredient] = relationship()