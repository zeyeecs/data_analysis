"""SQL 最近邻配对 ORDER BY delta ASC, date ASC 须与本模块结果一致。"""

from datetime import date

from src.snapshot_pairing import nearest_snapshot_pair

# 与 sql/shop_comparison.sql、sql/vestiaire_reference_comparison.sql 共用向量
SQL_ALIGNMENT_CASES = [
    (date(2025, 3, 1), [date(2025, 2, 28)], date(2025, 2, 28)),
    (date(2025, 3, 1), [date(2025, 2, 25)], None),
    (date(2025, 3, 10), [date(2025, 3, 13), date(2025, 3, 7)], date(2025, 3, 7)),
]


def test_sql_alignment_vectors():
    for anchor, candidates, expected in SQL_ALIGNMENT_CASES:
        assert nearest_snapshot_pair(anchor, candidates) == expected
