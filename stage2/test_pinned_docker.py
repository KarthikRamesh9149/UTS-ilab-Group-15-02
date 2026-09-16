import unittest
from unittest.mock import AsyncMock, patch

from pinned_docker import PinnedImageDockerEnvironment, DockerEnvironment


class PinnedDockerTests(unittest.IsolatedAsyncioTestCase):
    async def test_cleanup_preserves_images_not_trial_resources(self):
        environment = object.__new__(PinnedImageDockerEnvironment)
        command = ['down', '--rmi', 'local', '--volumes', '--remove-orphans']
        with patch.object(DockerEnvironment, '_run_docker_compose_command', new_callable=AsyncMock) as parent:
            parent.return_value = 'result'
            result = await environment._run_docker_compose_command(command, check=False, timeout_sec=30)
            parent.assert_awaited_once_with(['down', '--volumes', '--remove-orphans'], check=False, timeout_sec=30)
            self.assertEqual(result, 'result')
        self.assertEqual(command, ['down', '--rmi', 'local', '--volumes', '--remove-orphans'])

    async def test_other_commands_are_unchanged(self):
        environment = object.__new__(PinnedImageDockerEnvironment)
        for command in [['up', '-d'], ['down', '--volumes'], ['exec', 'main', 'echo', '--rmi', 'local']]:
            with patch.object(DockerEnvironment, '_run_docker_compose_command', new_callable=AsyncMock) as parent:
                await environment._run_docker_compose_command(command)
                parent.assert_awaited_once_with(command)
