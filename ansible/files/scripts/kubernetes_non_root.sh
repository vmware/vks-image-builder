#!/usr/bin/env bash

KUBE_CONFIG_DIR="$HOME/.kube"
KUBE_CONFIG_FILE="${KUBE_CONFIG_DIR}/config"
ADMIN_KUBE_CONFIG="/etc/kubernetes/admin.conf"

# Check for interactive bash
if [ "x${BASH_VERSION-}" != x -a "x${PS1-}" ]; then
  # Execute only if a) control plane node and b) non-root user
  if [ -f ${ADMIN_KUBE_CONFIG} -a "$EUID" -ne 0 ]; then
    # Execute only on first login
    if ! [ -f "${KUBE_CONFIG_FILE}" ]; then
      mkdir -p "${KUBE_CONFIG_DIR}"
      sudo cp ${ADMIN_KUBE_CONFIG} ${KUBE_CONFIG_FILE}
      sudo chown "$(id -u):$(id -g)" "${KUBE_CONFIG_FILE}"
    fi
  fi
fi