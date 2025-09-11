#!/bin/bash
# © Broadcom. All Rights Reserved.
# The term “Broadcom” refers to Broadcom Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MPL-2.0

set -e
set -x

# Default variables
image_builder_root=${IB_ROOT:-"/image-builder/images/capi"}
default_packer_variables=${image_builder_root}/image/packer-variables/
packer_configuration_folder=${image_builder_root}
tkr_metadata_folder=${image_builder_root}/tkr-metadata/
custom_ovf_properties_file=${image_builder_root}/custom_ovf_properties.json
artifacts_output_folder=${image_builder_root}/artifacts
ova_destination_folder=${artifacts_output_folder}/ovas
ova_ts_suffix=$(date +%Y%m%d%H%M%S)

function copy_custom_image_builder_files() {
    cp image/hack/tkgs-image-build-ova.py hack/image-build-ova.py
    cp image/hack/tkgs_ovf_template.xml hack/ovf_template.xml
}

function download_ovftool() {
   wget -q  http://${HOST_IP}:${ARTIFACTS_CONTAINER_PORT}/artifacts/vmware-ovftool.zip || echo "VMware OVF Tool doesn't exist"
   unzip vmware-ovftool.zip -d /
}

function download_configuration_files() {
    # Download kubernetes configuration file
    wget -q http://${HOST_IP}:${ARTIFACTS_CONTAINER_PORT}/artifacts/metadata/kubernetes_config.json

    wget -q http://${HOST_IP}:${ARTIFACTS_CONTAINER_PORT}/artifacts/metadata/unified-tkr-vsphere.tar.gz
    mkdir ${tkr_metadata_folder}
    tar xzf unified-tkr-vsphere.tar.gz -C ${tkr_metadata_folder}

    # Download compatibility files
    wget -q http://${HOST_IP}:${ARTIFACTS_CONTAINER_PORT}/artifacts/metadata/compatibility/vmware-system.compatibilityoffering.json
    wget -q http://${HOST_IP}:${ARTIFACTS_CONTAINER_PORT}/artifacts/metadata/compatibility/vmware-system.guest.kubernetes.distribution.image.version.json

    # Download VKr constraints files
    wget -q http://${HOST_IP}:${ARTIFACTS_CONTAINER_PORT}/artifacts/metadata/vmware-system.kr.destination-semver-constraint.json || echo "override-semver-constraint.json don't exist"
    wget -q http://${HOST_IP}:${ARTIFACTS_CONTAINER_PORT}/artifacts/metadata/vmware-system.kr.override-semver-constraint.json || echo "override-semver-constraint.json don't exist"
}

# Generate packaer input variables based on packer-variables folder
function generate_packager_configuration() {
    mkdir -p $ova_destination_folder
    TKR_SUFFIX_ARG=
    [[ -n "$TKR_SUFFIX" ]] && TKR_SUFFIX_ARG="--tkr_suffix ${TKR_SUFFIX}"

    # additional_packer_variables
    ADDITIONAL_PACKER_VAR_FILES_LIST=
    [[ -n "$ADDITIONAL_PACKER_VARIABLE_FILES" ]] && ADDITIONAL_PACKER_VAR_FILES_LIST="--additional_packer_variables ${ADDITIONAL_PACKER_VARIABLE_FILES}"

    # override_package_repositories
    OVERRIDE_PACKAGE_REPO_FILE_LIST=
    [[ -n "${OVERRIDE_PACKAGE_REPOS}" ]] && OVERRIDE_PACKAGE_REPO_FILE_LIST="--override_package_repositories ${OVERRIDE_PACKAGE_REPOS}"

    python3 image/scripts/tkg_byoi.py setup \
    --host_ip ${HOST_IP} \
    --artifacts_container_port ${ARTIFACTS_CONTAINER_PORT} \
    --packer_http_port ${PACKER_HTTP_PORT} \
    --default_config_folder ${default_packer_variables} \
    --dest_config ${packer_configuration_folder} \
    --tkr_metadata_folder ${tkr_metadata_folder} \
    ${TKR_SUFFIX_ARG} \
    --kubernetes_config ${image_builder_root}/kubernetes_config.json \
    --ova_destination_folder ${ova_destination_folder} \
    --os_type ${OS_TARGET} \
    --ova_ts_suffix ${ova_ts_suffix} \
    ${ADDITIONAL_PACKER_VAR_FILES_LIST} \
    ${OVERRIDE_PACKAGE_REPO_FILE_LIST}

    echo "Image Builder Packer Variables"
    cat ${packer_configuration_folder}/packer-variables.json
}

