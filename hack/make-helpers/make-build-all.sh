#!/bin/bash
# Copyright 2023 VMware, Inc.
# SPDX-License-Identifier: MPL-2.0

set -e
source $(dirname "${BASH_SOURCE[0]}")/utils.sh
enable_debugging

ROOT=$(dirname "${BASH_SOURCE[0]}")/../..

# First make sure there are not containers running
make clean-containers -C "${ROOT}"

artifact_container_port_counter=9090
packer_port_counter=8081
output_counter=1
KUBERNETES_VERSION=$(cat $SUPPORTED_VERSION_TEXT | xargs)

echo "Running artifact container for '${KUBERNETES_VERSION} exposing port at '${artifact_container_port_counter}'"
make run-artifacts-container -C "${ROOT}" ARTIFACTS_CONTAINER_PORT="${artifact_container_port_counter}"

while read supported_os; do
    echo "Building node image for '${KUBERNETES_VERSION} | ${supported_os}' using packer port '${packer_port_counter}'"
    make build-node-image -C "${ROOT}" OS_TARGET="${supported_os}" TKR_SUFFIX="demo" HOST_IP=$(hostname -I | awk '{print $1}') IMAGE_ARTIFACTS_PATH="${PWD}/output${output_counter}" DEBUGGING=1 ARTIFACTS_CONTAINER_PORT="${artifact_container_port_counter}" PACKER_HTTP_PORT="${packer_port_counter}"
    
    packer_port_counter=$((packer_port_counter+1))
    output_counter=$((output_counter+1))
done < <(cat "${SUPPORTED_CONTEXT_JSON}" | jq -c -r '.supported_os[]')
