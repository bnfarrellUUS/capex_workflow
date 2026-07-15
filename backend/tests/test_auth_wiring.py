from app.extensions import db, login_manager
from app.models import User
from app.services.security import hash_password


def test_user_loader_and_roles(app):
    u = User(email="a@x.com", name="A",
             password_hash=hash_password("x"), roles='["ADMIN","REQUESTOR"]')
    db.session.add(u)
    db.session.commit()
    loaded = login_manager._user_callback(u.id)
    assert loaded.id == u.id
    assert loaded.roles_list == ["ADMIN", "REQUESTOR"]
    assert loaded.is_active is True


def test_csrf_token_generation(app):
    from flask_wtf.csrf import generate_csrf
    with app.test_request_context():
        token = generate_csrf()
    assert isinstance(token, str) and len(token) > 0
