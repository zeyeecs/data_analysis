from datetime import date

from src.snapshot_pairing import nearest_snapshot_pair


def test_same_day():
    anchor = date(2025, 3, 1)
    assert nearest_snapshot_pair(anchor, [date(2025, 3, 1)]) == date(2025, 3, 1)


def test_one_day_gap():
    anchor = date(2025, 3, 1)
    assert nearest_snapshot_pair(anchor, [date(2025, 2, 28)]) == date(2025, 2, 28)


def test_three_day_gap_allowed():
    anchor = date(2025, 3, 1)
    assert nearest_snapshot_pair(anchor, [date(2025, 2, 26)]) == date(2025, 2, 26)


def test_four_day_gap_no_pair():
    anchor = date(2025, 3, 1)
    assert nearest_snapshot_pair(anchor, [date(2025, 2, 25)]) is None


def test_empty_candidates():
    assert nearest_snapshot_pair(date(2025, 3, 1), []) is None


def test_picks_smallest_delta():
    anchor = date(2025, 3, 1)
    assert nearest_snapshot_pair(
        anchor,
        [date(2025, 2, 20), date(2025, 2, 28), date(2025, 3, 3)],
    ) == date(2025, 2, 28)


def test_tie_picks_earlier_date():
    anchor = date(2025, 3, 10)
    assert nearest_snapshot_pair(
        anchor,
        [date(2025, 3, 13), date(2025, 3, 7)],
    ) == date(2025, 3, 7)


def test_all_candidates_over_gap():
    anchor = date(2025, 3, 1)
    assert nearest_snapshot_pair(anchor, [date(2025, 1, 1), date(2025, 2, 1)]) is None
