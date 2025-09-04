# vSphere Kubernetes Service Image Builder

vSphere Kubernetes Service Image Builder provides tooling that can be used to build node images for use with [vSphere Kubernetes Service][vsphere-kubernetes-service-workloads].

## Content

- [Prerequisites](#prerequisites)
- [Building Images](#building-images)
- [Make Targets](#make-targets)
- [Customization Examples](#customizations-examples)
- [Blog](#blog)
- [Debugging](#debugging)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

## Prerequisites

Below are the prerequisites for building the node images

- vSphere Environment version >= 8.0
- DCHP configured for vCenter (required by Packer)
- `jq` version >= `1.6`
- `make` version >= `4.2.1`
- `docker` version >= `20.10.21`
- Linux environment should have the below utilities available on the system
  - [Docker](https://www.docker.com/)
  - [GNU Make](https://www.gnu.org/software/make/)
  - [jq](https://stedolan.github.io/jq/)

## Building Images

![Demo](./docs/files/demo.gif)

- Clone this repository on the linux environment for building the image.
- Update the vSphere environment details like vCenter IP, Username, Password, etc. in [vsphere.j2](packer-variables/vsphere.j2)
  - For details on the permissions required for the user please refer to the packer [vsphere-iso documentation](https://developer.hashicorp.com/packer/plugins/builders/vsphere/vsphere-iso#required-vsphere-privileges).
- To identify the kubernetes version supported by the branch, check the version information provided in [supported version file][supported-version].
- Run the artifacts container using `make run-artifacts-container`.
  - Default port used by the artifacts container is `8081` but this can be configured using the `ARTIFACTS_CONTAINER_PORT` parameter.
- Run the image-builder container to build the node image(use `make build-node-image` target).
  - Default port used the image-builder containter is `8082` but this can be configured using the `PACKER_HTTP_PORT`.
- Once the OVA is generated upload the OVA to a [content library][vm-admin-guide] used by the supervisor.
- To clean the containers and artifacts use the `make clean` target.

## Supported Kubernetes Version

[supported-version.txt](supported-version.txt) holds information about the kubernetes release version supported.

[supported-context.json](supported-context.json) holds information about the context for the supported Kubernetes versions which includes supported OS targets along with the artifacts container image URL. This file will be updated when a new Kubernetes version is supported by the **vSphere Kubernetes Service** team.

## Make targets

### Help

- `make help` Provides help information about different make targets

```bash
make
make help
```

### Clean

There are three different clean targets to clean the containers or artifacts generated during the process or both.

- `make clean-containers` is used to stop/remove the artifacts or image builder or both.
  - During the container creation, All containers related to BYOI will be labelled as `byoi`
    - artifacts container will have `byoi_artifacts` and Kubernetes version as labels.
    - image builder container will have `byoi_image_builder`, Kubernetes version, and os target as labels

```bash
make clean-containers PRINT_HELP=y         # To show the help information for this target
make clean-containers                      # To clean all the artifacts and image-builder containers
make clean-containers LABEL=byoi_artifacts # To remove artifact containers
```

- `make clean-image-artifacts` is used to remove the image artifacts like OVA's and packer log files

```bash
make clean-image-artifacts PRINT_HELP=y                           # To show help information for this target
make clean-image-artifacts IMAGE_ARTIFACTS_PATH=/root/artifacts/  # To clean the image artifacts in a folder
```

- `make clean` is a combination of `clean-containers` and `clean-image-artifacts` that cleans both containers and image artifacts

```bash
make clean PRINT_HELP=y                                                   # To show the help information for this target
make clean IMAGE_ARTIFACTS_PATH=/root/artifacts/                          # To clean image artifacts and containers
make clean IMAGE_ARTIFACTS_PATH=/root/artifacts/ LABEL=byoi_image_builder # To clean image artifacts and image builder containers
```

### Image Building

- `make run-artifacts-container` is used to run the artifacts container for a Kubernetes version at a particular port
  - artifacts image URL will be fetched from the [supported-context.json](supported-context.json).
  - By default artifacts container uses port `8080` by default however this can be configured through the `ARTIFACTS_CONTAINER_PORT` parameter.

```bash
make run-artifacts-container PRINT_HELP=y                                                       # To show the help information for this target
make run-artifacts-container ARTIFACTS_CONTAINER_PORT=9090 # To run 1.22.13 Kubernetes artifacts container on port 9090
```

- `make build-image-builder-container` is used to build the image builder container locally with all the dependencies like `Packer`, `Ansible`, and `OVF Tool`.

```bash
make build-image-builder-container PRINT_HELP=y # To show the help information for this target.
make build-image-builder-container # To create the image builder container.
```

- `make build-node-image` is used to build the vSphere Kubernetes Service compatible node image for a Kubernetes version.
  - Host IP is required to pull the required Carvel Packages during the image build process and the default artifacts container port is 8080 which can be configured through `ARTIFACTS_CONTAINER_PORT`.
  - VKr(vSphere Kubernetes Release) Suffix is used to distinguish images built on the same version for a different purpose. Maximum suffix length can be 8 characters.

```bash
make build-node-image PRINT_HELP=y # To show the help information for this target.
make build-node-image OS_TARGET=photon-5 TKR_SUFFIX=byoi HOST_IP=1.2.3.4 IMAGE_ARTIFACTS_PATH=/Users/image ARTIFACTS_CONTAINER_PORT=9090 # Create photon-5 based Kubernetes node image
```

## Customizations Examples

Sample customization examples can be found [here](docs/examples/README.md).

## Blog

Refer to the blog post [Building Custom Tanzu Kubernetes releases for vSphere with Tanzu](https://williamlam.com/2023/07/building-custom-tanzu-kubernetes-releases-tkr-for-vsphere-with-tanzu.html) for  step-by-step instructions on building a custom Tanzu Kubernetes release for use with TKG on Supervisor.

For Windows support you may refer to [Windows tutorial](docs/windows.md)

## Debugging

- To enable debugging for the [make file scripts](hack/make-helpers/) export `DEBUGGING=true`.
- Debug logs are enabled by default on the image builder container which can be viewed through the `docker logs -f <container_name>` command.
- Packer logs can be found at `<artifacts-folder>/logs/packer-<random_id>.log` which will be helpful when debugging issues.

## Contributing

The vSphere Kubernetes Service Image Builder project team welcomes contributions from the community. Before you start working with VMware Image Builder, please read our [Developer Certificate of Origin][dco]. All contributions to this repository must be signed as described on that page. Your signature certifies that you wrote the patch or have the right to pass it on as an open-source patch. For more detailed information, please refer to [CONTRIBUTING][contributing].

## License

This project is available under the [Mozilla Public License, V2.0][project-license].

## Support

VMware will support issues with the vSphere Kubernetes Service Image Builder, but you are responsible for any issues relating to your image customizations and custom applications. You can open VMware Support cases for VKS clusters built with a custom vSphere Kubernetes release image, however, VMware Support will be limited to best effort only, with VMware Support having full discretion over how much effort to put in to troubleshooting. On opening a case with VMware Support regarding any issue with a cluster built with a custom vSphere Kubernetes release image, VMware Support asks that you provide support staff with the exact changes made to the base image.

[//]: Links

[contributing]: CONTRIBUTING.md
[dco]: https://cla.vmware.com/dco
[project-license]: LICENSE.txt
[vsphere-kubernetes-service-workloads]: https://techdocs.broadcom.com/us/en/vmware-cis/vsphere/vsphere-supervisor/8-0/vsphere-supervisor-services-and-workloads-8-0.html
[supported-version]: ./supported-version.txt
[vm-admin-guide]: https://techdocs.broadcom.com/us/en/vmware-cis/vsphere/vsphere/8-0/vsphere-virtual-machine-administration-guide-8-0.html
