"""Create the first real administrator on a deployed database.

    python create_admin.py <email> "<name>"

Prompts for the password (twice, not echoed) so it never lands in shell
history. Unlike seed.py -- whose admin password is in the repo -- this is safe
to run against Azure SQL. The account holds ADMIN only; give it other roles
from Admin -> Users afterwards.
"""

import getpass
import sys

from app import create_app
from app.extensions import db
from app.models import User
from app.roles import serialize_roles
from app.services.security import hash_password

MIN_PASSWORD_LENGTH = 12


def create_admin(session, email, name, password):
    mail = email.strip().lower()
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"The password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if session.query(User).filter_by(email=mail).first() is not None:
        raise ValueError(f"A user with email {mail} already exists.")
    user = User(email=mail, name=name.strip(), password_hash=hash_password(password),
                roles=serialize_roles(["ADMIN"]), active=True,
                must_change_password=False)
    session.add(user)
    session.commit()
    return user


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit('Usage: python create_admin.py <email> "<name>"')
    password = getpass.getpass("Password: ")
    if getpass.getpass("Repeat password: ") != password:
        sys.exit("The passwords do not match.")
    app = create_app()
    with app.app_context():
        try:
            user = create_admin(db.session, sys.argv[1], sys.argv[2], password)
        except ValueError as err:
            sys.exit(str(err))
        print(f"Created administrator {user.email}.")
