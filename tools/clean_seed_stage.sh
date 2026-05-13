#!/bin/bash
# Steps 1-4: Clean seed + preflight + staging
set -e
cd /mnt/passport/shared/phosphene

echo "========================================="
echo "STEP 1: CLEAR VAULT"
echo "========================================="
find vault -type f -delete 2>/dev/null || true
find vault -mindepth 1 -type d -delete 2>/dev/null || true
rm -f vault/.source_markers.json 2>/dev/null || true
echo "Vault cleared"

echo ""
echo "========================================="
echo "STEP 2: RE-SEED (with timestamps)"
echo "========================================="
~/phosphene-venv/bin/python3 -u run.py --seed-direct

echo ""
echo "========================================="
echo "STEP 3: PREFLIGHT"
echo "========================================="
~/phosphene-venv/bin/python3 tools/preflight.py

echo ""
echo "========================================="
echo "STEP 4: STAGING (keep 200 by timestamp)"
echo "========================================="
rm -rf vault/staging 2>/dev/null || true
mkdir -p vault/staging

cd vault/tier1
# Sort by filename (which now includes original timestamps)
files=($(ls | sort))
total=${#files[@]}
keep=200

if [ "$total" -le "$keep" ]; then
    echo "Only $total files, keeping all"
else
    move_count=$((total - keep))
    echo "Total: $total, Keeping: $keep, Moving to staging: $move_count"
    for ((i=keep; i<total; i++)); do
        mv "${files[$i]}" ../staging/
    done
    echo "tier1: $(ls | wc -l)"
    echo "staging: $(ls ../staging/ | wc -l)"
fi
cd /mnt/passport/shared/phosphene

echo ""
echo "========================================="
echo "READY FOR DISTILLATION"
echo "========================================="
echo "tier1: $(ls vault/tier1/ | wc -l)"
echo "tier2: $(ls vault/tier2/ 2>/dev/null | wc -l)"
echo "staging: $(ls vault/staging/ | wc -l)"
