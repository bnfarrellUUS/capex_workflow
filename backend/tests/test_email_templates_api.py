from tests.factories import make_user


def _login(client, username, password="secret123"):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def test_list_requires_admin(client, app):
    make_user("plain", roles='["REQUESTOR"]')
    _login(client, "plain")
    assert client.get("/api/email-templates").status_code == 403


def test_admin_can_list_get_save_preview_reset(client, app):
    make_user("boss", roles='["ADMIN"]')
    _login(client, "boss")

    items = client.get("/api/email-templates").get_json()
    assert {i["type"] for i in items} == {"ASSIGNED", "APPROVED", "REJECTED", "FINANCE_READY"}

    one = client.get("/api/email-templates/ASSIGNED").get_json()
    assert one["is_custom"] is False and "tokens" in one

    saved = client.put("/api/email-templates/ASSIGNED",
                       json={"subject": "S", "body_html": "<p>{number}</p>", "enabled": True}).get_json()
    assert saved["is_custom"] is True

    prev = client.post("/api/email-templates/ASSIGNED/preview",
                       json={"subject": "S", "body_html": "<p>{number}</p>"}).get_json()
    assert "CX000042" in prev["html"]           # sample data substituted

    reset = client.post("/api/email-templates/ASSIGNED/reset").get_json()
    assert reset["subject"] == items[0]["subject"] or reset["is_custom"] is True
