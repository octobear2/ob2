import docker
from docker.utils import create_host_config
from docker.utils.types import Ulimit
from requests.exceptions import ConnectionError, ReadTimeout

import ob2.config as config


class DockerClient(object):
    def __init__(self, sock="unix://var/run/docker.sock"):
        self.client = docker.Client(base_url=sock, version="auto")

    def clean(self):
        containers = self.client.containers(quiet=True, all=True)
        for container in containers:
            self.client.remove_container(container=container, v=True, force=True)
        dangling_images = self.client.images(quiet=True, filters={"dangling": True})
        for image in dangling_images:
            self.client.remove_image(image=image, force=True)

    def start(self, image, mem_limit="1024m", memswap_limit="1024m", labels=[], volumes={},
              max_procs=256, max_files=256):
        """
        Starts a new container and returns the container ID for use.

        image      -- The docker image to use as a base
        mem_limit  -- The memory limit
        labels     -- A list of strings to label this container.
        volumes    -- A dictionary of {local_path: remote_path} of mounts to install on the
                      container.
        max_procs  -- The ulimit nproc
        max_files  -- The ulimit nofile

        """
        host_config = {"mem_limit": mem_limit,
                       "memswap_limit": memswap_limit,
                       "network_mode": "none",
                       "ulimits": [Ulimit(name="nproc", soft=max_procs, hard=max_procs),
                                   Ulimit(name="nofile", soft=max_files, hard=max_files),
                                   Ulimit(name="nice", soft=5, hard=5)]}
        if volumes:
            host_config["binds"] = {local_path: {"bind": remote_path, "ro": False}
                                    for local_path, remote_path in volumes.items()}
        if config.dockergrader_apparmor_profile:
            host_config["security_opt"] = ["apparmor:%s" % config.dockergrader_apparmor_profile]
        volumes_list = volumes.values()
        container = self.client.create_container(image=image, command="/bin/bash", tty=True,
                                                 labels=labels, volumes=volumes_list,
                                                 host_config=create_host_config(**host_config))
        container_id = container['Id']

        # WARNING: Do not add ANY extra options to this method call.
        # Due to a bug in Docker-Py, all of our host_config options are clobbered when there are
        #     kwargs on this function. Adding any arguments here would eliminate our network
        #     isolation, memory limits, etc (huge problems).
        self.client.start(container_id)

        return Container(self, container['Id'])

    def stop(self, container_id, v=True, force=True):
        """
        Kills and destroys a container.

        v     -- Also removes the volumes associated with the container.
        force -- Stops container if it is running.

        """
        self.client.remove_container(container_id, v=v, force=force)

    def run_command(self, container_id, command, timeout=10):
        instance = self.client.exec_create(container=container_id, cmd=command, stdout=True,
                                           stderr=True, tty=False)
        old_timeout = self.client.timeout
        self.client.timeout = timeout
        try:
            output = self.client.exec_start(exec_id=instance['Id'], tty=False, stream=False)
            return output
        except (ConnectionError, ReadTimeout):
            # For forward-compatibility with whatever decision they make next
            # https://github.com/kennethreitz/requests/issues/2392
            raise TimeoutError()
        finally:
            self.client.timeout = old_timeout

    def bash(self, container_id, payload, user="root", timeout=10):
        return self.run_command(container_id, ["su", "-c", payload, "-s", "/bin/bash", user],
                                timeout)


class Container(object):
    def __init__(self, docker_client, container_id):
        """A convenience object that represents a single container."""
        self.docker_client = docker_client
        self.container_id = container_id

    def run_command(self, *args, **kwargs):
        return self.docker_client.run_command(self.container_id, *args, **kwargs)

    def bash(self, *args, **kwargs):
        return self.docker_client.bash(self.container_id, *args, **kwargs)

    def stop(self, *args, **kwargs):
        return self.docker_client.stop(self.container_id, *args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stop()


class TimeoutError(Exception):
    pass
