from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Bill, DiningTable
from ..schemas import BillOut, TableIn, TableOut

router = APIRouter(prefix="/tables", tags=["tables"])


def get_table_or_404(db: Session, table_id: int) -> DiningTable:
    table = db.get(DiningTable, table_id)
    if table is None:
        raise HTTPException(404, "Table not found")
    return table


@router.get("", response_model=list[TableOut])
def list_tables(db: Session = Depends(get_db)):
    return db.scalars(select(DiningTable).order_by(DiningTable.id)).all()


@router.post("", response_model=TableOut, status_code=201)
def create_table(data: TableIn, db: Session = Depends(get_db)):
    table = DiningTable(name=data.name)
    db.add(table)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A table with this name already exists")
    db.refresh(table)
    return table


@router.get("/{table_id}", response_model=TableOut)
def get_table(table_id: int, db: Session = Depends(get_db)):
    return get_table_or_404(db, table_id)


@router.put("/{table_id}", response_model=TableOut)
def update_table(table_id: int, data: TableIn, db: Session = Depends(get_db)):
    table = get_table_or_404(db, table_id)
    table.name = data.name
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A table with this name already exists")
    db.refresh(table)
    return table


@router.delete("/{table_id}", status_code=204)
def delete_table(table_id: int, db: Session = Depends(get_db)):
    table = get_table_or_404(db, table_id)
    has_bills = db.scalar(select(Bill.id).where(Bill.table_id == table_id).limit(1))
    if has_bills is not None:
        raise HTTPException(409, "This table has bills and cannot be deleted")
    db.delete(table)
    db.commit()


@router.get("/{table_id}/current-bill", response_model=BillOut)
def current_bill(table_id: int, db: Session = Depends(get_db)):
    get_table_or_404(db, table_id)
    bill = db.scalar(select(Bill).where(Bill.table_id == table_id, Bill.status == "open"))
    if bill is None:
        raise HTTPException(404, "This table has no open bill")
    return bill
