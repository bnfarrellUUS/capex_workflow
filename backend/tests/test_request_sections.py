import pytest
from pydantic import ValidationError

from app.extensions import db
from app.models import AppSetting
from app.services import settings_service
from app.schemas.request_sections import HiddenSectionsIn
from tests.factories import make_user, make_division, make_draft


# ---- settings_service ----

def test_defaults_to_nothing_hidden(app):
    assert settings_service.get_hidden_sections() == []


def test_set_hidden_sections_persists_as_json(app):
    settings_service.set_hidden_sections(["economic"])
    assert settings_service.get_hidden_sections() == ["economic"]
    assert db.session.get(AppSetting, "wizard_hidden_sections").value == '["economic"]'


def test_set_hidden_sections_can_clear(app):
    settings_service.set_hidden_sections(["economic", "attachments"])
    settings_service.set_hidden_sections([])
    assert settings_service.get_hidden_sections() == []


def test_malformed_stored_value_reads_as_nothing_hidden(app):
    db.session.add(AppSetting(key="wizard_hidden_sections", value="not json"))
    db.session.commit()
    assert settings_service.get_hidden_sections() == []


# ---- schema validation ----

def test_schema_accepts_the_five_hideable_keys():
    keys = ["description", "effect_on_ops", "asset_details", "economic", "attachments"]
    assert HiddenSectionsIn(hidden=keys).hidden == keys


def test_schema_defaults_to_empty_list():
    assert HiddenSectionsIn().hidden == []


def test_schema_rejects_unknown_key():
    with pytest.raises(ValidationError):
        HiddenSectionsIn(hidden=["nonsense"])


@pytest.mark.parametrize("key", ["basic_info", "review"])
def test_schema_rejects_always_visible_sections(key):
    with pytest.raises(ValidationError):
        HiddenSectionsIn(hidden=[key])


def test_schema_collapses_duplicates():
    assert HiddenSectionsIn(hidden=["economic", "economic"]).hidden == ["economic"]


# ---- API ----

def _login(client, key, roles):
    make_user(key, roles=roles)
    client.post("/api/auth/login", json={"email": f"{key}@x.com", "password": "secret123"})


def test_get_defaults_to_empty_hidden_list(client):
    _login(client, "admin", '["ADMIN"]')
    assert client.get("/api/request-sections").get_json() == {"hidden": []}


def test_admin_put_persists_and_round_trips(client):
    _login(client, "admin", '["ADMIN"]')
    r = client.put("/api/request-sections", json={"hidden": ["economic"]})
    assert r.status_code == 200
    assert r.get_json() == {"hidden": ["economic"]}
    assert client.get("/api/request-sections").get_json() == {"hidden": ["economic"]}


def test_requestor_can_read_the_config(client):
    # The wizard needs this config, so it is not ADMIN-gated for reads.
    _login(client, "plain", '["REQUESTOR"]')
    assert client.get("/api/request-sections").status_code == 200


def test_non_admin_cannot_change_the_config(client):
    _login(client, "plain", '["REQUESTOR"]')
    assert client.put("/api/request-sections", json={"hidden": ["economic"]}).status_code == 403


def test_anonymous_cannot_read_the_config(client):
    assert client.get("/api/request-sections").status_code == 401


def test_put_rejects_unknown_section(client):
    _login(client, "admin", '["ADMIN"]')
    assert client.put("/api/request-sections", json={"hidden": ["nonsense"]}).status_code == 400


def test_put_rejects_hiding_basic_info(client):
    _login(client, "admin", '["ADMIN"]')
    assert client.put("/api/request-sections", json={"hidden": ["basic_info"]}).status_code == 400


def test_hidden_section_fields_are_still_saveable(client, app):
    # Visibility is display config, not a security boundary: a hidden section's
    # fields must keep saving so existing data is never made unwritable.
    owner = make_user("owner", roles='["REQUESTOR"]')
    div = make_division()
    req = make_draft(owner.id, div.id)
    settings_service.set_hidden_sections(["economic"])
    db.session.commit()
    client.post("/api/auth/login", json={"email": "owner@x.com", "password": "secret123"})

    r = client.patch(f"/api/requests/{req.id}", json={"annual_savings": "1200.00"})

    assert r.status_code == 200
    assert r.get_json()["annual_savings"] == "1200"  # money_str drops trailing zeros
