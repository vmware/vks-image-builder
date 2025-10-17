# Copyright 2023 VMware, Inc.
# SPDX-License-Identifier: MPL-2.0

import argparse
import json
import os
import shutil
import semver

import yaml
from jinja2 import Environment, BaseLoader

# Dictionary to store the Jinja Variables that stores data
# about kubernetes version and URLs
jinja_args_map = {}
packer_vars = {}

tkr_api_kind = "TanzuKubernetesRelease"
osimage_api_kind = "OSImage"
cbt_api_kind = "ClusterBootstrapTemplate"
package_api_kind = "Package"

max_k8s_object_name_length = 63
max_tkr_suffix_length = 8


def parse_args():
    parser = argparse.ArgumentParser(
        description='Script to setup the Packer Variables for TKG BYOI')
    sub_parsers = parser.add_subparsers(
        help="Helper functions", dest='subparser_name')
    setup_group = sub_parsers.add_parser('setup')
    setup_group.add_argument('--kubernetes_config', required=True,
                             help='Kubernetes related configuration JSON')
    setup_group.add_argument('--os_type', required=True,
                             help='OS type')
    setup_group.add_argument('--host_ip', required=True,
                             help='Host IP')
    setup_group.add_argument('--artifacts_container_port', required=False,
                             help='Artifacts container port, default value is 8081', default="8081")
    setup_group.add_argument('--packer_http_port', required=False,
                             help='Packer HTTP server port, default value is 8082', default="8082")
    setup_group.add_argument('--default_config_folder', required=True,
                             help='Path to default packer variable configuration folder')
    setup_group.add_argument('--tkr_metadata_folder', required=True,
                             help='Path to TKR metadata')
    setup_group.add_argument('--tkr_suffix', required=False,
                             help='Suffix to be added to the TKR, OVA and OSImage')
    setup_group.add_argument('--dest_config', required=True,
                             help='Path to the final packer destination config file')
    setup_group.add_argument('--ova_destination_folder', required=True,
                             help='Destination folder to copy the OVA after changing the name')
    setup_group.add_argument('--ova_ts_suffix', required=True,
                             help='Suffix to be attached to generate the OVA name')
    setup_group.add_argument('--additional_packer_variables', required=False,
                             default=None,
                             help='Comma separated additional Image Builder overrides as json files. The files should be given as absolute paths')
    setup_group.add_argument('--override_package_repositories', required=False,
                             default=None,
                             help='Comma delimited string containing the names of files to override the image containing repository definitions. The files should be given as absolute paths')

    ova_copy_group = sub_parsers.add_parser("copy_ova")
    ova_copy_group.add_argument('--kubernetes_config', required=True,
                                help='Kubernetes related configuration JSON')
    ova_copy_group.add_argument('--os_type', required=True,
                                help='OS type')
    ova_copy_group.add_argument('--tkr_metadata_folder', required=True,
                                help='Path to TKR metadata')
    ova_copy_group.add_argument('--tkr_suffix', required=False,
                                help='Suffix to be added to the TKR, OVA and OSImage')
    ova_copy_group.add_argument('--ova_destination_folder', required=True,
                                help='Destination folder to copy the OVA after changing the name')
    ova_copy_group.add_argument('--ova_ts_suffix', required=True,
                                help='Suffix to be attached to generate the OVA name')
    args = parser.parse_args()
    return args


def main():
    args = parse_args()
    if args.subparser_name == "setup":
        setup(args)
    elif args.subparser_name == "copy_ova":
        copy_ova(args)


def setup(args):
    """
    Parse and template the Jinja files present in the packer-variables folder.
    """
    global jinja_args_map

    populate_jinja_args(args)

    render_default_config(args)
    json.dump(packer_vars, open(os.path.join(
        args.dest_config, 'packer-variables.json'), 'w'), indent=4)

    update_tkr_metadata(args)


