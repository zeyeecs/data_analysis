from datetime import date

from src.analysis import default_period_bounds


def test_default_period_bounds_recent_30_days():
    bounds = {
        "F": (date(2026, 5, 1), date(2026, 5, 21)),
        "R": (None, None),
        "V": (None, None),
    }
    start, end = default_period_bounds(bounds, days=30)
    assert end == date(2026, 5, 21)
    assert start == date(2026, 5, 1)
