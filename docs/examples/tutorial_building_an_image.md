# Tutorial for Using the vSphere Kubernetes Service Image Builder

This tutorial describes how to use the vSphere Kubernetes Service Image Builder to build a custom VKr for use on Supervisor in the vSphere.

The vSphere Kubernetes Service Image Builder uses Hashicorp Packer to generate images. Packer invokes vCenter APIs to create a VM from a VKr.

## Requirements

- vCenter Server 8, which can be any vCenter 8 instance, it does not have to be the same vCenter managing your vSphere
- Packer requires the vSphere environment to have DHCP configured; you cannot use static IP address management
- Tutorial uses Ubuntu 24.04 based Linux VM to generate the image

## Clone the Repository

Clone the vSphere Kubernetes Service Image Builder repository on the Linux VM where you are building the image.

```bash
git clone https://github.com/vmware-tanzu/vsphere-tanzu-kubernetes-grid-image-builder.git
```

## Install Docker

The vSphere Kubernetes Service Image Builder runs components as Docker images to generate VMs.

Refer to the [Docker installation guide][docker-installation] for setting up Docker Engine.

## Install JQ

Install:

```bash
sudo apt install -y jq
```

Verify:

```bash
jq --version
```

## Install Make

Install:

```bash
sudo apt install make
```

Verify:

```bash
make --version
```

## Update vsphere.j2 with vSphere Environment Details

The `vsphere.j2` file is a packer configuration file with vSphere environment details.

CD to the `vsphere-tanzu-kubernetes-grid-image-builder/packer-variables/` directory.

Update the vsphere.j2 environment variables with details for your vCenter 8 instance.

```bash
vi vsphere.j2
```

For example:

```bash
{
    {# vCenter server IP or FQDN #}
    "vcenter_server":"192.2.2.2",
    {# vCenter username #}
    "username":"user@vsphere.local",
    {# vCenter user password #}
    "password":"ADMIN-PASSWORD",
    {# Datacenter name where packer creates the VM for customization #}
    "datacenter":"Datacenter",
    {# Datastore name for the VM #}
    "datastore":"datastore22",
    {# [Optional] Folder name #}
    "folder":"",
    {# Cluster name where packer creates the VM for customization #}
    "cluster": "Management-Cluster",
    {# Packer VM network #}
    "network": "PG-MGMT-VLAN-1050",
    {# To use insecure connection with vCenter  #}
    "insecure_connection": "true",
    {# TO create a clone of the Packer VM after customization#}
    "linked_clone": "true",
    {# To create a snapshot of the Packer VM after customization #}
    "create_snapshot": "true",
    {# To destroy Packer VM after Image Build is completed #}
    "destroy": "true"
}
```

## Identify the Kubernetes version

To identify the version of Kubernetes Release supported by the current branch, refer the [supported-version.txt](../../supported-version.txt)

Usage:

```bash
cat supported-version.txt
```

## Run the Artifacts Server Container for the Selected Kubernetes Version

Running the `run-artifacts-container` Makefile target, will pull the Artifacts Server container image corresponding to the selected Kubernetes Release.

Usage:

```bash
make run-artifacts-container
```

## Run the Image Builder Application

Usage:

```bash
make build-node-image OS_TARGET=<os_target> TKR_SUFFIX=<tkr_suffix> HOST_IP=<host_ip> IMAGE_ARTIFACTS_PATH=<image_artifacts_path> ARTIFACTS_CONTAINER_PORT=8081
```

NOTE: The HOST_IP must be reachable from the vCenter.

Example:

```bash
make build-node-image OS_TARGET=ubuntu-2404-efi TKR_SUFFIX=byoi HOST_IP=192.2.2.3 IMAGE_ARTIFACTS_PATH=/home/ubuntu/image ARTIFACTS_CONTAINER_PORT=8081
```

## Verify the Custom Image

Locally the image is stored in the `/image/ovas` directory. For example, `/home/ubuntu/image/ovas`.

The `/image/logs` directory contains the `packer-xxxx.log` file that you can use to troubleshoot image building errors.

To verify that image is built successfully, check vCenter Server.

You should see the image being built in the datacenter, cluster, folder that you specified in the vsphere.j2 file.

## Customize the image

Refer to the [customization examples][customizations].

## Upload the Image to generate custom Kubernetes Release

Download the custom image from local storage or from the vCenter Server.

In your vSphere environment, create a local content library and upload the custom image there.

Refer to the documentation for [creating a local content library][create-local-content-library] for use with Supervisor.

To use the custom TKR, configure the vSphere Namespace to use the local content library.

[//]: Links
[docker-installation]: https://docs.docker.com/engine/install/
[create-local-content-library]: https://techdocs.broadcom.com/us/en/vmware-cis/vsphere/vsphere-supervisor/8-0/using-tkg-service-with-vsphere-supervisor.html
[customizations]: ./customizations/README.md
