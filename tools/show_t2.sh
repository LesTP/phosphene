#!/bin/bash
cd /mnt/passport/shared/phosphene
for f in vault/tier2/*.md; do
    echo "=== $(basename "$f") ==="
    head -40 "$f"
    echo ""
done
