import json

ROLES = ["REQUESTOR", "APPROVER", "FINANCE", "ADMIN"]


def valid_roles(roles) -> bool:
    return all(r in ROLES for r in roles)


def serialize_roles(roles) -> str:
    # Keep only known roles, in canonical order.
    return json.dumps([r for r in ROLES if r in roles])
