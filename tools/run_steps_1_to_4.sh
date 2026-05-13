#!/bin/bash
# Step 1: Dedup vault
# Step 2: Preflight
# Step 3: Move to staging (keep 200 in tier1)
# Steps 4-6 run separately (need human approval between)

set -e
cd /mnt/passport/shared/phosphene

echo "========================================="
echo "STEP 1: DEDUP"
echo "========================================="
echo "Before: $(ls vault/tier1/ | wc -l) T1 notes"
~/phosphene-venv/bin/python3 tools/dedup_vault.py
echo "After: $(ls vault/tier1/ | wc -l) T1 notes"

echo ""
echo "========================================="
echo "STEP 2: PREFLIGHT"
echo "========================================="
~/phosphene-venv/bin/python3 tools/preflight.py

echo ""
echo "========================================="
echo "STEP 3: STAGING"
echo "========================================="
# Clear any previous staging
rm -rf vault/staging 2>/dev/null
mkdir -p vault/staging

# Move all but first 200 files (sorted by name) to staging
cd vault/tier1
files=($(ls | sort))
total=${#files[@]}
keep=200

if [ "$total" -le "$keep" ]; then
    echo "Only $total files, keeping all"
else
    move_count=$((total - keep))
    echo "Total: $total, Keeping: $keep, Moving to staging: $move_count"
    
    # Move files starting from index $keep
    for ((i=keep; i<total; i++)); do
        mv "${files[$i]}" ../staging/
    done
    
    echo "tier1 now: $(ls | wc -l)"
    echo "staging now: $(ls ../staging/ | wc -l)"
fi
cd /mnt/passport/shared/phosphene

echo ""
echo "========================================="
echo "STEP 4: DRY-RUN CLUSTERING"
echo "========================================="
~/phosphene-venv/bin/python3 tools/dry_run_distillation.py

echo ""
echo "========================================="
echo "READY FOR STEP 5"
echo "========================================="
echo "tier1: $(ls vault/tier1/ | wc -l) notes"
echo "tier2: $(ls vault/tier2/ 2>/dev/null | wc -l) notes"
echo "staging: $(ls vault/staging/ | wc -l) notes"
echo ""
echo "To run distillation: ~/phosphene-venv/bin/python3 tools/distill_batch.py"
echo "Estimated cost: see cluster count above × \$0.015"
