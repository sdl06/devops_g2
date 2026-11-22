"""The recommendation rule, kept apart from the API so it is easy to test."""

from .models import Dish


def is_available(dish: Dish) -> bool:
    """A dish is available if every ingredient has enough stock for one serving."""
    return all(line.ingredient.stock >= line.amount for line in dish.ingredients)


def is_surplus(dish: Dish) -> bool:
    """A dish is surplus if any of its ingredients has more stock than its surplus level."""
    return any(line.ingredient.stock > line.ingredient.surplus_level for line in dish.ingredients)


def rank_menu(dishes: list[Dish]) -> list[dict]:
    """Available dishes only, surplus dishes first, then alphabetical."""
    menu = [
        {"id": d.id, "name": d.name, "price_cents": d.price_cents, "surplus": is_surplus(d)}
        for d in dishes
        if is_available(d)
    ]
    return sorted(menu, key=lambda item: (not item["surplus"], item["name"].lower()))
