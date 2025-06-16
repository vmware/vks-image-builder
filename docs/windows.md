# Building Windows Image Using the vSphere Kubernetes Service Image Builder

This tutorial describes how to use the vSphere Kubernetes Service Image Builder to build Windows OVA image for use with [vSphere Kubernetes Service 3.3][vsphere-kubernetes-service-release-notes] and above. Windows container workload support is only available in Kubernetes release v1.31 and above.

## Use case

I want to build a Windows Node Image to deploy a node pool for Windows container workloads in my guest cluster.

## Requirements

- Check the [prerequisites][prerequisites]
- vCenter Server 8, which can be any vCenter 8 instance, it does not have to be the same vCenter managing your vSphere Kubernetes Service environment
- Packer requires the vSphere environment to have DHCP configured; you cannot use static IP address management
- A recent Windows Server 22H2 ISO image. Download through your Microsoft Developer Network (MSDN) or Volume Licensing (VL) account. The use of evaluation media is not supported or recommended.
- VMware Tools ISO Image
- A datastore on your vCenter that can accommodate your custom Windows VM template, which can have a starting size greater than 10GB (thin provisioned).

## Prepare for Image Builder

Follow the [standard tutorial][tutorials-base] to prepare the environment for vSphere Kubernetes Service Image Builder.

## Get Windows Server and VMware Tools ISO

Windows Server 22H2 ISO image can be downloaded from Microsoft through your Microsoft Developer Network (MSDN) or Volume Licensing (VL) account.

VMware Tools can be downloaded via the [Broadcom Knowledge Base][broadcom-kb].

In this tutorial, we use Windows Server 22H2 `en-us_windows_server_2022_x64_dvd_620d7eac.iso` and `VMware-tools-windows-12.5.0-23800621.iso`.

### Install govc (Optional)

You may follow the [govc documentation][govc-doc] to install govc on the Linux VM you're building the image.

You may use the below example bash commands to upload Windows Server 22H2 ISO and the VMware Tools Windows ISO to your vCenter instance.

```bash
export GOVC_URL=[VC_URL]
export GOVC_USERNAME=[VC_USERNAME]
export GOVC_PASSWORD=[VC_PASSWORD]
export GOVC_INSECURE=1
export GOVC_DATACENTER=Datacenter
export GOVC_CLUSTER=Management-Cluster
export GOVC_DATASTORE=datastore22

govc datastore.upload --ds="$GOVC_DATASTORE" --dc="$GOVC_DATACENTER" en-us_windows_server_2022_x64_dvd_620d7eac.iso windows2022.iso
govc datastore.upload --ds="$GOVC_DATASTORE" --dc="$GOVC_DATACENTER" VMware-tools-windows-12.5.0-23800621.iso vmtools.iso
```

Alternatively, you may use the vCenter UI to upload the ISOs to the datastore.

## Prepare Windows setup answer file

You may customize the Windows Node Image with a [Windows setup answer file][windows-setup-ans-file]

The upstream Windows setup answer file can be found at [Image Builder][ib-windows-unattended-xml].

### Provision Administrative Account for Log Collection

In order for the Windows nodes to work with the [vSphere Kubernetes Service support bundle tool][gather-logs], you need to add an administrative account in the answer file.

The following snippet shows how to add an administrative account in the answer file.

```bash
curl https://raw.githubusercontent.com/kubernetes-sigs/image-builder/refs/heads/main/images/capi/packer/ova/windows/windows-2022-efi/autounattend.xml -o /home/image-builder/windows_autounattend.xml
vi /home/image-builder/windows_autounattend.xml
```

Locate the `LocalAccounts` in the xml and add a new `LocalAccount` to this section.

```xml
<LocalAccounts>
    <LocalAccount wcm:action="add">
        <Description>Administrator</Description>
        <DisplayName>Administrator</DisplayName>
        <Group>Administrators</Group>
        <Name>Administrator</Name>
    </LocalAccount>
    <LocalAccount wcm:action="add">
        <Password>
            <Value>MyAdminPassw0rd</Value>
            <PlainText>true</PlainText>
        </Password>
        <Description>For log collection</Description>
        <DisplayName>Admin Account</DisplayName>
        <Name>WindowsAdmin</Name>
        <Group>Administrators</Group>
    </LocalAccount>
</LocalAccounts>
```

You should alter the user name and password to comform to organizational policies.

## Update vsphere.j2 with vSphere Environment Details

The `vsphere.j2` file is a packer configuration file with vSphere environment details.

CD to the `vsphere-tanzu-kubernetes-grid-image-builder/packer-variables/` directory.

Update the `vsphere.j2` and `packer-variables/windows/vsphere-windows.j2` environment variables with details for your vCenter 8 instance.

```bash
$ vi vsphere.j2

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

```bash
vi packer-variables/windows/vsphere-windows.j2

{
    "os_iso_path": "[datastore22] windows2022.iso",
    "vmtools_iso_path": "[datastore22] vmtools.iso"
}
```

NOTE: You need to match the ISO image file names in the datastore.

## Run the Artifacts Container for the Selected Kubernetes Version

Usage:

```bash
make run-artifacts-container
```

## Run the Image Builder Application

Usage:

```bash
make build-node-image OS_TARGET=<os_target> TKR_SUFFIX=<tkr_suffix> HOST_IP=<host_ip> IMAGE_ARTIFACTS_PATH=<image_artifacts_path> ARTIFACTS_CONTAINER_PORT=8081
```

NOTE:

- The HOST_IP must be reachable from the vCenter.

- You may list the Kubernetes in your Supervisor cluster to get the version suffix.

```bash
$ kubectl get kr

