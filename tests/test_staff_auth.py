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


def test_manager_people_admin_guards(
    client: TestClient,
    owner_auth: dict[str, str],
) -> None:
    assert client.post(
        "/api/staff/users/owner/role",
        headers=owner_auth,
        json={"role": "staff"},
    ).status_code == 400
    assert client.post("/api/staff/users/owner/disable", headers=owner_auth).status_code == 400

    promoted = client.post(
        "/api/staff/users/reception/role",
        headers=owner_auth,
        json={"role": "manager"},
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "manager"

    demoted = client.post(
        "/api/staff/users/reception/role",
        headers=owner_auth,
        json={"role": "staff"},
    )
    assert demoted.status_code == 200

    disabled = client.post("/api/staff/users/reception/disable", headers=owner_auth)
    assert disabled.status_code == 200
    assert disabled.json()["active"] is False

    users = client.get("/api/staff/users", headers=owner_auth)
    reception = next(item for item in users.json() if item["username"] == "reception")
    assert reception["active"] is False

    login_blocked = client.post(
        "/api/auth/login",
        json={"username": "reception", "password": "test-pass-99"},
    )
    assert login_blocked.status_code == 401

    enabled = client.post("/api/staff/users/reception/enable", headers=owner_auth)
    assert enabled.status_code == 200
    assert enabled.json()["active"] is True


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
