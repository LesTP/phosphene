#!/bin/bash
# Clean reseed: clear everything, seed fresh, verify count
set -e
cd /mnt/passport/shared/phosphene

echo "=== CLEARING VAULT ==="
find vault -type f -delete 2>/dev/null || true
find vault -mindepth 1 -type d -delete 2>/dev/null || true
rm -f vault/.source_markers.json 2>/dev/null || true
echo "Cleared"

echo ""
echo "=== SEEDING ==="
~/phosphene-venv/bin/python3 -u run.py --seed-direct

echo ""
echo "=== SYNCING FILESYSTEM ==="
sync
sleep 5

echo ""
echo "=== VERIFYING ==="
count=$(ls vault/tier1/ | wc -l)
echo "T1 notes: $count"
if [ "$count" -lt 3800 ]; then
    echo "WARNING: Expected ~3859, got $count. NTFS flush may have lost notes."
else
    echo "OK: count looks correct"
fi
