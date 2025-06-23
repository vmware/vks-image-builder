#!/bin/bash
# Copyright 2023 VMware, Inc.
# SPDX-License-Identifier: MPL-2.0

set -e
source $(dirname "${BASH_SOURCE[0]}")/utils.sh

enable_debugging

is_argument_set "KUBERNETES_VERSION argument is required" $KUBERNETES_VERSION

if [ -z "$ARTIFACTS_CONTAINER_PORT" ]; then
    # Makefile creates this environment variables
    ARTIFACTS_CONTAINER_PORT=$DEFAULT_ARTIFACTS_CONTAINER_PORT
    echo "Using default port for artifacts container $DEFAULT_ARTIFACTS_CONTAINER_PORT"
fi

artifacts_container_image_url=$(jq -r '.artifacts_image' $SUPPORTED_CONTEXT_JSON)
if [ "$artifacts_container_image_url" == "null" ]; then
    print_error 'Missing artifact server container image url'
    exit 1
fi

container_name=$(get_artifacts_container_name "$KUBERNETES_VERSION")

docker rm -f $container_name
docker run -d --name $container_name $(get_artifacts_container_labels $KUBERNETES_VERSION) -p $ARTIFACTS_CONTAINER_PORT:80 --platform linux/amd64 $artifacts_container_image_url

next_hint_msg "Use \"make build-node-image OS_TARGET=<os_target> KUBERNETES_VERSION=${KUBERNETES_VERSION} TKR_SUFFIX=<tkr_suffix> HOST_IP=<host_ip> IMAGE_ARTIFACTS_PATH=<image_artifacts_path> ARTIFACTS_CONTAINER_PORT=${ARTIFACTS_CONTAINER_PORT} PACKER_HTTP_PORT=${DEFAULT_PACKER_HTTP_PORT}\" to build node image"
next_hint_msg "Change PACKER_HTTP_PORT if the ${DEFAULT_PACKER_HTTP_PORT} port is already in use or not opened"