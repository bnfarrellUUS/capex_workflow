from functools import wraps

from flask import jsonify
from flask_login import login_required, current_user


def require_roles(*roles):
    def decorator(fn):
        @login_required
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not any(r in current_user.roles_list for r in roles):
                return jsonify(error="Forbidden."), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
