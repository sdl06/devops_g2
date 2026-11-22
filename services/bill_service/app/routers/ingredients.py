from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import DbSession
from ..models import DishIngredient, Ingredient
from ..schemas import IngredientIn, IngredientOut

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


def get_ingredient_or_404(db: Session, ingredient_id: int) -> Ingredient:
    ingredient = db.get(Ingredient, ingredient_id)
    if ingredient is None:
        raise HTTPException(404, "Ingredient not found")
    return ingredient


def commit_or_409(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An ingredient with this name already exists")


@router.get("", response_model=list[IngredientOut])
def list_ingredients(db: DbSession):
    return db.scalars(select(Ingredient).order_by(Ingredient.id)).all()


@router.post("", response_model=IngredientOut, status_code=201)
def create_ingredient(data: IngredientIn, db: DbSession):
    ingredient = Ingredient(**data.model_dump())
    db.add(ingredient)
    commit_or_409(db)
    db.refresh(ingredient)
    return ingredient


@router.get("/{ingredient_id}", response_model=IngredientOut)
def get_ingredient(ingredient_id: int, db: DbSession):
    return get_ingredient_or_404(db, ingredient_id)


@router.put("/{ingredient_id}", response_model=IngredientOut)
def update_ingredient(ingredient_id: int, data: IngredientIn, db: DbSession):
    ingredient = get_ingredient_or_404(db, ingredient_id)
    for field, value in data.model_dump().items():
        setattr(ingredient, field, value)
    commit_or_409(db)
    db.refresh(ingredient)
    return ingredient


@router.delete("/{ingredient_id}", status_code=204)
def delete_ingredient(ingredient_id: int, db: DbSession):
    ingredient = get_ingredient_or_404(db, ingredient_id)
    used = db.scalar(
        select(DishIngredient.dish_id).where(DishIngredient.ingredient_id == ingredient_id).limit(1)
    )
    if used is not None:
        raise HTTPException(409, "This ingredient is used in a dish recipe")
    db.delete(ingredient)
    db.commit()
