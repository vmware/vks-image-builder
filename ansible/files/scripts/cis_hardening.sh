#!/bin/bash

set -euo pipefail

# Dropin files to check
TARGET_FILES=(
  "/usr/lib/systemd/system/kubelet.service.d/10-kubeadm.conf"
  "/usr/lib/systemd/system/kubelet.service.d/11-resource-sizing.conf"
)
TIMEOUT=300  # total seconds to wait
INTERVAL=2 

log() {
  echo "[CIS 4.1.1] $1"
}

log "Starting permission hardening for kubelet systemd service files."

# Wait until the first required file exists or timeout
elapsed=0
while [[ ! -f "${TARGET_FILES[0]}" && $elapsed -lt $TIMEOUT ]]; do
  sleep $INTERVAL
  elapsed=$((elapsed + INTERVAL))
done

if [[ -f "${TARGET_FILES[0]}" ]]; then
  log "Found ${TARGET_FILES[0]} after $elapsed seconds."
  for file in "${TARGET_FILES[@]}"; do
    if [[ -f "$file" ]]; then
      chmod 600 "$file" || true
      log "Permissions for $file set to 600."
    else
      log "File $file not found, skipping."
    fi
  done
else
  log "Timeout reached ($TIMEOUT). ${TARGET_FILES[0]} not found. Skipping permission fix."
fi