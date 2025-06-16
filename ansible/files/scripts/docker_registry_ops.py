import argparse
import json
import subprocess

IMAGE_NAME = "docker.io/vmware/docker-registry"
PAUSE_IMAGE_NAME = "localhost:5000/vmware.io/pause"
LABEL = "io.cri-containerd.pinned=pinned"

def get_image_version(image_name):
    cp = subprocess.run(["crictl", "images", "-o", "json"], capture_output=True, text=True)
    cp.check_returncode()
    images = json.loads(cp.stdout)["images"]
    for image in images:
        for repo_tag in image["repoTags"]:
            if repo_tag.startswith(image_name):
                return repo_tag.split(":")[-1]
    else:
        raise Exception(f"No image with name {image_name} found")

def get_registry_version():
    return get_image_version(IMAGE_NAME)

def get_pause_version():
    return get_image_version(PAUSE_IMAGE_NAME)

def apply_label(image):
    subprocess.run(["ctr", "-n", "k8s.io", "images", "label", image, LABEL], check=True)

def pin_image():
    image_name_with_version = IMAGE_NAME + ":" + get_registry_version()
    apply_label(image_name_with_version)

    pause_image_name_with_version = PAUSE_IMAGE_NAME + ":" + get_pause_version()
    apply_label(pause_image_name_with_version)

def main():
    parser = argparse.ArgumentParser(
        description='Script to copy carvel packages')
    parser.add_argument('--version',
                        action='store_true',
                        help='Print version of docker-registry image')
    parser.add_argument('--pin',
                        action='store_true',
                        help='Pin image by applying label io.cri-containerd.pinned=pinned')

    args = parser.parse_args()
    if args.version:
        print(get_registry_version())
    elif args.pin:
        pin_image()


if __name__ == '__main__':
    main()