def populate_jinja_args(args):
    """
    Populate the key value pairs for Jinja templates based on the kubernetes configuration
    file downloaded from the artifacts container.
    """
    global jinja_args_map

    jinja_args_map = vars(args)
    kubernetes_args = {}
    with open(args.kubernetes_config, 'r') as fp:
        kubernetes_args = json.loads(fp.read())
    jinja_args_map.update(kubernetes_args)
    jinja_args_map["kubernetes_version"] = jinja_args_map["kubernetes"]
    kubernetes_series = jinja_args_map["kubernetes"].split('+')[0]
    jinja_args_map["kubernetes_series"] = kubernetes_series
    jinja_args_map["sysusr_prefix"] = "/usr"

    if kubernetes_series.startswith("v"):
        # Remove the leading v from version for semver module.
        kubernetes_series = kubernetes_series[1:]

    k8sversion = semver.Version.parse(kubernetes_series)
    # gateway-api package is not present for TKRs upto v1.26.x. gateway_package_present can be used
    # to determine if carvel package of gateway-api should be present depending on TKR version.
    jinja_args_map["gateway_package_present"] = False
    if semver.Version(k8sversion.major, k8sversion.minor, k8sversion.patch).compare("1.27.0") >= 0:
        jinja_args_map["gateway_package_present"] = True
    # Populate the ova_ts_suffix
    jinja_args_map["ova_ts_suffix"] = args.ova_ts_suffix

    # use goss bundled inside artifact server starting v1.31.0
    jinja_args_map["use_artifact_server_goss"] = False
    if semver.Version.parse(kubernetes_series).compare("1.31.0") >= 0:
        jinja_args_map["use_artifact_server_goss"] = True

    # capabilities-package is not present for TKrs starting v1.31.x. capabilities_package_present can be
    # used to determine if carvel package of capabilites should be present depending on the TKr version.
    jinja_args_map["capabilities_package_present"] = True
    # When comparing ignore rc/alpha/beta notations
    if semver.Version(k8sversion.major, k8sversion.minor, k8sversion.patch).compare("1.31.0") >= 0:
        jinja_args_map["capabilities_package_present"] = False

    images_local_host_paths = get_images_local_host_path(args)
    jinja_args_map.update(images_local_host_paths)

    jinja_args_map['registry_store_path'] = get_registry_store_path(args)

    print("Jinja Args:", jinja_args_map)


def get_images_local_host_path(args):
    """
    Get the localhost paths based on the Package objects from the
    TKR metadata that will be used for by imgpkg to upload the
    thick tar files to local docker registry during the image build.
    """
    packages_folder = os.path.join(args.tkr_metadata_folder, "packages")
    localhost_paths = {}
    kapp_key_name = ''
    kapp_file = ''
    for subdir, dirs, files in os.walk(packages_folder):
        for file in files:
            with open(os.path.join(subdir, file), 'r') as fp:
                yaml_doc = yaml.safe_load(fp)
                if yaml_doc["kind"] == package_api_kind:
                    key_name = yaml_doc["spec"]["refName"].split('.')[
                        0].replace('-', '_')
                    if 'kapp' not in key_name:
                        key_name = key_name + '_package_localhost_path'

                        image = yaml_doc["spec"]["template"]["spec"]["fetch"][0]["imgpkgBundle"]["image"]
                        # Split based on the presence of '@' or ':'.
                        if '@' in image:
                            path = ":".join(image.split('@')[:-1])
                        else:
                            path = ":".join(image.split(':')[:-1])
                        localhost_paths[key_name] = path
                        continue
                    kapp_file = os.path.join(subdir, file)
                    kapp_key_name = key_name + '_localhost_path'
    with open(kapp_file, 'r') as fp:
        for line in fp:
            if "image: localhost:5000/tkg/packages/core/kapp-controller" in line:
                path = ':'.join(line.strip().split('@')[0].split(':')[1:]).strip()
                localhost_paths[kapp_key_name] = path
                print(line)
    print("localhost_paths: ", localhost_paths)
    return localhost_paths


def get_registry_store_path(args):
    os_type_parts = args.os_type.split('-')
    os_name = 'linux'
    arch_variants = ['amd64']
    if len(os_type_parts) > 0 and os_type_parts[0].lower() == 'windows':
        os_name = 'windows'
        arch_variants.append(os_type_parts[1])

    return 'registry-%s-%s.tar.gz' % (os_name, '-'.join(arch_variants))


