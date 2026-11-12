import hashlib
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[2] / 'scripts/ops/agent-fleet/native_final_recovery.py'
spec = importlib.util.spec_from_file_location('native_final_recovery', str(SOURCE))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class NativeFinalRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.snapshot = {'conversation_id': 'native', 'binding': {'conversation_id': 'application'},
            'prompt_sha256': hashlib.sha256(b'Owner prompt').hexdigest(),
            'messages': [{'id': 'final', 'kind': 'reply', 'text': ''}]}
        self.final = {'id': 'final', 'author': {'role': 'assistant'}, 'status': 'finished_successfully',
            'end_turn': True, 'content': {'content_type': 'text', 'parts': ['Useful final']}}
        self.conversation = {'conversation_id': 'native', 'current_node': 'final', 'mapping': {
            'final': {'parent': 'user', 'message': self.final},
            'user': {'parent': None, 'message': {'author': {'role': 'user'},
                'content': {'parts': ['Owner prompt']}}}}}
        self.select = Mock(return_value=self.final)

    @staticmethod
    def text(message):
        return ''.join(message.get('content', {}).get('parts', []))

    def recover(self):
        return module.recover_projection(self.snapshot, self.conversation, self.select, self.text)

    def test_recovers_final_without_duplicate_message_or_mutating_input(self):
        recovered = self.recover()
        self.assertEqual(len(recovered['messages']), 1)
        self.assertEqual(recovered['messages'][0]['text'], 'Useful final')
        self.assertEqual(recovered['messages'][0]['parent_id'], 'user')
        self.assertEqual(recovered['messages'][0]['kind'], 'final')
        self.assertEqual(self.snapshot['messages'][0]['text'], '')
        self.select.assert_called_once_with(self.conversation, 'Owner prompt')

    def test_rejects_another_conversation_even_with_identical_prompt(self):
        self.conversation['conversation_id'] = 'another-native'
        with self.assertRaises(ValueError): self.recover()
        self.select.assert_not_called()

    def test_rejects_later_user_turn_instead_of_borrowing_an_older_final(self):
        self.conversation['current_node'] = 'later'
        self.conversation['mapping']['later'] = {'parent': 'final', 'message': {
            'author': {'role': 'user'}, 'content': {'parts': ['Later instruction']}}}
        with self.assertRaises(ValueError): self.recover()
        self.select.assert_not_called()

    def test_requires_application_binding_and_an_actual_final(self):
        self.snapshot['binding'] = {}
        with self.assertRaises(ValueError): self.recover()
        self.snapshot['binding'] = {'conversation_id': 'application'}
        self.select.side_effect = ValueError('No completed visible final')
        with self.assertRaises(ValueError): self.recover()


if __name__ == '__main__':
    unittest.main()
