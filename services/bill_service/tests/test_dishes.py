def test_dish_crud(client):
    created = client.post("/dishes", json={"name": "Soup", "price_cents": 600})
    assert created.status_code == 201
    dish_id = created.json()["id"]
    assert created.json()["ingredients"] == []

    assert len(client.get("/dishes").json()) == 1
    assert client.get(f"/dishes/{dish_id}").json()["name"] == "Soup"

    updated = client.put(f"/dishes/{dish_id}", json={"name": "Tomato soup", "price_cents": 700})
    assert updated.json() == {"id": dish_id, "name": "Tomato soup", "price_cents": 700, "ingredients": []}

    assert client.delete(f"/dishes/{dish_id}").status_code == 204
    assert client.get(f"/dishes/{dish_id}").status_code == 404


def test_duplicate_dish_name_is_rejected(client, dish):
    assert client.post("/dishes", json={"name": "Chicken curry", "price_cents": 1}).status_code == 409


def test_negative_price_is_rejected(client):
    assert client.post("/dishes", json={"name": "Free", "price_cents": -1}).status_code == 400


def test_recipe_can_be_replaced(client, dish):
    rice = client.post(
        "/ingredients", json={"name": "Rice", "unit": "g", "stock": 1000, "surplus_level": 5000}
    ).json()
    response = client.put(
        f"/dishes/{dish['id']}/ingredients", json=[{"ingredient_id": rice["id"], "amount": 150}]
    )
    assert response.status_code == 200
    assert response.json()["ingredients"] == [{"ingredient_id": rice["id"], "amount": 150}]


def test_recipe_errors(client, dish):
    chicken_id = client.get(f"/dishes/{dish['id']}").json()["ingredients"][0]["ingredient_id"]
    duplicate = [{"ingredient_id": chicken_id, "amount": 1}, {"ingredient_id": chicken_id, "amount": 2}]
    assert client.put(f"/dishes/{dish['id']}/ingredients", json=duplicate).status_code == 400
    unknown = [{"ingredient_id": 999, "amount": 1}]
    assert client.put(f"/dishes/{dish['id']}/ingredients", json=unknown).status_code == 404


def test_menu_endpoint_shows_surplus_dish(client, dish):
    assert client.get("/menu").json() == [
        {"id": dish["id"], "name": "Chicken curry", "price_cents": 1250, "surplus": True}
    ]


def test_menu_hides_dish_when_stock_runs_out(client, dish):
    chicken_id = client.get(f"/dishes/{dish['id']}").json()["ingredients"][0]["ingredient_id"]
    client.put(
        f"/ingredients/{chicken_id}",
        json={"name": "Chicken", "unit": "g", "stock": 100, "surplus_level": 3000},
    )
    assert client.get("/menu").json() == []


def test_ingredient_crud(client):
    body = {"name": "Rice", "unit": "g", "stock": 1000, "surplus_level": 500}
    created = client.post("/ingredients", json=body)
    assert created.status_code == 201
    ingredient_id = created.json()["id"]

    assert len(client.get("/ingredients").json()) == 1
    assert client.get(f"/ingredients/{ingredient_id}").json()["stock"] == 1000

    updated = client.put(f"/ingredients/{ingredient_id}", json={**body, "stock": 10})
    assert updated.json()["stock"] == 10

    assert client.delete(f"/ingredients/{ingredient_id}").status_code == 204
    assert client.get(f"/ingredients/{ingredient_id}").status_code == 404


def test_duplicate_ingredient_name_is_rejected(client, dish):
    body = {"name": "Chicken", "unit": "g", "stock": 1, "surplus_level": 1}
    assert client.post("/ingredients", json=body).status_code == 409


def test_cannot_delete_ingredient_used_in_a_recipe(client, dish):
    chicken_id = client.get(f"/dishes/{dish['id']}").json()["ingredients"][0]["ingredient_id"]
    response = client.delete(f"/ingredients/{chicken_id}")
    assert response.status_code == 409
    assert "recipe" in response.json()["error"]
