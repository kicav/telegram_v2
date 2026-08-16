from tms.datasets.set_operations import difference, intersection, union


def test_set_ops():
    a = {1, 2, 3}
    b = {3, 4}
    assert union(a, b) == {1, 2, 3, 4}
    assert difference(a, b) == {1, 2}
    assert intersection(a, b) == {3}
