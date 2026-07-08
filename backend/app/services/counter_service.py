from app.extensions import db
from app.models import Counter

_COUNTER_NAME = "capex_request"


def next_request_number() -> str:
    counter = db.session.get(Counter, _COUNTER_NAME)
    if counter is None:
        counter = Counter(name=_COUNTER_NAME, value=0)
        db.session.add(counter)
    counter.value += 1
    db.session.commit()
    return f"CX{counter.value:06d}"
