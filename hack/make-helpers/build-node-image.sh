#!/bin/bash
# © Broadcom. All Rights Reserved.
# The term “Broadcom” refers to Broadcom Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MPL-2.0

set -e

source $(dirname "${BASH_SOURCE[0]}")/utils.sh
ROOT=$(dirname "${BASH_SOURCE[0]}")/../..

enable_debugging

is_argument_set "KUBERNETES_VERSION argument is required" $KUBERNETES_VERSION
is_argument_set "OS_TARGET argument is required" $OS_TARGET
# if [[ $OS_TARGET != windows-* ]]; then
#   is_argument_set "TKR_SUFFIX argument is required" $TKR_SUFFIX
# fi
is_argument_set "HOST_IP argument is required" $HOST_IP
is_argument_set "IMAGE_ARTIFACTS_PATH argument is required" $IMAGE_ARTIFACTS_PATH

KUBERNETES_VERSION=$(cat supported-version.txt | xargs)

if [ -z "$ARTIFACTS_CONTAINER_PORT" ]; then
    # Makefile creates this environment variables
    ARTIFACTS_CONTAINER_PORT=$DEFAULT_ARTIFACTS_CONTAINER_PORT
    echo "Using default port for artifacts container $DEFAULT_ARTIFACTS_CONTAINER_PORT"
fi

if [ -z "$PACKER_HTTP_PORT" ]; then
    # Makefile creates this environment variables
    PACKER_HTTP_PORT=$DEFAULT_PACKER_HTTP_PORT
    echo "Using default Packer HTTP port $PACKER_HTTP_PORT"
fi

function build_node_image() {
    docker rm -f $(get_node_image_builder_container_name "$KUBERNETES_VERSION" "$OS_TARGET")

    # allow unattanded anwer file to be overriden
    AUTO_UNATTEND_ANSWER_FILE_BIND=
    [ -n "$AUTO_UNATTEND_ANSWER_FILE_PATH" ] && AUTO_UNATTEND_ANSWER_FILE_BIND="-v ${AUTO_UNATTEND_ANSWER_FILE_PATH}:/image-builder/images/capi/packer/ova/windows/${OS_TARGET}/autounattend.xml"

    # additional_jinja_args
    ADDITIONAL_PACKER_VAR_FILES_MOUNTS=
    INCONTAINER_ADDITIONAL_PACKER_VAR_ENV=
    if [ -n "$ADDITIONAL_PACKER_VARIABLE_FILES" ]; then
        for i in ${ADDITIONAL_PACKER_VARIABLE_FILES//,/ }
        do
            FILENAME=$(basename -- "${i}")
            INCONTAINER_PATH="/image-builder/images/capi/image/customizations/${FILENAME}"
            ADDITIONAL_PACKER_VAR_FILES_MOUNTS="${ADDITIONAL_PACKER_VAR_FILES_MOUNTS} -v ${i}:${INCONTAINER_PATH}"
            if [[ "${#INCONTAINER_ADDITIONAL_PACKER_VAR_ENV}" == 0 ]];then
                INCONTAINER_ADDITIONAL_PACKER_VAR_ENV="-e ADDITIONAL_PACKER_VARIABLE_FILES=${INCONTAINER_PATH}"
            else
                INCONTAINER_ADDITIONAL_PACKER_VAR_ENV="${INCONTAINER_ADDITIONAL_PACKER_VAR_ENV},${INCONTAINER_PATH}"
            fi
        done
    fi

    # override_package_repositories
    OVERRIDE_REPO_MOUNTS=
    INCONTAINER_OVERRIDE_REPO_ENV=  
    if [ -n "$OVERRIDE_PACKAGE_REPOS" ]; then
        for i in ${OVERRIDE_PACKAGE_REPOS//,/ }
        do
            FILENAME=$(basename -- "${i}")
            INCONTAINER_PATH="/image-builder/images/capi/image/custom-repos/${FILENAME}"
            OVERRIDE_REPO_MOUNTS="${OVERRIDE_REPO_MOUNTS} -v ${i}:${INCONTAINER_PATH}"
            if [[ "${#INCONTAINER_OVERRIDE_REPO_ENV}" == 0 ]];then
                INCONTAINER_OVERRIDE_REPO_ENV="-e OVERRIDE_PACKAGE_REPOS=${INCONTAINER_PATH}"
            else
                INCONTAINER_OVERRIDE_REPO_ENV="${INCONTAINER_OVERRIDE_REPO_ENV},${INCONTAINER_PATH}"
            fi
        done
    fi

    docker run -d \
        --name $(get_node_image_builder_container_name "$KUBERNETES_VERSION" "$OS_TARGET") \
        $(get_node_image_builder_container_labels "$KUBERNETES_VERSION" "$OS_TARGET") \
        -v $ROOT/ansible:/image-builder/images/capi/image/ansible \
        -v $ROOT/ansible-finalize:/image-builder/images/capi/image/ansible-finalize \
        -v $ROOT/ansible-windows:/image-builder/images/capi/image/ansible-windows \
        -v $ROOT/goss:/image-builder/images/capi/image/goss \
        -v $ROOT/hack:/image-builder/images/capi/image/hack \
        -v $ROOT/packer-variables:/image-builder/images/capi/image/packer-variables \
        -v $ROOT/scripts:/image-builder/images/capi/image/scripts \
        -v $IMAGE_ARTIFACTS_PATH:/image-builder/images/capi/artifacts \
        ${ADDITIONAL_PACKER_VAR_FILES_MOUNTS} \
        ${OVERRIDE_REPO_MOUNTS} \
        ${INCONTAINER_ADDITIONAL_PACKER_VAR_ENV} \
        ${INCONTAINER_OVERRIDE_REPO_ENV} \
        ${AUTO_UNATTEND_ANSWER_FILE_BIND} \
        -w /image-builder/images/capi/ \
        -e HOST_IP=$HOST_IP -e ARTIFACTS_CONTAINER_PORT=$ARTIFACTS_CONTAINER_PORT -e OS_TARGET=$OS_TARGET \
        -e TKR_SUFFIX=$TKR_SUFFIX -e KUBERNETES_VERSION=$KUBERNETES_VERSION \
        -e PACKER_HTTP_PORT=$PACKER_HTTP_PORT \
        -p $PACKER_HTTP_PORT:$PACKER_HTTP_PORT \
        --platform linux/amd64 \
        $(get_image_builder_container_image_name $KUBERNETES_VERSION)
}

supported_os_list=$(jq -r '.supported_os' $SUPPORTED_CONTEXT_JSON)
if [ "$supported_os_list" == "null" ]; then
    print_error 'Use supported KUBERNETES_VERSION, run "make list-versions" to list the supported kubernetes versions'
    exit 1
fi

supported_os=false
while read SUPPORTED_OS_TARGET; do
    if [ $SUPPORTED_OS_TARGET == $OS_TARGET ]; then
        build_node_image
		echo ""
		next_hint_msg "Use \"docker logs -f $(get_node_image_builder_container_name $KUBERNETES_VERSION $OS_TARGET)\" to see logs and status"
		next_hint_msg "Node Image OVA can be found at $IMAGE_ARTIFACTS_PATH/ovas/"
        supported_os=true
    fi
done < <(jq -r '.supported_os[]' "$SUPPORTED_CONTEXT_JSON")

if [ "$supported_os" == false ]; then
	print_error 'Use supported OS_TARGET, run "make list-supported-os" to list the supported kubernetes versions'
	exit 1
fi
