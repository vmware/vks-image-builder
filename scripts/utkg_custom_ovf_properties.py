#!/usr/bin/env python3

# © Broadcom. All Rights Reserved.
# The term “Broadcom” refers to Broadcom Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MPL-2.0

import argparse
import base64
import json
import re
import string
from pathlib import Path
from xml.dom.minidom import Text
from os.path import join
import os
import io
import gzip
import yaml

custom_ovf_properties = {}
version_maps = {}
componentList = ""
config_data_list = {}
tkg_core_directory = "/image-builder/images/capi/tkr-metadata"
config_directory = join(tkg_core_directory, 'config')
packages_directory = join(tkg_core_directory, 'packages')
localhost_path = 'localhost:5000'


def set_versions(args):
    global version_maps

    kubernetes_config = {}
    with open(args.kubernetes_config, 'r') as fp:
        kubernetes_config = json.loads(fp.read())

    version_maps = {
        "image": kubernetes_config["image_version"],
        "k8s": kubernetes_config["kubernetes"],
        "cloudInit": "22.4.2",
        "coredns": kubernetes_config["coredns"],
        "etcd": kubernetes_config["etcd"],
    }


def substitute_data(value, tkr_version):
    subMap = {
        'IMAGE_VERSION': version_maps['image'],
        'CLOUD_INIT_VERSION': version_maps['cloudInit'],
        'ETCD_VERSION': version_maps['etcd'].replace("+", "_"),
        'COREDNS_VERSION': version_maps['coredns'].replace("+", "_"),
        'KUBERNETES_VERSION': version_maps['k8s'],
        'COMPATIBILITY_7_0_0_10100': 'true',
        'COMPATIBILITY_7_0_0_10200': 'true',
        'COMPATIBILITY_7_0_0_10300': 'true',
        'COMPATIBILITY_VC_7_0_0_1_MP3': 'true',
        'DIST_VERSION': tkr_version
    }
    value = string.Template(value).substitute(subMap)
    value = json.dumps(json.loads(value))
    return value


def fetch_addon_packages():
    addon_packages = []

    for root, subdirectories, _ in os.walk(packages_directory):
        for subdirectory in subdirectories:
            addon_packages.append(join(packages_directory, subdirectory))

    return addon_packages


def downloadUtkgAddonFiles():
    addon_packages = fetch_addon_packages()
    return addon_packages


def convert_to_xml(data):
    t = Text()
    t.data = data
    return t.toxml()


def create_non_addon_ovf_properties():
    tkr_version, _ = fetch_tkr_data()
    filenames = ["/image-builder/images/capi/vmware-system.guest.kubernetes.distribution.image.version.json",
                 "/image-builder/images/capi/vmware-system.compatibilityoffering.json"]

    for file in filenames:
        with open(file) as f:
            data = json.dumps(json.load(f))
            data = substitute_data(data, tkr_version)
            key = Path(file).stem
            custom_ovf_properties[key] = convert_to_xml(data)

def create_non_addon_VKr_constraints_ovf_properties():
    filenames = [ join(tkg_core_directory,"vmware-system.kr.destination-semver-constraint.json"),
                  join(tkg_core_directory,"vmware-system.kr.override-k8s-semver-version.json")]
    for file in filenames:
        try:
            with open(file) as f:
                data = json.dumps(json.load(f)).replace('"','')
                key = Path(file).stem
                custom_ovf_properties[key] = convert_to_xml(compress_and_base64_encode(data))
        except IOError:
            print("couldn't find/read file: ",file)
    #  special case to add static resources to ovf properties
    static_resources_file = join(tkg_core_directory,"static-resources","vmware-system.kr.addon.staticresources.yaml")
    try:
        with open(static_resources_file, 'r') as file:
            tkr_version, _ = fetch_tkr_data()
            documents = list(yaml.safe_load_all(file))
            data = yaml.dump_all(documents,sort_keys=False)
            inner_data = set_inner_data(data, "staticresources", tkr_version)
            key = Path(static_resources_file).stem
            custom_ovf_properties[key] = inner_data
    except IOError:
        print("couldn't find/read static-resources file: ",static_resources_file)


