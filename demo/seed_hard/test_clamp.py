from clamp import clamp


def test_inside():
    assert clamp(5, 0, 10) == 5


def test_below():
    assert clamp(-2, 0, 10) == 0


def test_above():
    assert clamp(99, 0, 10) == 10
