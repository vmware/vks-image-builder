#!/bin/bash
# This script monitors cloud-init output and journal logs (errors and higher) and redirects them
# to host logs via vmware-rpctool. It runs until cloud-init completes or a default timeout of 15 minutes is reached.

set -euo pipefail

# Config 
BUFFER_FILE="/run/logredirect/buffer.log"
# Path to cloud-init log
CLOUDINIT_LOG="/var/log/cloud-init-output.log"
# Path to cloud-init completion file (created when cloud-init finishes successfully)
CLOUDINIT_DONE="/run/cloud-init/result.json"
# Default timeout: 15 minutes (in seconds)
TIMEOUT_SECONDS=400
# Sleep interval after flushing to avoid rapid-fire rpc calls that could trigger throttling
FLUSH_INTERVAL=1
# Message chunk size
CHUNK_SIZE=100
# Path to the VMWare RPC tool
RPC_TOOL="/usr/bin/vmware-rpctool"
# Record the script start time
START_TIME=$(date +%s)

# Setup
mkdir -p "$(dirname "$BUFFER_FILE")"
: > "$BUFFER_FILE"

# flush_logs: Sends the buffered log lines via vmware-rpctool.
flush_logs() {
  local line chunk count=0
  # Check buffer size and only flush if there is content
  if [ -s "$BUFFER_FILE" ]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
      echo "count $count"
      while [[ -n "$line" ]]; do
        chunk="${line:0:$CHUNK_SIZE}"
        line="${line:$CHUNK_SIZE}"
        $RPC_TOOL "log $chunk" || echo "Error sending log chunk: $chunk"
        sleep 0.1
      done
    done < "$BUFFER_FILE"
    : > "$BUFFER_FILE"  # Clear buffer after flushing
  fi
}

# flusher: background log flusher
flusher() {
  while true; do
    sleep "$FLUSH_INTERVAL"
    flush_logs
  done
}

# tail_cloudinit: Tails throttled log file continuously and processes each line.
# Uses tail -F to follow the file; stops if cloud-init completes or timeout is reached.
tail_cloudinit() {
  touch "$CLOUDINIT_LOG"
  tail -n +1 -F "$CLOUDINIT_LOG" 2>/dev/null | while read -r line; do
    echo "[CLOUDINIT] $line" >> "$BUFFER_FILE"
  done
}

# tail_journal: Monitors high-priority journal logs continuously.
# Uses journalctl with -p 3 (errors and above) and follows output.
tail_journal() {
  journalctl -p 3 -xb -f -o cat --no-pager | while read -r line; do
    echo "[JOURNAL] $line" >> "$BUFFER_FILE"
  done
}

# Monitor cloud-init completion or timeout and terminate the background processes 
monitor_completion() {
    while true; do
        local now
        now=$(date +%s)
        # If cloud-init result file exists, we assume cloud-init has completed
        if [[ -f "${CLOUDINIT_DONE}" ]]; then
            $RPC_TOOL "log [LOG_REDIRECT] Cloud-init completed successfully." || true
            break
        fi
        # If timeout is reached, log a message and break
        if (((now - START_TIME) >= TIMEOUT_SECONDS )); then
            $RPC_TOOL "log [LOG_REDIRECT] Timeout reached after $TIMEOUT_SECONDS seconds. Cloud-init did not complete." || true
            break
        fi
        sleep 5
    done
}


# Launch Jobs 
tail_cloudinit &
PID_CLOUDINIT=$!

tail_journal &
PID_JOURNAL=$!

flusher &
PID_FLUSHER=$!

monitor_completion
STATUS=$?

# Cleanup
sleep 3
kill "$PID_CLOUDINIT" "$PID_JOURNAL" "$PID_FLUSHER" 2>/dev/null || true
wait "$PID_CLOUDINIT" "$PID_JOURNAL" "$PID_FLUSHER" 2>/dev/null || true

flush_logs  # Final flush before exit

exit 0