# fetch tkr apiversion and tkr version
def fetch_tkr_data():
    tkr_filename = "TanzuKubernetesRelease.yml"
    with open(join(config_directory, tkr_filename), 'r') as file:
        info = yaml.safe_load(file)
        tkr_version = info["spec"]["version"]
        api_version = info["apiVersion"]
        file.close()
    return tkr_version, api_version


def fetch_addon_image_name(info, image_repo, tkg_core_package, package_name):
    image_path = ""
    addon_name = package_name.split(".")[0]
    # for "capabilities" addon, component is named as capabilities-package
    if "capabilities" in package_name:
        addon_name = addon_name + "-package"

    # Fetch kapp-controller container image instead of bundle
    if "kapp-controller" in package_name:
        package_name = "kappControllerImage"

    if package_name in tkg_core_package:
        image_path = image_repo + "/" + tkg_core_package[package_name]['imagePath'] + ':' + \
                     tkg_core_package[package_name]['tag']
    elif addon_name in info['components']:
        # if package is not present in tkg_core_packages,
        # check in components
        image_info = info['components'][addon_name][0]['images'][package_name]
        image_path = image_repo + "/" + image_info['imagePath'] + ':' + image_info['tag']
    else:
        raise Exception("Could not find package")

    return image_path


# As kapp-controller is inline package, container image
# needs to pull instead of package bundle and pushed to the
# same inline repo path
def fetch_kapp_controller_localhost_image(addon_package):
    data, info = fetch_file_contents(addon_package)
    images_yaml_string = info['spec']['template']['spec']['fetch'][0]['inline']['paths']['.imgpkg/images.yml']
    images_yaml = yaml.safe_load(images_yaml_string)
    localhost_path = images_yaml['images'][0]['image']

    return localhost_path.split('@')[0]


# fetch images path from the package CR
def fetch_image_path():
    _, repo_url = fetch_tkr_data()
    image_repo = ""
    image_path_list = []
    localhost_image_path_list = []
    addon_packages = fetch_addon_packages()

    with open("/image-builder/images/capi/tkr-bom.yaml", 'r') as file:
        info = yaml.safe_load(file)
        image_repo = info['imageConfig']['imageRepository']
        tkg_core_package = info['components']['tkg-core-packages'][0]['images']

    for addon_package in addon_packages:
        package_name = addon_package.split("/")[-1]
        image_path = fetch_addon_image_name(info, image_repo, tkg_core_package, package_name)
        image_path_list.append(image_path)
        if "kapp-controller" in addon_package:
            localhost_image = fetch_kapp_controller_localhost_image(addon_package)
            localhost_image_path_list.append(localhost_image)
            continue
        localhost_image = image_path.replace(image_path.split('/')[0], localhost_path)
        localhost_image_path_list.append(":".join(localhost_image.split(":")[:-1]))

    return image_path_list, localhost_image_path_list


# parse the data from package and packageMetadata CR for each addon
def fetch_file_contents(addon_package):
    data = ""
    info = {}
    for filename in os.listdir(addon_package):
        with open(join(addon_package, filename), 'r') as file:
            content = file.read()
            if not content.endswith("\n"):
                content += "\n"
            data = data + "---\n" + content

            if "metadata" not in filename:
                info = yaml.safe_load(content)

    return data, info


# parse the data from config CR for each addon
def append_addon_config(data, addon_package):
    if addon_package in config_data_list:
        filename = config_data_list[addon_package]
        config_data_list.pop(addon_package)
        with open(filename, 'r') as file:
            content = file.read()
            if not content.endswith("\n"):
                content += "\n"
            data = data + "---\n" + content

    return data


# validate if the key length is less than 62, DO NOT CHANGE THIS LIMIT
# as this limitation comes from VirtualMachine Image name
def validate_addon_key_length(key):
    if len(key) > 62:
        raise Exception("key length is too long, hence skipping", key)
    return True


