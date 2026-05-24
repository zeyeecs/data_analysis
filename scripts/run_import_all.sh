#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
LOG=import_all.log
exec > >(tee "$LOG") 2>&1

echo "=== $(date) reset + import V ==="
python3 -u scripts/import_to_tables.py --reset --category V

echo "=== $(date) import R ==="
python3 -u scripts/import_to_tables.py --category R

echo "=== $(date) import F ==="
python3 -u scripts/import_to_tables.py --category F

echo "=== $(date) drop legacy tables ==="
python3 -u scripts/import_to_tables.py --drop-legacy

echo "=== $(date) done ==="
