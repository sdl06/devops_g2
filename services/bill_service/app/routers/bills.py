from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Bill, BillItem, DiningTable, Dish
from ..schemas import BillIn, BillOut, ItemIn, ItemOut, ItemUpdate

router = APIRouter(prefix="/bills", tags=["bills"])


# ---------- helpers ----------
def get_bill_or_404(db: Session, bill_id: int) -> Bill:
    bill = db.get(Bill, bill_id)
    if bill is None:
        raise HTTPException(404, "Bill not found")
    return bill


def require_not_closed(bill: Bill) -> None:
    if bill.status == "closed":
        raise HTTPException(409, "This bill is closed and cannot be changed")


def require_table(db: Session, table_id: int) -> None:
    if db.get(DiningTable, table_id) is None:
        raise HTTPException(404, "Table not found")


def save(db: Session, bill: Bill) -> Bill:
    """Every change to a bill or its items goes through here, so version always goes up."""
    bill.version += 1
    db.commit()
    db.refresh(bill)
    return bill


# ---------- bills ----------
@router.get("", response_model=list[BillOut])
def list_bills(status: str | None = None, table_id: int | None = None,
               db: Session = Depends(get_db)):
    query = select(Bill).order_by(Bill.id)
    if status:
        query = query.where(Bill.status == status)
    if table_id:
        query = query.where(Bill.table_id == table_id)
    return db.scalars(query).all()


@router.post("", response_model=BillOut, status_code=201)
def create_bill(data: BillIn, db: Session = Depends(get_db)):
    require_table(db, data.table_id)
    bill = Bill(table_id=data.table_id, status="draft", version=1)
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return bill


@router.get("/{bill_id}", response_model=BillOut)
def get_bill(bill_id: int, db: Session = Depends(get_db)):
    return get_bill_or_404(db, bill_id)


@router.put("/{bill_id}", response_model=BillOut)
def update_bill(bill_id: int, data: BillIn, db: Session = Depends(get_db)):
    bill = get_bill_or_404(db, bill_id)
    require_not_closed(bill)
    require_table(db, data.table_id)
    bill.table_id = data.table_id
    return save(db, bill)


@router.delete("/{bill_id}", status_code=204)
def delete_bill(bill_id: int, db: Session = Depends(get_db)):
    bill = get_bill_or_404(db, bill_id)
    if bill.status != "draft":
        raise HTTPException(409, "Only draft bills can be deleted")
    db.delete(bill)
    db.commit()


@router.post("/{bill_id}/open", response_model=BillOut)
def open_bill(bill_id: int, db: Session = Depends(get_db)):
    bill = get_bill_or_404(db, bill_id)
    if bill.status != "draft":
        raise HTTPException(409, "Only draft bills can be opened")
    if not bill.items:
        raise HTTPException(409, "Add at least one item before opening the bill")
    already_open = db.scalar(
        select(Bill.id).where(Bill.table_id == bill.table_id, Bill.status == "open")
    )
    if already_open is not None:
        raise HTTPException(409, "This table already has an open bill")
    bill.status = "open"
    return save(db, bill)


@router.post("/{bill_id}/close", response_model=BillOut)
def close_bill(bill_id: int, db: Session = Depends(get_db)):
    bill = get_bill_or_404(db, bill_id)
    if bill.status != "open":
        raise HTTPException(409, "Only open bills can be closed")
    bill.status = "closed"
    return save(db, bill)


# ---------- bill items ----------
def get_item_or_404(db: Session, bill_id: int, item_id: int) -> BillItem:
    item = db.scalar(select(BillItem).where(BillItem.id == item_id, BillItem.bill_id == bill_id))
    if item is None:
        raise HTTPException(404, "Item not found on this bill")
    return item


@router.post("/{bill_id}/items", response_model=ItemOut, status_code=201)
def add_item(bill_id: int, data: ItemIn, db: Session = Depends(get_db)):
    bill = get_bill_or_404(db, bill_id)
    require_not_closed(bill)
    dish = db.get(Dish, data.dish_id)
    if dish is None:
        raise HTTPException(404, "Dish not found")
    # Copy name and price, so later menu changes don't change this bill.
    item = BillItem(bill_id=bill.id, dish_id=dish.id, name=dish.name,
                    quantity=data.quantity, price_cents=dish.price_cents)
    db.add(item)
    save(db, bill)
    db.refresh(item)
    return item


@router.put("/{bill_id}/items/{item_id}", response_model=ItemOut)
def update_item(bill_id: int, item_id: int, data: ItemUpdate, db: Session = Depends(get_db)):
    bill = get_bill_or_404(db, bill_id)
    require_not_closed(bill)
    item = get_item_or_404(db, bill_id, item_id)
    item.quantity = data.quantity
    save(db, bill)
    db.refresh(item)
    return item


@router.delete("/{bill_id}/items/{item_id}", status_code=204)
def delete_item(bill_id: int, item_id: int, db: Session = Depends(get_db)):
    bill = get_bill_or_404(db, bill_id)
    require_not_closed(bill)
    item = get_item_or_404(db, bill_id, item_id)
    db.delete(item)
    save(db, bill)