NAME                                                                    VERSION                       READY   COMPATIBLE   CREATED   TYPE
kubernetesrelease.kubernetes.vmware.com/v1.32.0---vmware.6-fips-vkr.2   v1.32.0+vmware.6-fips-vkr.2   True    True         3h8m
```

Example:

```bash
make build-node-image OS_TARGET=windows-2022-efi TKR_SUFFIX=vkr.4 HOST_IP=192.2.2.3 IMAGE_ARTIFACTS_PATH=/home/image-builder/image ARTIFACTS_CONTAINER_PORT=8081 AUTO_UNATTEND_ANSWER_FILE_PATH=/home/image-builder/windows_autounattend.xml
```

## Verify the Custom Image

Locally the image is stored in the `/image/ovas` directory. For example, `/home/image-builder/image/ovas`.

The `/image/logs` directory contains the `packer-xxxx.log` file that you can use to troubleshoot image building errors.

To verify that image is built successfully, check vCenter Server.

You should see the image being built in the datacenter, cluster, folder that you specified in the vsphere.j2 file.

## Upload the Image to the vSphere Kubernetes Service Environment

Download the custom image from local storage or from the vCenter Server.

In your vSphere Kubernetes Service environment, create a local content library and upload the custom image there.

Refer to the documentation for [creating a local content library][vsphere-service-with-supervisor] for use with vSphere Kubernetes Service.

You need to upload both Linux and Windows node images to the local content library as the Linux node image will be
used to deploy VMs for Kubernetes Control Plane and Linux node pools (if any).

Note: You should disable Security Policy for this content library for Windows image.

## Create a cluster with Windows Node Pool

You may refer to [vSphere Kubernetes Service 3.3 documentation][vsphere-kubernetes-service-release-notes] for more information on how to deploy a cluster with Windows Node Pool with vSphere Kubernetes Service 3.3 and above.

## Known Issues for Windows Container Workload Support

### Kubernetes Release v1.32

- The minimum vmclass should be best-effort-large for Windows Worker Node

  When a windows worker node is configured with a vm-class which has resource configuration lower than best-effort-large, some of the management pods may not run due to loss of network connectivity.

  Resolution:
  Switch to a vmclass configured with more resources.

- After a node reboot, stateful windows Application pods can be in failed (Unknown) state.

  Symptoms: The windows stateful pod description shows failed mount with error as following:

  ```bash
  Warning FailedMount 23m kubelet MountVolume.MountDevice failed for volume "pvc-63a2bde4-8183-40ac-b115-247ae64b6cb4" : rpc error: code = Internal desc = error mounting volume. Parameters: {7e1b7769-d86d-4b8a-b9a6-a1a303021b43-63a2bde4-8183-40ac-b115-247ae64b6cb4 ntfs
  ```

  Relevant log’s location: logs of vsphere-csi-node `kubectl logs $pod_name` or `kubectl describe` the application pod it self.

  Workaround: After restart if pod is in unknown state, follow these steps:

  1. cordon the node with command kubectl cordon <\<*node*\>>

  2. delete the pod, let pod schedule on other node and wait until pod is running

  3. uncordon node with cmd : kubectl uncordon <\<*node*\>>

- Upgrade of some linux pods will not complete when using 1 control plane (linux) and 1 worker node (windows) configuration.

  Reason: Some of the linux pods are configured to use system resources like nodePort and are also configured with node affinity to linux nodes and upgrade strategy of rolling upgrades. When there is a single linux node in the cluster and pods are being upgraded, the previous version pod will bind to system resources like nodePort, which will block the scheduling and starting of the new version.

  Symptom: The pod will be stuck in pending state with error message similar to the following:

  ```bash
  Warning FailedScheduling 3m5s (x38 over 3h9m) default-scheduler 0/2 nodes are available: 1 node(s) didn't have free ports for the requested pod ports, 1 node(s) had untolerated taint {os: windows}. preemption: 0/2 nodes are available: 1 Preemption is not helpful for scheduling, 1 node(s) didn't have free ports for the requested pod ports.
  ```

  Workaround: Configure with additional control plane nodes or with another node pool that has linux nodes.

### Generic Known Issues

You may refer to [this link][supervisor-8-release-notes] for generic known issues for vSphere Kubernetes Service.

[//]: Links

[vsphere-kubernetes-service-release-notes]: https://techdocs.broadcom.com/us/en/vmware-cis/vsphere/vsphere-supervisor/8-0/release-notes/vmware-tanzu-kubernetes-grid-service-release-notes.html
[prerequisites]: https://techdocs.broadcom.com/us/en/vmware-cis/vsphere/vsphere-supervisor/8-0/installing-and-configuring-vsphere-supervisor.html
[tutorials-base]: examples/tutorial_building_an_image.md
[broadcom-kb]: https://knowledge.broadcom.com/external/article/315363/how-to-install-vmware-tools.html
[govc-doc]: https://github.com/vmware/govmomi/blob/main/govc/README.md
[windows-setup-ans-file]: https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/update-windows-settings-and-scripts-create-your-own-answer-file-sxs?view=windows-11
[ib-windows-unattended-xml]: https://raw.githubusercontent.com/kubernetes-sigs/image-builder/refs/heads/main/images/capi/packer/ova/windows/windows-2022-efi/autounattend.xml
[gather-logs]: https://knowledge.broadcom.com/external/article/345464/gathering-logs-for-vsphere-with-tanzu.html
[vsphere-service-with-supervisor]: https://techdocs.broadcom.com/us/en/vmware-cis/vsphere/vsphere-supervisor/8-0/using-tkg-service-with-vsphere-supervisor.html
[supervisor-8-release-notes]:https://techdocs.broadcom.com/us/en/vmware-cis/vsphere/vsphere-supervisor/8-0/release-notes/vmware-tkrs-release-notes.html
