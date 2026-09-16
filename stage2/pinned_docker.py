"""Keep immutable runtime images while retaining Harbor's resource cleanup."""
from harbor.environments.docker.docker import DockerEnvironment


class PinnedImageDockerEnvironment(DockerEnvironment):
    async def _run_docker_compose_command(self, command, *args, **kwargs):
        forwarded = list(command)
        if forwarded[:1] == ['down']:
            for index in range(len(forwarded) - 1):
                if forwarded[index:index + 2] == ['--rmi', 'local']:
                    del forwarded[index:index + 2]
                    break
        return await super()._run_docker_compose_command(forwarded, *args, **kwargs)
