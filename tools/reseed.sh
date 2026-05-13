#!/bin/bash
# Clear vault and re-run chronological seed
set -e

cd /mnt/passport/shared/phosphene

echo "Clearing vault..."
find vault -type f -delete 2>/dev/null || true
find vault -mindepth 1 -type d -delete 2>/dev/null || true
echo "Vault cleared: $(ls vault/ 2>/dev/null | wc -l) items remaining"

echo "Launching chronological seed..."
mkdir -p logs
nohup ~/phosphene-venv/bin/python3 -u run.py --seed-chronological > logs/seed_v5.log 2>&1 &
echo "PID: $!"

echo "Waiting 60s for first batches..."
sleep 60
echo "=== Log so far ==="
tail -30 logs/seed_v5.log
