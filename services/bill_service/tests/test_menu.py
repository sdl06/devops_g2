"""Unit tests for the recommendation rule (no database needed)."""

from types import SimpleNamespace

from app.menu import is_available, is_surplus, rank_menu


def make_dish(dish_id, name, lines):
    """lines: list of (amount per serving, stock, surplus_level)."""
    return SimpleNamespace(
        id=dish_id,
        name=name,
        price_cents=1000,
        ingredients=[
            SimpleNamespace(
                amount=amount,
                ingredient=SimpleNamespace(stock=stock, surplus_level=surplus_level),
            )
            for amount, stock, surplus_level in lines
        ],
    )


def test_dish_is_available_when_every_ingredient_has_enough_stock():
    assert is_available(make_dish(1, "Curry", [(200, 200, 1000), (50, 500, 1000)]))


def test_dish_is_not_available_when_one_ingredient_is_short():
    assert not is_available(make_dish(1, "Curry", [(200, 5000, 1000), (50, 49, 1000)]))


def test_dish_is_surplus_when_any_ingredient_is_above_its_surplus_level():
    assert is_surplus(make_dish(1, "Curry", [(200, 5000, 3000), (50, 100, 1000)]))


def test_dish_is_not_surplus_at_exactly_the_surplus_level():
    assert not is_surplus(make_dish(1, "Curry", [(200, 3000, 3000)]))


def test_menu_hides_unavailable_dishes_and_puts_surplus_first():
    dishes = [
        make_dish(1, "Soup", [(100, 500, 1000)]),  # available, normal
        make_dish(2, "Curry", [(200, 5000, 3000)]),  # available, surplus
        make_dish(3, "Steak", [(300, 100, 1000)]),  # out of stock
        make_dish(4, "Bread", [(50, 500, 1000)]),  # available, normal
    ]
    menu = rank_menu(dishes)
    assert [item["name"] for item in menu] == ["Curry", "Bread", "Soup"]
    assert [item["surplus"] for item in menu] == [True, False, False]


def test_dish_without_recipe_is_available_but_not_surplus():
    menu = rank_menu([make_dish(1, "Water", [])])
    assert menu == [{"id": 1, "name": "Water", "price_cents": 1000, "surplus": False}]