def copy_ova(args):
    """
    Copy the OVA from output folder to destination folder after changing the OVA name.
    """
    default_ova_destination_folder = '/image-builder/images/capi/output/{}-kube-{}-{}/'
    config_folder = os.path.join(args.tkr_metadata_folder, "config")
    new_ova_name = ''
    for filename in os.listdir(config_folder):
        file = os.path.join(config_folder, filename)
        with open(file, 'r') as fp:
            yaml_docs = yaml.safe_load_all(fp)
            for yaml_doc in yaml_docs:
                # When multiple versions of same os is supported (eg: Ubuntu 22 and 24), matching just os_name can return false postive.
                #Example: expected would be to match ubuntu-2204 but if first OSImage file returned is that of ubuntu 24, then it will match ubuntu-2404
                # So matching with version from OSImage (ubuntu versions have a dot in between - 22.04) as well
                if yaml_doc["kind"] == osimage_api_kind and yaml_doc["spec"]["os"]["name"] in args.os_type and yaml_doc["spec"]["os"]["version"].replace('.','') in args.os_type:
                    new_ova_name = "{}.ova".format(
                        yaml_doc["spec"]["image"]["ref"]["name"])
    if not new_ova_name:
        print("Matching OSImage Spec not found in metadata")
        exit(1)

    old_ova_name = ''
    with open(args.kubernetes_config, 'r') as fp:
        kubernetes_args = json.loads(fp.read())
        default_ova_destination_folder = \
            default_ova_destination_folder.format(
                args.os_type, kubernetes_args["kubernetes"].split('+')[0], args.ova_ts_suffix)
        old_ova_name = "{}-{}.ova".format(args.os_type,
                                          kubernetes_args["kubernetes"].replace('+', '---'))

    new_path = os.path.join(args.ova_destination_folder, new_ova_name)
    old_path = os.path.join(default_ova_destination_folder, old_ova_name)
    print("Copying OVA from {} to {}".format(old_path, new_path))
    shutil.copyfile(old_path, new_path)

    # Copy the package list
    old_path = os.path.join(default_ova_destination_folder, "package_list.json")
    new_path = os.path.join(args.ova_destination_folder, "package_list.json")
    print("Copying package list file from {} to {}".format(old_path, new_path))
    shutil.copyfile(old_path, new_path)

    # Copy the kernel config file
    old_path = os.path.join(default_ova_destination_folder, "kernel.config")
    new_path = os.path.join(args.ova_destination_folder, "kernel.config")
    print("Copying kernel config file from {} to {}".format(old_path, new_path))
    shutil.copyfile(old_path, new_path)

    # Copy the OS manifest file
    old_path = os.path.join(default_ova_destination_folder, "os_manifest.json")
    new_path = os.path.join(args.ova_destination_folder, "os_manifest.json")
    print("Copying OS manifest file from {} to {}".format(old_path, new_path))
    shutil.copyfile(old_path, new_path)

    # Copy the Kernel Tunable details
    old_path = os.path.join(default_ova_destination_folder, "kernel_tunables.tgz")
    new_path = os.path.join(args.ova_destination_folder, "kernel_tunables.tgz")
    print("Copying kernel tunables from {} to {}".format(old_path, new_path))
    shutil.copyfile(old_path, new_path)

    # Copy the Source repo details
    old_path = os.path.join(default_ova_destination_folder, "repo_sources.tgz")
    new_path = os.path.join(args.ova_destination_folder, "repo_sources.tgz")
    print("Copying repo source details from {} to {}".format(old_path, new_path))
    shutil.copyfile(old_path, new_path)
        
    print("Copying completed")


def update_tkr_metadata(args):
    """
    Reads the TKR metadata like Addon Config, TKR, CBT and Package objects
    that are downloaded from the artifacts containers and updates the TKR,
    CBT and Addon config objects name based on the <kubernetes_version>-<tkr_suffix>
    """
    config_folder = os.path.join(args.tkr_metadata_folder, "config")
    kubernetes_version = None
    old_tkr_name = None
    tkr_file = None
    cbt_file = None
    osimage_files = []
    addons_files = []
    for filename in os.listdir(config_folder):
        file = os.path.join(config_folder, filename)
        with open(file, 'r') as fp:
            yaml_docs = yaml.safe_load_all(fp)
            for yaml_doc in yaml_docs:
                if yaml_doc["kind"] == tkr_api_kind:
                    # kubernetes version contains + which is not a supported character
                    # so replace + with ---
                    kubernetes_version = yaml_doc["spec"]["kubernetes"]["version"].replace(
                        '+', '---')
                    tkr_file = file
                    old_tkr_name = yaml_doc["metadata"]["name"]
                elif yaml_doc["kind"] == osimage_api_kind:
                    osimage_files.append(file)
                elif yaml_doc["kind"] == cbt_api_kind:
                    cbt_file = file
                else:
                    if file not in addons_files:
                        addons_files.append(file)

    new_osimages = []
    for osimage_file in osimage_files:
        new_osimage_name = ''
        with open(osimage_file, 'r') as fp:
            yaml_doc = yaml.safe_load(fp)
            # Create new OSImage name based on the OS Name, version and architecture.
            new_osimage_name = format_name(args.tkr_suffix,
                                           yaml_doc["spec"]["os"]["name"],
                                           yaml_doc["spec"]["os"]["version"].replace(
                                               '.', ''),
                                           yaml_doc["spec"]["os"]["arch"],
                                           kubernetes_version)
            new_osimages.append({"name": new_osimage_name})
            if yaml_doc["spec"]["os"]["name"].lower() in args.os_type.lower():
                check_ova_file(new_osimage_name, args.ova_destination_folder)
        update_osimage(osimage_file, new_osimage_name)

    new_tkr_name = format_name(args.tkr_suffix, kubernetes_version)
    update_tkr(tkr_file, new_tkr_name, new_osimages)
    update_cbt(cbt_file, new_tkr_name, old_tkr_name, new_tkr_name)

    for addon_file in addons_files:
        update_addon_config(addon_file, old_tkr_name, new_tkr_name)


