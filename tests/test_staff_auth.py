from fastapi.testclient import TestClient


def test_reception_can_use_the_desk(client: TestClient, reception_auth: dict[str, str]) -> None:
    queue = client.get("/api/queue", headers=reception_auth)
    assert queue.status_code == 200


def test_manager_can_list_staff_users(
    client: TestClient,
    reception_auth: dict[str, str],
    owner_auth: dict[str, str],
) -> None:
    forbidden = client.get("/api/staff/users", headers=reception_auth)
    assert forbidden.status_code == 403

    users = client.get("/api/staff/users", headers=owner_auth)
    assert users.status_code == 200
    names = {item["username"] for item in users.json()}
    assert names == {"owner", "reception"}


def test_manager_can_clear_another_users_mfa(
    client: TestClient,
    owner_auth: dict[str, str],
) -> None:
    self_clear = client.post("/api/staff/users/owner/mfa/reset", headers=owner_auth)
    assert self_clear.status_code == 400

    cleared = client.post("/api/staff/users/reception/mfa/reset", headers=owner_auth)
    assert cleared.status_code == 200


def test_manager_can_create_a_staff_user(client: TestClient, owner_auth: dict[str, str]) -> None:
    created = client.post(
        "/api/staff/users",
        headers=owner_auth,
        json={
            "username": "physio1",
            "password": "another-pass-99",
            "role": "staff",
        },
    )
    assert created.status_code == 201
    assert created.json()["username"] == "physio1"
