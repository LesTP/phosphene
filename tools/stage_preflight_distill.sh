#!/bin/bash
# Stage 200 notes, run preflight, then distill
set -e
cd /mnt/passport/shared/phosphene

echo "=== STAGING ==="
rm -rf vault/staging 2>/dev/null || true
mkdir -p vault/staging

cd vault/tier1
files=($(ls | sort))
total=${#files[@]}
keep=200

echo "Total: $total, Keeping: $keep"
if [ "$total" -le "$keep" ]; then
    echo "Only $total files, keeping all"
else
    move_count=$((total - keep))
    for ((i=keep; i<total; i++)); do
        mv "${files[$i]}" ../staging/
    done
    echo "tier1: $(ls | wc -l), staging: $(ls ../staging/ | wc -l)"
fi
cd /mnt/passport/shared/phosphene

echo ""
echo "=== PREFLIGHT ==="
~/phosphene-venv/bin/python3 tools/preflight.py

echo ""
echo "=== DISTILLATION (200 notes) ==="
~/phosphene-venv/bin/python3 tools/distill_batch.py 200
