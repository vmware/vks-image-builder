# © Broadcom. All Rights Reserved.
# The term “Broadcom” refers to Broadcom Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MPL-2.0

ARG BASE_IMAGE=library/photon:5.0
FROM ${BASE_IMAGE}

ARG IMAGE_BUILDER_COMMIT_ID=""
ARG ANSIBLE_VERSION=2.15.13
ARG IMAGE_BUILDER_REPO="https://github.com/kubernetes-sigs/image-builder.git"
ARG IMAGE_BUILDER_REPO_NAME=image-builder
ARG PACKER_GITHUB_API_TOKEN=""

ARG WINDOWS_ADMIN_PASSWORD
ENV WINDOWS_ADMIN_PASSWORD="${WINDOWS_ADMIN_PASSWORD}"

ENV PATH=${PATH}:/ovftool
ENV LANG=en_US.UTF-8

SHELL ["/bin/bash", "-c"]

RUN tdnf -y update
RUN tdnf -y upgrade

# Install required packages
RUN for package in unzip git wget build-essential python3-pip jq coreutils openssh-server xorriso grep ; do tdnf -y install "$package" --refresh; done

# Install Semver
RUN pip3 install semver jinja2 jinja2-time

# Install Windows Remote Management 
RUN pip3 install pywinrm

# Setup image Builder code
RUN git clone $IMAGE_BUILDER_REPO $IMAGE_BUILDER_REPO_NAME
WORKDIR $IMAGE_BUILDER_REPO_NAME

RUN git checkout $IMAGE_BUILDER_COMMIT_ID

# Install Ansible
RUN pip3 install ansible-core==$ANSIBLE_VERSION
# Set the environment variable where packer will be installed
ENV PATH=${PATH}:/image-builder/images/capi/.local/bin

# Running deps-ova to setup packer, goss provisioner and other ansible galaxy collections
WORKDIR images/capi

# This version of ansible requires locale to be set explicitly.
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

RUN make deps-ova

# Make sure packer and ansible are installed properly
RUN command -v packer
RUN command -v ansible

COPY patches patches
# Copy the image build script
COPY build-ova.sh .
RUN chmod +x build-ova.sh

CMD ["./build-ova.sh"]
