from app.services.counter_service import next_request_number


def test_first_number_is_cx000001(app):
    assert next_request_number() == "CX000001"


def test_numbers_increment(app):
    a = next_request_number()
    b = next_request_number()
    c = next_request_number()
    assert [a, b, c] == ["CX000001", "CX000002", "CX000003"]