def check_ova_file(new_osimage_name, ova_destination_folder):
    """
    Verifies if a OVA file with a same TKR version and TKR suffix
    exists in the image artifacts folder.
    """
    for filename in os.listdir(ova_destination_folder):
        if filename == "{}.ova".format(new_osimage_name):
            raise Exception(
                "OVA {}.ova already exists in the OVA folder".format(new_osimage_name))


def update_addon_config(addon_file, old_tkr_name, new_tkr_name):
    """
    Update the Addon Config object name. (For updating the data on CBT refer to update_cbt function)
    """
    addon_data = []
    with open(addon_file, 'r') as os_fp:
        temp_addon_data = yaml.safe_load_all(os_fp)
        for yaml_doc in temp_addon_data:
            old_name = yaml_doc["metadata"]["name"]
            new_name = old_name.replace(old_tkr_name, new_tkr_name)
            yaml_doc["metadata"]["name"] = new_name
            print("{} name changed from {} to {}".format(
                yaml_doc["kind"], old_name, new_name))
            addon_data.append(yaml_doc)

    with open(addon_file, 'w') as os_fp:
        yaml.dump_all(addon_data, os_fp)


def update_osimage(osimage_file, osimage_name):
    """
    Update OSImage object with the new name
    """
    osimage_data = ''
    with open(osimage_file, 'r') as os_fp:
        osimage_data = yaml.safe_load(os_fp)
    osimage_data["metadata"]["name"] = osimage_name
    osimage_data["spec"]["image"]["ref"]["name"] = osimage_name
    print("New OSImage Name for {} is {}".format(
        osimage_data["spec"]["os"]["name"], osimage_name))
    with open(osimage_file, 'w') as os_fp:
        yaml.dump(osimage_data, os_fp)


def update_tkr(tkr_file, tkr_name, osimages):
    """
    Update the TKR object with the new name based on kubernetes and suffix.
    New name format is <kuberneter_version>-<tkr_suffix>
    """
    tkr_data = ''
    with open(tkr_file, 'r') as fp:
        tkr_data = yaml.safe_load(fp)
    tkr_data["metadata"]["name"] = tkr_name
    tkr_data["spec"]["osImages"] = osimages
    tkr_data["spec"]["version"] = tkr_name.replace('---', '+')
    with open(tkr_file, 'w') as fp:
        yaml.dump(tkr_data, fp)
    print("New TKR Name:", tkr_name)


def update_cbt(cbt_file, cbt_name, old_tkr_name, new_tkr_name):
    """
    Updates the CBT with new data like
    - Name of CBT.
    - Updates all the addons object names like calico,antrea,kapp,csi,cpi configs
      from old TKR reference to new TKR name reference.
    - Updates the Package secret names like capabilites, guest cluster auth service
      from old TKR reference to new TKR name reference.
    """
    cbt_data = ''
    with open(cbt_file, 'r') as fp:
        cbt_data = yaml.safe_load(fp)
    cbt_data["metadata"]["name"] = cbt_name
    for addon in ["cni", "cpi", "csi", "kapp"]:
        cbt_data["spec"][addon]["valuesFrom"]["providerRef"]["name"] = \
            cbt_data["spec"][addon]["valuesFrom"]["providerRef"]["name"].replace(
                old_tkr_name, new_tkr_name)
    for index in range(len(cbt_data["spec"]["additionalPackages"])):
        if "valuesFrom" in cbt_data["spec"]["additionalPackages"][index]:
            if "secretRef" in cbt_data["spec"]["additionalPackages"][index]["valuesFrom"]:
                cbt_data["spec"]["additionalPackages"][index]["valuesFrom"]["secretRef"] = \
                    cbt_data["spec"]["additionalPackages"][index]["valuesFrom"]["secretRef"].replace(old_tkr_name,
                                                                                                     new_tkr_name)
    with open(cbt_file, 'w') as fp:
        yaml.dump(cbt_data, fp)
    print("New CBT Name:", cbt_name)


