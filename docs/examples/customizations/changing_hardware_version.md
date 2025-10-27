# Changing the Hardware version

## Use case

As a customer, I want to change the Hardware version of the node image to use the latest hardware functionalities.

## Background

By default, node images use the hardware version(`VMX`) 17 defined in [default-args.j2][default-args](Windows uses hardware version 18 by default defined in [default-args-windows.j2][default-args-windows]). Please refer to the below documents to learn more about the hardware version and its compatibility with the vSphere environment.

- [Hardware Features Available with Virtual Machine Compatibility Settings][vm-admin-guide]
- [ESXi/ESX hosts and compatible virtual machine hardware versions list][kb-vm-hardware-version-list]

## Customization

[Kubernetes Image Builder][kubernetes-image-builder] has a `vmx_version` packer variable through which the hardware version can be configured. Edit the `vmx_version` filed in the [default-args.j2][default-args] present in [packer variables](./../../packer-variables/) folder with the appropriate hardware version and build the image

```text
    "vmx_version": "21",
```

- _**Note**: For Windows, update the `vmx_version` in the [default-args-windows.j2][default-args-windows] file._

[//]: Links

[default-args]: [./../../../packer-variables/default-args.j2]
[kubernetes-image-builder]: https://github.com/kubernetes-sigs/image-builder/
[default-args-windows]: ../../packer-variables/windows/default-args-windows.j2
[vm-admin-guide]: https://techdocs.broadcom.com/us/en/vmware-cis/vsphere/vsphere/8-0/vsphere-virtual-machine-administration-guide-8-0.html
[kb-vm-hardware-version-list]: https://knowledge.broadcom.com/external/article?legacyId=2007240
