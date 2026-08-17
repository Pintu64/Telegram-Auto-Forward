from forwarder.service import normalize_reference
def test_normalize_reference():
    assert normalize_reference("https://t.me/example/") == "@example"
    assert normalize_reference("@example") == "@example"
    assert normalize_reference("example") == "@example"
    assert normalize_reference("-1001234567890") == -1001234567890
