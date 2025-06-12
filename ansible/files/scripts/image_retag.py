import argparse
import subprocess
import time
import logging
import re

logging.basicConfig(format='%(message)s', level=logging.DEBUG)


class Retag():
    def __init__(self, k8sSemver, dockerVersion, family, startRegistry=True):
        self.k8sSemver = k8sSemver
        self.k8sSeries = re.match('^([0-9]+\.[0-9]+)', k8sSemver[1:]).groups(1)[0]
        self.dockerVersion = dockerVersion
        logging.info(f"dockerVersion: {dockerVersion}")

        self.ctrPrefix = "ctr -n k8s.io images "
        self.newImagePrefix = ["localhost:5000/vmware.io/"]
        self.target = "ubuntu" if family == "Debian" else "photon"
        self.imageList = self.listImages()
        logging.info(f"Existing images: {self.imageList}")

        if startRegistry:
            self.docker()

        registry = localRegistry(self.dockerVersion)
        if startRegistry:
            registry.start()

        self.k8s()

        if startRegistry:
            registry.stop()

        logging.info("Retagged images list:")
        logging.info(self.listImages())

    # gccp & gcauth are considered specialPrefix
    # ex. `localhost:5000/vmware.io/guest-cluster-cloud-provider:0.1-93-gb26e653`
    # All other images are not
    # ex. `vmware.io/csi-attacher:v3.2.1_vmware.1`
    def getImageInfo(self, imageHint, specialPrefix=False):
        for image in self.imageList:
            if imageHint in image:
                imageVersion = image.split(':')[-1]
                if specialPrefix:
                    imagePrefix = ":".join(image.split(':')[0:-1])
                else:
                    imagePrefix = image.split(':')[0]
                logging.info(f"ImageInfo: {image}, {imagePrefix}, {imageVersion}")
                return image, imagePrefix, imageVersion

        logging.info(f"No image found for {imageHint}")

    def listImages(self):
        cmd = f"{self.ctrPrefix} ls -q"
        output = subprocess.run(cmd, check=True, shell=True, capture_output=True)
        imageList = output.stdout.decode().split()
        return imageList

    def retagAndPush(self, oldTag, newTag, push=True):
        retag = f"{self.ctrPrefix} tag --force {oldTag} {newTag}"
        subprocess.run(retag, check=True, shell=True)
        logging.info(f"Retagged {oldTag} -> {newTag}")

        if push:
            pushCmd = f"{self.ctrPrefix} push --plain-http {newTag} {oldTag}"
            subprocess.run(pushCmd, check=True, shell=True)
            logging.info(f"Pushed {newTag}")

    def removeImage(self, oldTag):
        cmd = f"{self.ctrPrefix} rm {oldTag}"
        subprocess.run(cmd, check=True, shell=True)
        logging.info(f"Removed {oldTag}")

    def docker(self):
        dockerImages = [f"docker.io/vmware/docker-registry:{self.dockerVersion}"]

        for image in dockerImages:
            oldImage, oldPrefix, imageVersion = self.getImageInfo(image)
            newTag = f'{oldPrefix}:{self.dockerVersion}'
            self.retagAndPush(oldImage, newTag, push=False)
            self.removeImage(oldImage)

    def k8s(self):
        k8sImages = [
            "coredns", "etcd", "kube-apiserver", "pause",
            "kube-controller-manager", "kube-proxy", "kube-scheduler"
        ]

        for image in k8sImages:
            for prefix in self.newImagePrefix:
                oldImage, oldPrefix, imageVersion = self.getImageInfo(image)
                newTag = f'{prefix}{"/".join(oldPrefix.split("/")[2:])}:{imageVersion}'
                self.retagAndPush(oldImage, newTag)
            self.removeImage(oldImage)


class localRegistry():
    def __init__(self, dockerVersion):
        self.dockerVersion = dockerVersion
        self.ctrPrefix = "ctr -n k8s.io "
        self.ctrRunOptions = "run -d --null-io --net-host "

        self.registryImage = f"docker.io/vmware/docker-registry:{self.dockerVersion}"

        self.imageName = "docker-registry"
        self.mountSrc = "/storage/container-registry"
        self.mountDst = "/var/lib/registry"
        self.mountOptions = "rbind:rw"
        self.imageCmd = "/bin/registry serve /etc/docker/registry/config.yaml"

    def start(self):
        cmd = f"{self.ctrPrefix} {self.ctrRunOptions} " \
              f"--mount type=bind,src={self.mountSrc},dst={self.mountDst},options={self.mountOptions} " \
              f"{self.registryImage} {self.imageName} " \
              f"{self.imageCmd}"
        subprocess.run(cmd, check=True, shell=True)
        logging.info(f"Docker registry started with {self.registryImage}")

    def stop(self):
        taskKill = f"{self.ctrPrefix} task kill {self.imageName}"
        rmContainer = f"{self.ctrPrefix} containers rm {self.imageName}"

        subprocess.run(taskKill, check=True, shell=True)
        time.sleep(3)
        subprocess.run(rmContainer, check=False, shell=True)
        logging.info("Docker registry stopped")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--k8sSemver')
    parser.add_argument('--dockerVersion')
    parser.add_argument('--family')
    parser.add_argument('--startRegistry')
    args = parser.parse_args()

    start_registry = args.startRegistry.lower() in ("yes", "true", "t", "1")
    Retag(args.k8sSemver, args.dockerVersion, args.family, start_registry)


if __name__ == "__main__":
    main()
