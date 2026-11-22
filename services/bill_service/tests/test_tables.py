def test_create_list_get_update_table(client):
    created = client.post("/tables", json={"name": "Table 1"})
    assert created.status_code == 201
    table_id = created.json()["id"]

    assert client.get("/tables").json() == [{"id": table_id, "name": "Table 1"}]
    assert client.get(f"/tables/{table_id}").json()["name"] == "Table 1"

    updated = client.put(f"/tables/{table_id}", json={"name": "Terrace 1"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Terrace 1"


def test_duplicate_table_name_is_rejected(client, table):
    response = client.post("/tables", json={"name": "Table 1"})
    assert response.status_code == 409
    assert "already exists" in response.json()["error"]


def test_renaming_to_an_existing_name_is_rejected(client, table):
    other = client.post("/tables", json={"name": "Table 2"}).json()
    response = client.put(f"/tables/{other['id']}", json={"name": "Table 1"})
    assert response.status_code == 409


def test_unknown_table_returns_404_with_error_format(client):
    response = client.get("/tables/999")
    assert response.status_code == 404
    assert response.json() == {"error": "Table not found"}


def test_empty_name_returns_400_with_field_name(client):
    response = client.post("/tables", json={"name": ""})
    assert response.status_code == 400
    assert response.json()["error"].startswith("name:")


def test_delete_table_without_bills(client, table):
    assert client.delete(f"/tables/{table['id']}").status_code == 204
    assert client.get(f"/tables/{table['id']}").status_code == 404


def test_cannot_delete_table_with_bills(client, table, bill):
    response = client.delete(f"/tables/{table['id']}")
    assert response.status_code == 409


def test_current_bill_for_qr_page(client, table, bill, dish):
    assert client.get(f"/tables/{table['id']}/current-bill").status_code == 404

    client.post(f"/bills/{bill['id']}/items", json={"dish_id": dish["id"], "quantity": 1})
    client.post(f"/bills/{bill['id']}/open")

    response = client.get(f"/tables/{table['id']}/current-bill")
    assert response.status_code == 200
    assert response.json()["id"] == bill["id"]