# compress the addon value yamls and encode to base64
def compress_and_base64_encode(text):
    data = bytes(text, 'utf-8')
    with io.BytesIO() as buff:
        g = gzip.GzipFile(fileobj=buff, mode='wb')
        g.write(data)
        g.close()

        return str(base64.b64encode(buff.getvalue()), 'utf-8')


def set_inner_data(data, name, version):
    inner_data = {}

    encoded_data = compress_and_base64_encode(data)
    inner_data["name"] = name
    inner_data["type"] = "inline"
    inner_data["version"] = version
    inner_data["value"] = encoded_data
    inner_data = convert_to_xml(json.dumps(inner_data))

    return inner_data


def create_utkg_tkr_metadata_ovf_properties():
    addon_packages = downloadUtkgAddonFiles()

    # map config CR with corresponding Addon Package
    for filename in os.listdir(config_directory):
        is_addon = False
        for addon_package in addon_packages:
            addon_name = re.sub('[^A-Za-z0-9]+', '', Path(addon_package).stem.split(".")[0])
            if "pv-csi" in addon_package:
                addon_name = "csi"

            if addon_name in filename.lower():
                config_data_list[addon_package] = join(config_directory, filename)
                is_addon = True
                break
        if not is_addon:
            config_data_list[filename] = join(config_directory, filename)

    # fetch TKR version
    tkr_version, _ = fetch_tkr_data()

    # add the custom_ovf_property for given list of addons
    for addon_package in addon_packages:
        data, info = fetch_file_contents(addon_package)
        data = append_addon_config(data, addon_package)
        add_on_version = info["spec"]["version"]

        addon_name = Path(addon_package).stem.split(".")[0]
        inner_data = set_inner_data(data, addon_name, add_on_version)

        # Renaming the guest-cluster-auth-service to gc-auth-service as the name of the add on becomes
        # more than 63 chars which is not permissible for VirtualMachineImage Name
        if addon_name == "guest-cluster-auth-service":
            addon_name = "gc-auth-service"

        if validate_addon_key_length("vmware-system.guest.kubernetes.addons." + addon_name):
            custom_ovf_properties[f"vmware-system.guest.kubernetes.addons.{addon_name}"] = inner_data

    # add OSImage, ClusterBootstrapTemplate and TanzuKubernetesRelease
    osi_images_list = []
    isOsimage = False

    for filename in config_data_list.values():
        data = ""

        with open(filename, 'r') as file:
            content = file.read()
            if not content.endswith("\n"):
                content += "\n"
            data = data + "---\n" + content

            info = yaml.safe_load(content)
            if "OSImage" in filename:
                osi_content = {}
                osi_content["name"] = info["metadata"]["name"]
                osi_content["value"] = compress_and_base64_encode(data)
                osi_images_list.append(osi_content)
                isOsimage = True
                continue

            else:
                metadata_version = tkr_version
                if "ClusterBootstrapTemplate" in filename:
                    split_version = info["metadata"]["name"]
                    # Fetching the short version in order to maintain the max key limit(63 characters) in the ovf
                    # property
                    metadata_name = "tkr.cbt"
                else:
                    metadata_name = "tkr"

        inner_data = set_inner_data(data, info["metadata"]["name"], metadata_version)

        if validate_addon_key_length("vmware-system." + metadata_name):
            custom_ovf_properties[f"vmware-system.{metadata_name}"] = inner_data

    if isOsimage:
        custom_ovf_properties[f"vmware-system.tkr.osi"] = convert_to_xml(json.dumps(osi_images_list))


def write_properties_to_file(filename):
    with open(filename, 'w') as f:
        f.write(json.dumps(custom_ovf_properties))


def main():
    parser = argparse.ArgumentParser(
        description='Script to generate OVF properties')
    parser.add_argument('--kubernetes_config', required=True,
                        help='Kubernetes related configuration JSON')
    parser.add_argument('--outfile',
                        help='Path to output file')
    args = parser.parse_args()

    set_versions(args)
    create_utkg_tkr_metadata_ovf_properties()
    create_non_addon_ovf_properties()
    create_non_addon_VKr_constraints_ovf_properties()
    write_properties_to_file(args.outfile)
    print(custom_ovf_properties)


if __name__ == '__main__':
    main()
