#!/bin/bash
echo "tier1: $(ls /mnt/passport/shared/phosphene/vault/tier1/ | wc -l)"
echo "staging: $(ls /mnt/passport/shared/phosphene/vault/staging/ | wc -l)"
echo "tier2: $(ls /mnt/passport/shared/phosphene/vault/tier2/ 2>/dev/null | wc -l)"
