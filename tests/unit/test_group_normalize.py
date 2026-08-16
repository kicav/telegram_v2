from tms.groups.service import normalize_group_reference

def test_normalize():
    assert normalize_group_reference('https://t.me/example')=='example'
    assert normalize_group_reference('@example')=='example'
