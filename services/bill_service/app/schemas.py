from pydantic import BaseModel, ConfigDict, Field


# ---------- Tables ----------
class TableIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class TableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


# ---------- Bills ----------
class BillIn(BaseModel):
    table_id: int


class ItemIn(BaseModel):
    dish_id: int
    quantity: int = Field(gt=0)


class ItemUpdate(BaseModel):
    quantity: int = Field(gt=0)


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    dish_id: int | None
    name: str
    quantity: int
    price_cents: int
    total_cents: int


class BillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    table_id: int
    status: str
    version: int
    total_cents: int
    items: list[ItemOut]