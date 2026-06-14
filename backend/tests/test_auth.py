def test_signup_and_me(client):
    signup_res = client.post(
        "/api/v1/auth/signup",
        json={"username": "alice", "email": "alice@example.com", "password": "password123"},
    )
    assert signup_res.status_code == 200
    body = signup_res.json()
    assert body["access_token"]
    assert body["refresh_token"]

    me_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me_res.status_code == 200
    me_body = me_res.json()
    assert me_body["username"] == "alice"


def test_refresh_rotates_tokens(client):
    signup_res = client.post(
        "/api/v1/auth/signup",
        json={"username": "bob", "email": "bob@example.com", "password": "password123"},
    )
    assert signup_res.status_code == 200
    first_pair = signup_res.json()

    refresh_res = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_pair["refresh_token"]},
    )
    assert refresh_res.status_code == 200
    second_pair = refresh_res.json()
    assert second_pair["access_token"] != first_pair["access_token"]
    assert second_pair["refresh_token"] != first_pair["refresh_token"]

    reuse_old_res = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_pair["refresh_token"]},
    )
    assert reuse_old_res.status_code == 401


def test_logout_revokes_refresh_token(client):
    signup_res = client.post(
        "/api/v1/auth/signup",
        json={"username": "carol", "email": "carol@example.com", "password": "password123"},
    )
    assert signup_res.status_code == 200
    pair = signup_res.json()

    logout_res = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": pair["refresh_token"]},
    )
    assert logout_res.status_code == 200

    refresh_res = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": pair["refresh_token"]},
    )
    assert refresh_res.status_code == 401
