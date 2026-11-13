from escriba.core import fmt_ts


def test_fmt_ts():
    assert fmt_ts(0) == "00:00:00"
    assert fmt_ts(3661) == "01:01:01"
