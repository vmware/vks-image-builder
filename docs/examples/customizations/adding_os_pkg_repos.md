# Adding new OS packages and configuring the repositories or sources

## Use case

As a user I want to

1. Add new OS packages such as `pkg1` and `pkg2`.
2. Configure sources/repositories to an internal mirror to build the node images in an air-gapped scenario. Configuring new sources/repositories is also useful when we want to install internally built software.

## Customization

Configuration of OS packages and sources/repositories is exposed as packer variables. To view a list of packer variables exposed by [kubernetes image builder][kubernetes-image-builder] please refer to this [page][customizations-doc].

### Adding new packages

To add new packages [kubernetes image builder][kubernetes-image-builder] provides `extra_rpms` and `extra_debs` packer variables for Photon and Ubuntu respectively.

To add new packages to Ubuntu 24.04, add the packages to the packer variables in the [default-args-ubuntu-2404-efi.j2][default-args-ubuntu-2404-efi] file as shown below.

```jinja
    "extra_debs": "existing_packages pkg1 pkg2"
```

To add new packages to Photon 5, add the packages to the packer variables in the [default-args-photon-5.j2][default-args-photon-5] file as shown below.

```jinja
    "extra_rpms": "existing_packages pkg1 pkg2"
```

_**Note**: The location of default configuration specific to OS follows the path nomenclature, `packer-variables/<OS>-<Version>/default-args-<OS>-<version>.j2`. Include `-efi` suffix as well along with the version for Ubuntu._

### Configuring new sources/repositories

[kubernetes image builder][kubernetes-image-builder] provides `extra_repos` packer variables through which sources/repositories can be configured for both Photon and Ubuntu. As there is a difference in how Ubuntu/Photon sources are configured we need to have separate source files for Photon/Ubuntu.

- Create new folder `repos` in [ansible files][ansible-files] folder
- Depending upon the Linux OS flavour, use either of the below steps
  - For **Photon** sources, create a new file called `photon.repo` in the `repos` folder. Refer below for sample content and refer to the official Photon [document][photon-repo-doc] for more information.

  ```text
  [photon]
  name=VMware Photon Linux $releasever ($basearch)
  baseurl=<internal_mirror_url>/$releasever/photon_release_$releasever_$basearch
  gpgkey=<gpg_key>
  gpgcheck=1
  enabled=1

  [photon-updates]
  name=VMware Photon Linux $releasever ($basearch) Updates
  baseurl=<internal_mirror_url>/$releasever/photon_updates_$releasever_$basearch
  gpgkey=<gpg_key>
  gpgcheck=1
  enabled=1

  [photon-extras]
  name=VMware Photon Extras $releasever ($basearch)
  baseurl=<internal_mirror_url>/$releasever/photon_extras_$releasever_$basearch
  gpgkey=<gpg_key>
  gpgcheck=1
  enabled=1
  ```

  - For **Ubuntu** sources, create a new file called `ubuntu.list` in the `repos` folder. Refer to the official ubuntu [documentation][ubuntu-sources-doc] for more information.

```text
deb <internal_source_url> jammy main restricted universe
deb <internal_source_url> jammy-security main restricted
deb <internal_source_url> jammy-updates main restricted
```

- Create a new file `repos.j2` in [packer-variables][packer-variables] folder for configuring the `extra_repos` packer variable folder. (Uses [jinja][jinja] templating)

```jinja
{
    {% if os_type == "photon-5" %}
    "extra_repos": "/image-builder/images/capi/image/ansible/files/repos/photon.repo"
    {% elif os_type == "ubuntu-2404-efi" %}
    "extra_repos": "/image-builder/images/capi/image/ansible/files/repos/ubuntu.list"
    {% endif %}
}
```

### Disabling public repositories/sources

For disabling public repos set the `disable_public_repos` packer variable to `true` in the `repos.j2` file.

### Removing the extra repositories/sources

To remove the extra repositories/sources that were configured during the image build process set the `remove_extra_repos` packer variable to `true`.

```jinja
{
    "disable_public_repos": true,
    "remove_extra_repos": true
    {% if os_type == "photon-5" %}
    "extra_repos": "/image-builder/images/capi/image/ansible/files/repos/photon.repo"
    {% elif os_type == "ubuntu-2404-efi" %}
    "extra_repos": "/image-builder/images/capi/image/ansible/files/repos/ubuntu.sources"
    {% endif %}
}
```

[//]: Links

[ansible-files]: ./../../ansible/files/
[customizations-doc]: https://image-builder.sigs.k8s.io/capi/capi.html#customization
[jinja]: https://jinja.palletsprojects.com/en/3.1.x/
[kubernetes-image-builder]: https://github.com/kubernetes-sigs/image-builder/
[photon-repo-doc]: https://vmware.github.io/photon/assets/files/html/3.0/photon_admin/adding-a-new-repository.html
[ubuntu-sources-doc]: https://manpages.ubuntu.com/manpages/noble/man5/sources.list.5.html#deb822-style%20format
[default-args-ubuntu-2404-efi]: ../../packer-variables/ubuntu-2404-efi/default-args-ubuntu-2404-efi.j2
[default-args-photon-5]: ../../packer-variables/photon-5/default-args-photon-5.j2
[packer-variables]: ./../../packer-variables/
