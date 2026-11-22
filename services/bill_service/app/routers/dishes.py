from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..menu import rank_menu
from ..models import Dish, DishIngredient, Ingredient
from ..schemas import DishIn, DishOut, MenuDish, RecipeLine

router = APIRouter(tags=["dishes"])


def get_dish_or_404(db: Session, dish_id: int) -> Dish:
    dish = db.get(Dish, dish_id)
    if dish is None:
        raise HTTPException(404, "Dish not found")
    return dish


def commit_or_409(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A dish with this name already exists")


@router.get("/dishes", response_model=list[DishOut])
def list_dishes(db: Session = Depends(get_db)):
    return db.scalars(select(Dish).order_by(Dish.id)).all()


@router.post("/dishes", response_model=DishOut, status_code=201)
def create_dish(data: DishIn, db: Session = Depends(get_db)):
    dish = Dish(name=data.name, price_cents=data.price_cents)
    db.add(dish)
    commit_or_409(db)
    db.refresh(dish)
    return dish


@router.get("/dishes/{dish_id}", response_model=DishOut)
def get_dish(dish_id: int, db: Session = Depends(get_db)):
    return get_dish_or_404(db, dish_id)


@router.put("/dishes/{dish_id}", response_model=DishOut)
def update_dish(dish_id: int, data: DishIn, db: Session = Depends(get_db)):
    dish = get_dish_or_404(db, dish_id)
    dish.name = data.name
    dish.price_cents = data.price_cents
    commit_or_409(db)
    db.refresh(dish)
    return dish


@router.delete("/dishes/{dish_id}", status_code=204)
def delete_dish(dish_id: int, db: Session = Depends(get_db)):
    # Old bill items keep their copied name and price (dish_id becomes empty).
    db.delete(get_dish_or_404(db, dish_id))
    db.commit()


@router.put("/dishes/{dish_id}/ingredients", response_model=DishOut)
def set_recipe(dish_id: int, lines: list[RecipeLine], db: Session = Depends(get_db)):
    dish = get_dish_or_404(db, dish_id)
    ids = [line.ingredient_id for line in lines]
    if len(ids) != len(set(ids)):
        raise HTTPException(400, "Each ingredient can appear only once in a recipe")
    for ingredient_id in ids:
        if db.get(Ingredient, ingredient_id) is None:
            raise HTTPException(404, f"Ingredient {ingredient_id} not found")
    # Replace the whole recipe: remove old lines first, then add the new ones.
    dish.ingredients.clear()
    db.flush()
    for line in lines:
        dish.ingredients.append(DishIngredient(ingredient_id=line.ingredient_id, amount=line.amount))
    db.commit()
    db.refresh(dish)
    return dish


@router.get("/menu", response_model=list[MenuDish], tags=["menu"])
def guest_menu(db: Session = Depends(get_db)):
    """Dishes in stock, with surplus dishes first (the recommendation feature)."""
    return rank_menu(db.scalars(select(Dish)).all())