def format_name(suffix, *default_values):
    """
    Creates a kubernetes object name with max name length(63) after
    appending the suffix string.
    """
    default_name = '-'.join(default_values)
    if not suffix:
        return default_name

    max_k8s_object_name_length = 63
    max_tkr_suffix_length = max_k8s_object_name_length - len(default_name) - 1
    if max_tkr_suffix_length > len(suffix):
        max_tkr_suffix_length = len(suffix)
    suffix = suffix[0:max_tkr_suffix_length]
    return '-'.join([default_name, suffix])


def render_additional_packer_variables(additional_packer_variables, os_type):
    """
    Creates a single JSON object after parses all files then
    applies the Jinja2 templating using jinja_args_map dictionary.
    """
    output = {}
    env = Environment(
        extensions=['jinja2_time.TimeExtension'],
        loader=BaseLoader
    )
    if additional_packer_variables is not None:
        additional_packer_var_files = additional_packer_variables.split(",")
        for variable_file in additional_packer_var_files:
            if os.path.exists(variable_file):
                with open(variable_file, 'r') as fp:
                    output.update(json.load(fp))
    
    if os_type.startswith("windows")  and output.get("windows_admin_password") is None:
        windows_admin_password = os.environ.get("WINDOWS_ADMIN_PASSWORD")
        if windows_admin_password is None:
            print("Either set `{}' in packer variables or set '{}' environment variable for OS type '{}'.` ".format("windows_admin_password", "WINDOWS_ADMIN_PASSWORD", os_type))
            exit(1)
        output["windows_admin_password"] = windows_admin_password
    print("Additional Packer Variables: ", json.dumps(output, indent=4))
    return output


def render_folder_and_append(folder, os_type):
    """
    Creates a single JSON object after parses all files on a folder then
    applies the Jinja2 templating using jinja_args_map dictionary.
    """
    output = {}
    env = Environment(
        extensions=['jinja2_time.TimeExtension'],
        loader=BaseLoader
    )
    os_type_tokens = os_type.split('-')
    # First read all direct files under packer-variables.
    # These are the default ones applicable to all.
    # Post that add for platform specific.
    # Non-version OS specific goes in followed by versioned ones.
    # Expectation is that if packer-variables folder has
    # say, 'ubuntu' and 'ubuntu-2204' folder with files,
    # files from 'ubuntu' get loaded first followed by 'ubuntu-2204'.
    # This means that files in version specific folder can override any
    # other declarations.
    for variable_file in os.listdir(folder):
        common_file = os.path.join(folder, variable_file)
        if os.path.isfile(common_file):
            with open(common_file, 'r') as fp:
                temp = env.from_string(fp.read())
                output.update(json.loads(temp.render(jinja_args_map)))

    for i in reversed(range(len(os_type_tokens))):
        platform_directory = os.path.join(
            folder, '-'.join(os_type_tokens[0:len(os_type_tokens) - i]))
        if os.path.isdir(platform_directory):
            for platform_file in os.listdir(platform_directory):
                with open(os.path.join(platform_directory, platform_file)) as fp:
                    temp = env.from_string(fp.read())
                    output.update(json.loads(temp.render(jinja_args_map)))

    return output


def render_default_config(args):
    packer_vars.update(render_folder_and_append(
        args.default_config_folder, args.os_type))
    packer_vars.update(render_extra_repos(args.override_package_repositories))
    packer_vars.update(render_additional_packer_variables(
        args.additional_packer_variables, args.os_type))


def render_extra_repos(comma_sep_repo_list):
    output = {}
    if comma_sep_repo_list is not None:
        extra_repos = ""
        extra_repos_list = comma_sep_repo_list.split(",")
        for repo_file in extra_repos_list:
            # We are not using string join just because we want to make sure repo path exists
            if os.path.exists(repo_file):
                extra_repos = extra_repos + " " + repo_file
        output["extra_repos"] = extra_repos.strip()
        output["remove_extra_repos"] = "true"
    print("Additional inflight package repos: ", json.dumps(output, indent=4))
    return output


if __name__ == "__main__":
    main()
