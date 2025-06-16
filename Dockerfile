# Copyright 2023 VMware, Inc.
# SPDX-License-Identifier: MPL-2.0

ARG BASE_IMAGE=library/photon:5.0
FROM ${BASE_IMAGE}

ARG IMAGE_BUILDER_COMMIT_ID=""
ARG ANSIBLE_VERSION=2.15.10
ARG IMAGE_BUILDER_REPO="https://github.com/kubernetes-sigs/image-builder.git"
ARG IMAGE_BUILDER_REPO_NAME=image-builder
ARG PACKER_GITHUB_API_TOKEN=""

ENV PATH=${PATH}:/ovftool
ENV LANG=en_US.UTF-8

SHELL ["/bin/bash", "-c"]

RUN tdnf -y update
RUN tdnf -y upgrade

# Install required packages
RUN for package in unzip git wget build-essential python3-pip jq coreutils openssh-server xorriso; do tdnf -y install "$package"; done

# Install Semver
RUN pip3 install semver jinja2 jinja2-time

# Install Windows Remote Management 
RUN pip3 install pywinrm

# Install ovftool
# TODO: this URL might change or expire so need to look at better way to install it on the container.
RUN wget https://vdc-download.vmware.com/vmwb-repository/dcr-public/2ee5a010-babf-450b-ab53-fb2fa4de79af/2a136212-2f83-4f5d-a419-232f34dc08cf/VMware-ovftool-4.4.3-18663434-lin.x86_64.zip
RUN unzip VMware-ovftool-4.4.3-18663434-lin.x86_64.zip -d /

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

# Make sure packer, ansible and ovftool are installed properly
RUN command -v packer
RUN command -v ansible
RUN command -v ovftool

# Copy the image build script
COPY build-ova.sh .
RUN chmod +x build-ova.sh

CMD ["./build-ova.sh"]
