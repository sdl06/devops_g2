def add_item(client, bill_id, dish_id, quantity=2):
    return client.post(f"/bills/{bill_id}/items", json={"dish_id": dish_id, "quantity": quantity})


def test_new_bill_starts_as_empty_draft(bill):
    assert bill["status"] == "draft"
    assert bill["version"] == 1
    assert bill["total_cents"] == 0
    assert bill["items"] == []


def test_bill_for_unknown_table_returns_404(client):
    assert client.post("/bills", json={"table_id": 999}).status_code == 404


def test_full_flow_bumps_version_on_every_change(client, bill, dish):
    item = add_item(client, bill["id"], dish["id"], quantity=2)
    assert item.status_code == 201
    assert item.json()["name"] == "Chicken curry"
    assert item.json()["price_cents"] == 1250
    assert item.json()["total_cents"] == 2500

    opened = client.post(f"/bills/{bill['id']}/open")
    assert opened.status_code == 200
    assert opened.json()["status"] == "open"
    assert opened.json()["version"] == 3  # 1 created, 2 item added, 3 opened
    assert opened.json()["total_cents"] == 2500

    closed = client.post(f"/bills/{bill['id']}/close")
    assert closed.json()["status"] == "closed"
    assert closed.json()["version"] == 4


def test_cannot_open_an_empty_bill(client, bill):
    response = client.post(f"/bills/{bill['id']}/open")
    assert response.status_code == 409
    assert response.json() == {"error": "Add at least one item before opening the bill"}


def test_cannot_open_twice_or_open_two_bills_on_one_table(client, table, bill, dish):
    add_item(client, bill["id"], dish["id"])
    client.post(f"/bills/{bill['id']}/open")
    assert client.post(f"/bills/{bill['id']}/open").status_code == 409

    second = client.post("/bills", json={"table_id": table["id"]}).json()
    add_item(client, second["id"], dish["id"])
    response = client.post(f"/bills/{second['id']}/open")
    assert response.status_code == 409
    assert "already has an open bill" in response.json()["error"]


def test_can_only_close_an_open_bill(client, bill):
    assert client.post(f"/bills/{bill['id']}/close").status_code == 409


def test_closed_bill_cannot_be_changed(client, table, bill, dish):
    item = add_item(client, bill["id"], dish["id"]).json()
    client.post(f"/bills/{bill['id']}/open")
    client.post(f"/bills/{bill['id']}/close")

    assert add_item(client, bill["id"], dish["id"]).status_code == 409
    assert client.put(f"/bills/{bill['id']}/items/{item['id']}", json={"quantity": 5}).status_code == 409
    assert client.delete(f"/bills/{bill['id']}/items/{item['id']}").status_code == 409
    assert client.put(f"/bills/{bill['id']}", json={"table_id": table["id"]}).status_code == 409


def test_update_and_delete_item_bump_version(client, bill, dish):
    item = add_item(client, bill["id"], dish["id"], quantity=1).json()

    updated = client.put(f"/bills/{bill['id']}/items/{item['id']}", json={"quantity": 3})
    assert updated.status_code == 200
    assert updated.json()["total_cents"] == 3750

    assert client.delete(f"/bills/{bill['id']}/items/{item['id']}").status_code == 204
    after = client.get(f"/bills/{bill['id']}").json()
    assert after["items"] == []
    assert after["version"] == 4  # created, added, updated, deleted


def test_item_errors(client, bill, dish):
    assert add_item(client, bill["id"], 999).status_code == 404
    assert add_item(client, 999, dish["id"]).status_code == 404
    assert client.put(f"/bills/{bill['id']}/items/999", json={"quantity": 1}).status_code == 404
    response = add_item(client, bill["id"], dish["id"], quantity=0)
    assert response.status_code == 400
    assert response.json()["error"].startswith("quantity:")


def test_item_keeps_name_and_price_after_menu_changes(client, bill, dish):
    add_item(client, bill["id"], dish["id"], quantity=1)
    client.put(f"/dishes/{dish['id']}", json={"name": "Spicy curry", "price_cents": 9999})
    client.delete(f"/dishes/{dish['id']}")

    item = client.get(f"/bills/{bill['id']}").json()["items"][0]
    assert item["name"] == "Chicken curry"
    assert item["price_cents"] == 1250
    assert item["dish_id"] is None


def test_move_bill_to_another_table(client, bill):
    other = client.post("/tables", json={"name": "Table 2"}).json()
    response = client.put(f"/bills/{bill['id']}", json={"table_id": other["id"]})
    assert response.json()["table_id"] == other["id"]
    assert response.json()["version"] == 2


def test_list_bills_with_filters(client, table, bill, dish):
    other_table = client.post("/tables", json={"name": "Table 2"}).json()
    client.post("/bills", json={"table_id": other_table["id"]})
    add_item(client, bill["id"], dish["id"])
    client.post(f"/bills/{bill['id']}/open")

    assert len(client.get("/bills").json()) == 2
    assert [b["id"] for b in client.get("/bills?status=open").json()] == [bill["id"]]
    assert len(client.get(f"/bills?table_id={other_table['id']}").json()) == 1


def test_only_draft_bills_can_be_deleted(client, bill, dish):
    add_item(client, bill["id"], dish["id"])
    client.post(f"/bills/{bill['id']}/open")
    assert client.delete(f"/bills/{bill['id']}").status_code == 409


def test_delete_draft_bill(client, bill):
    assert client.delete(f"/bills/{bill['id']}").status_code == 204
    assert client.get(f"/bills/{bill['id']}").status_code == 404
