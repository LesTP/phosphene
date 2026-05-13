#!/bin/bash
# Re-stage: move all but first 200 notes back to staging, clear T2 and metadata
set -e
cd /mnt/passport/shared/phosphene

echo "Clearing T2 and metadata..."
find vault/tier2 -type f -delete 2>/dev/null || true
rm -f vault/.phosphene/distillation_runs.json 2>/dev/null || true

echo "Re-staging..."
rm -rf vault/staging 2>/dev/null || true
mkdir -p vault/staging

cd vault/tier1
files=($(ls | sort))
total=${#files[@]}
keep=200

echo "Total: $total, Keeping: $keep"
move_count=$((total - keep))
for ((i=keep; i<total; i++)); do
    mv "${files[$i]}" ../staging/
done
cd /mnt/passport/shared/phosphene

echo "tier1: $(ls vault/tier1/ | wc -l)"
echo "staging: $(ls vault/staging/ | wc -l)"
echo "tier2: $(ls vault/tier2/ 2>/dev/null | wc -l)"
echo "Ready to run: bash tools/distill_loop.sh"