function generate_custom_ovf_properties() {
    python3 image/scripts/utkg_custom_ovf_properties.py \
    --kubernetes_config ${image_builder_root}/kubernetes_config.json \
    --outfile ${custom_ovf_properties_file}
}


function download_stig_files() {
    if [[ "$OS_TARGET" != "photon-3" && "$OS_TARGET" != "photon-5" && "$OS_TARGET" != "ubuntu-2204-efi" ]]; then
        echo "Skipping STIG setup as '${OS_TARGET}' is not STIG Compliant"
        return
    fi

    stig_compliance_dir="${image_builder_root}/image/compliance"
    if [ -d "$stig_compliance_dir" ]
    then
        rm -rf "${stig_compliance_dir}"
    fi
    mkdir -p "${image_builder_root}/image/tmp"
    if [ ${OS_TARGET} == "photon-3" ]
    then
        wget -q http://${HOST_IP}:${ARTIFACTS_CONTAINER_PORT}/artifacts/photon-3-stig-hardening.tar.gz
        tar -xvf photon-3-stig-hardening.tar.gz -C "${image_builder_root}/image/tmp/"
        mv ${image_builder_root}/image/tmp/photon-3-stig-hardening-* "${stig_compliance_dir}"
        rm -rf photon-3-stig-hardening.tar.gz
    elif [ ${OS_TARGET} == "photon-5" ]
    then
        wget -q http://${HOST_IP}:${ARTIFACTS_CONTAINER_PORT}/artifacts/vmware-photon-5.0-stig-ansible-hardening.tar.gz
        tar -xvf vmware-photon-5.0-stig-ansible-hardening.tar.gz -C "${image_builder_root}/image/tmp/"
        mv ${image_builder_root}/image/tmp/vmware-photon-5.0-stig-ansible-hardening-* "${stig_compliance_dir}"
        rm -rf vmware-photon-5.0-stig-ansible-hardening.tar.gz
    elif [ ${OS_TARGET} == "ubuntu-2204-efi" ]
    then
        wget -q http://${HOST_IP}:${ARTIFACTS_CONTAINER_PORT}/artifacts/vmware-ubuntu-22.04-stig-ansible-hardening.tar.gz
        tar -xvf vmware-ubuntu-22.04-stig-ansible-hardening.tar.gz -C "${image_builder_root}/image/tmp/"
        mv ${image_builder_root}/image/tmp/vmware-ubuntu-22.04-stig-ansible-hardening-* "${stig_compliance_dir}"
        rm -rf vmware-ubuntu-22.04-stig-ansible-hardening.tar.gz
    fi
}

# Enable packer debug logging to the log file
function packer_logging() {
    mkdir /image-builder/packer_cache
    mkdir -p $artifacts_output_folder/logs
    export PACKER_LOG=10
    datetime=$(date '+%Y%m%d%H%M%S')
    export PACKER_LOG_PATH="${artifacts_output_folder}/logs/packer-$datetime-$RANDOM.log"
    echo "Generating packer logs to $PACKER_LOG_PATH"
}

# Invokes kubernetes image builder for the corresponding OS target
function trigger_image_builder() {
    EXTRA_ARGS=""
    ON_ERROR_ASK=1 PATH=$PATH:/home/imgbuilder-ova/.local/bin PACKER_CACHE_DIR=/image-builder/packer_cache \
    PACKER_VAR_FILES="${image_builder_root}/packer-variables.json"  \
    OVF_CUSTOM_PROPERTIES=${custom_ovf_properties_file} \
    IB_OVFTOOL=1 ANSIBLE_TIMEOUT=180 IB_OVFTOOL_ARGS="--allowExtraConfig" \
    make build-node-ova-vsphere-${OS_TARGET}
}

# Packer generates OVA with a different name so change the OVA name to OSImage/VMI and
# copy to the destination folder.
function copy_ova() {
    TKR_SUFFIX_ARG=
    [[ -n "$TKR_SUFFIX" ]] && TKR_SUFFIX_ARG="--tkr_suffix ${TKR_SUFFIX}"
    python3 image/scripts/tkg_byoi.py copy_ova \
    --kubernetes_config ${image_builder_root}/kubernetes_config.json \
    --tkr_metadata_folder ${tkr_metadata_folder} \
    ${TKR_SUFFIX_ARG} \
    --os_type ${OS_TARGET} \
    --ova_destination_folder ${ova_destination_folder} \
    --ova_ts_suffix ${ova_ts_suffix}
}

function main() {
    copy_custom_image_builder_files
    download_configuration_files
    download_ovftool
    generate_packager_configuration
    generate_custom_ovf_properties
    download_stig_files
    packer_logging
    trigger_image_builder
    copy_ova
}

main
