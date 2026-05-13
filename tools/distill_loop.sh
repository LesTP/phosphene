#!/bin/bash
# Automated chronological distillation loop.
# Moves 200 notes from staging to tier1 per round, runs distillation,
# repeats until staging is empty.
#
# Usage: bash tools/distill_loop.sh 2>&1 | tee logs/distill_loop.log

set -e
cd /mnt/passport/shared/phosphene

BATCH_SIZE=200
round=0

echo "=== DISTILLATION LOOP ==="
echo "tier1: $(ls vault/tier1/ | wc -l)"
echo "staging: $(ls vault/staging/ | wc -l)"
echo "tier2: $(ls vault/tier2/ 2>/dev/null | wc -l)"
echo ""

while [ "$(ls vault/staging/ 2>/dev/null | wc -l)" -gt 0 ]; do
    round=$((round + 1))
    staging_count=$(ls vault/staging/ | wc -l)
    
    # Move next batch from staging to tier1
    cd vault/staging
    files=($(ls | sort | head -$BATCH_SIZE))
    moved=${#files[@]}
    for f in "${files[@]}"; do
        mv "$f" ../tier1/
    done
    cd /mnt/passport/shared/phosphene
    
    tier1_count=$(ls vault/tier1/ | wc -l)
    remaining=$((staging_count - moved))
    
    echo "============================================================"
    echo "Round $round: moved $moved notes (tier1: $tier1_count, staging: $remaining)"
    echo "============================================================"
    
    # Reset distillation metadata so the engine processes ALL notes, not just new ones
    rm -f vault/.phosphene/distillation_runs.json 2>/dev/null || true
    
    # Run distillation
    ~/phosphene-venv/bin/python3 tools/distill_batch.py $tier1_count
    
    t2_count=$(ls vault/tier2/ 2>/dev/null | wc -l)
    echo "  T2 notes after round $round: $t2_count"
    echo ""
done

echo "============================================================"
echo "LOOP COMPLETE"
echo "============================================================"
echo "Rounds: $round"
echo "tier1: $(ls vault/tier1/ | wc -l)"
echo "tier2: $(ls vault/tier2/ 2>/dev/null | wc -l)"
echo "staging: $(ls vault/staging/ 2>/dev/null | wc -l)"
