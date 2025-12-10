#!/usr/bin/env bash
set -euo pipefail

# Path to your main script
SCRIPT="bkp_data_stremio.sh"

export TOKEN_PASSPHRASE="abc"
export FORCE="true"

# Infinite loop
while true; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running $SCRIPT..."
    bash "$SCRIPT"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Done. Sleeping for 15 minutes..."
    sleep 900  # 900 seconds = 15 minutes
done
