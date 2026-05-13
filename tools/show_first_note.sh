#!/bin/bash
f=$(ls /mnt/passport/shared/phosphene/vault/tier1/ | head -1)
echo "File: $f"
head -20 "/mnt/passport/shared/phosphene/vault/tier1/$f"
