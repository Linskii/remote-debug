from remote_debug.dummy import dummy_add


def test_add_positive():
    assert dummy_add(2, 3) == 5


def test_add_negative():
    assert dummy_add(-1, -1) == -2
