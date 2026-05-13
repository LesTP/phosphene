#!/bin/bash
# Delete source markers and re-seed to fill missing T1 notes
set -e
cd /mnt/passport/shared/phosphene

echo "Before: $(ls vault/tier1/ 2>/dev/null | wc -l) T1 notes"

# Delete markers so adapters re-poll everything
rm -f vault/.source_markers.json
echo "Markers deleted"

# Run seed-direct (free — local embeddings only, no LLM)
echo "Running --seed-direct..."
~/phosphene-venv/bin/python3 -u run.py --seed-direct

echo "After: $(ls vault/tier1/ 2>/dev/null | wc -l) T1 notes"
