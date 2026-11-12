import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[2] / 'scripts/ops/agent-fleet/stable_shell_service.py'
spec = importlib.util.spec_from_file_location('stable_shell_service', str(SOURCE))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class StableShellServiceTest(unittest.TestCase):
    def test_matches_only_exact_owned_script_and_role(self):
        command = b'python\0-u\0/workspace/stable-shell-service.py\0shell\0'
        self.assertTrue(module.matches_owned_process(command, 'shell'))
        self.assertFalse(module.matches_owned_process(command, 'tunnel'))

    def test_does_not_target_app_server_or_old_connector(self):
        self.assertFalse(module.matches_owned_process(b'python\0/opt/adapter/server.py\0', 'shell'))
        self.assertFalse(module.matches_owned_process(b'python\0/state/shell-app-code/run.py\0', 'shell'))

    def test_substrings_are_not_process_identity(self):
        self.assertFalse(module.matches_owned_process(
            b'python\0/workspace/stable-shell-service.py.backup\0shell\0', 'shell'))
        self.assertFalse(module.matches_owned_process(
            b'python\0/workspace/stable-shell-service.py\0shell-other\0', 'shell'))


if __name__ == '__main__':
    unittest.main()
