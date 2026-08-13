from parity import is_even


def test_even():
    assert is_even(2) is True


def test_odd():
    assert is_even(3) is False
