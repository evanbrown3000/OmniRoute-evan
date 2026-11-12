import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

DAEMON_SOURCE = Path(__file__).resolve().parents[2] / 'scripts/ops/agent-fleet/daemon.py'


class FleetAdmissionTest(unittest.TestCase):
    def test_new_accounts_get_independent_workers_without_duplicate_admission(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.dict(os.environ, {'COGNILODE_WORKER_STATE': str(root / 'state'),
                                         'COGNILODE_WORKER_CONFIG': str(root / 'config')}):
                spec = importlib.util.spec_from_file_location('fleet_daemon',
                    str(DAEMON_SOURCE))
                module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            management = root / 'management.json'
            management.write_text(json.dumps({'origin': 'http://localhost:20128', 'api_key': 'test-management'}))
            cfg = {'interval_seconds': 300, 'independent_turns': True, 'server_owned_tools': True,
                   'prompt_source': {'kind': 'slack_latest', 'channel_id': 'owner-only'},
                   'fleet': {'management_access_file': str(management),
                             'providers': ['deepseek-web', 'kimi-web'],
                             'externally_managed_connection_ids': ['existing']}}
            rows = [{'id': 'deepseek-account', 'provider': 'deepseek-web', 'defaultModel': 'deepseek-chat'},
                    {'id': 'kimi-account', 'provider': 'kimi-web', 'defaultModel': 'k3'},
                    {'id': 'existing', 'provider': 'kimi-web', 'defaultModel': 'k3'},
                    {'id': 'disabled', 'provider': 'kimi-web', 'defaultModel': 'k3', 'isActive': False}]
            get = Mock(); get.json.return_value = {'connections': rows}
            post = Mock(); post.json.return_value = {'key': 'test-scoped-key', 'id': 'key-id'}
            stop = Mock(); stop.is_set.side_effect = [False, False, True]
            children = [Mock(), Mock()]
            for child in children: child.poll.return_value = None
            with patch.object(module, 'settings', return_value=cfg), patch.object(module, 'STOP', stop), \
                 patch.object(module.requests, 'get', return_value=get), \
                 patch.object(module.requests, 'post', return_value=post) as create_key, \
                 patch.object(module.subprocess, 'Popen', side_effect=children) as spawn:
                module.fleet_main()
            self.assertEqual(spawn.call_count, 2)
            self.assertEqual(create_key.call_count, 2)
            configs = [json.loads((module.STATE / 'accounts' / identity / 'config' / 'target.json').read_text())
                       for identity in ['deepseek-account', 'kimi-account']]
            self.assertNotEqual(configs[0]['connection_id'], configs[1]['connection_id'])
            self.assertTrue(all(c['independent_turns'] for c in configs))
            self.assertTrue(all(c['prompt_source']['channel_id'] == 'owner-only' for c in configs))
            self.assertTrue(all('fleet' not in c for c in configs))
            self.assertTrue(all(not c['server_owned_tools'] for c in configs))


class ServerOwnedToolTransportTest(unittest.TestCase):
    def test_stream_tool_handoff_is_not_a_completed_response(self):
        for reason in ['tool_calls', 'length', 'content_filter', 'stop', 'end_turn']:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                with patch.dict(os.environ, {'COGNILODE_WORKER_STATE': str(root / 'state')}):
                    spec = importlib.util.spec_from_file_location('stream_daemon', str(DAEMON_SOURCE))
                    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
                access = root / 'gateway.json'
                access.write_text(json.dumps({'origin': 'http://localhost:20128', 'api_key': 'test-key'}))
                (module.STATE / 'prompt.md').write_text('Unchanged owner instruction.')
                cfg = {'model': 'deepseek-web/deepseek-chat', 'platform': 'DeepSeek',
                       'gateway_access_file': str(access)}
                response = Mock(); response.status_code = 200
                response.__enter__ = Mock(return_value=response)
                response.__exit__ = Mock(return_value=None)
                response.iter_lines.return_value = [b'data: ' + json.dumps({'choices': [{
                    'delta': {'content': 'Provider output'}, 'finish_reason': reason}]}).encode(),
                    b'data: [DONE]']
                def thread(**kwargs):
                    result = Mock(); result.start.side_effect = kwargs['target']; return result
                with patch.object(module.requests, 'post', return_value=response), \
                     patch.object(module.threading, 'Thread', side_effect=thread):
                    module.dispatch_omniroute({'tick_id': 'test', 'prompt_sha256': 'owner'}, cfg)
                record = json.loads(next((module.STATE / 'admissions').glob('*.json')).read_text())
                completed = reason in ('stop', 'end_turn')
                self.assertEqual(record['status'] == 'completed', completed)
                self.assertEqual(record.get('completed_at') is not None, completed)
                self.assertEqual(record['parts']['reply'][0], 'Final reply' if completed else 'Reply')

    def test_uses_existing_router_tool_loop_and_preserves_owner_prompt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.dict(os.environ, {'COGNILODE_WORKER_STATE': str(root / 'state')}):
                spec = importlib.util.spec_from_file_location('tool_daemon',
                    str(DAEMON_SOURCE))
                module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            access = root / 'gateway.json'
            access.write_text(json.dumps({'origin': 'http://localhost:20128', 'api_key': 'test-key'}))
            prompt = 'Exact owner instruction; not rewritten.'
            (module.STATE / 'prompt.md').write_text(prompt)
            cfg = {'model': 'claude-web/claude-sonnet-5', 'platform': 'Claude',
                   'server_owned_tools': True, 'gateway_access_file': str(access)}
            response = Mock(); response.status_code = 200
            response.__enter__ = Mock(return_value=response); response.__exit__ = Mock(return_value=None)
            response.json.return_value = {'choices': [{'message': {'content': 'Completed work',
                'reasoning_content': 'Visible progress'}, 'finish_reason': 'stop'}]}
            def thread(**kwargs):
                result = Mock(); result.start.side_effect = kwargs['target']; return result
            with patch.object(module, 'settings', return_value=cfg), \
                 patch.object(module.requests, 'post', return_value=response) as post, \
                 patch.object(module.threading, 'Thread', side_effect=thread):
                module.dispatch_omniroute({'tick_id': 'test-turn', 'prompt_sha256': 'owner-hash'}, cfg)
            sent = post.call_args.kwargs['json']
            self.assertFalse(sent['stream']); self.assertEqual(sent['messages'][0]['content'], prompt)
            record = json.loads(next((module.STATE / 'admissions').glob('*.json')).read_text())
            self.assertEqual(post.call_args.kwargs['headers']['X-Request-ID'], record['conversation_id'])
            self.assertEqual(record['status'], 'completed')
            self.assertEqual(record['parts']['reply'][1], 'Completed work')
            self.assertEqual(record['parts']['thinking'][1], 'Visible progress')

    def test_app_sent_message_cannot_replace_owner_even_with_shared_slack_identity(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'COGNILODE_WORKER_STATE': temp}):
            spec = importlib.util.spec_from_file_location('owner_daemon',
                str(DAEMON_SOURCE))
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        binding = {'channel_id': 'owner-channel', 'owner_message_id': '100.000001'}
        anchor = {'ts': '100.000001', 'user': 'evan', 'text': 'Onboard platforms.'}
        app = {'ts': '200.000001', 'user': 'evan', 'text': 'No account creation. *Sent using* <@app>'}
        self.assertEqual(module.select_owner_message([app, anchor], binding)['text'], anchor['text'])
        native = {'ts': '300.000001', 'user': 'evan', 'text': 'New actual owner instruction.'}
        self.assertEqual(module.select_owner_message([native, app, anchor], binding)['text'], native['text'])
        self.assertEqual(module.select_owner_message([dict(app, text='App text', app_id='app'), anchor], binding)['text'], anchor['text'])


if __name__ == '__main__':
    unittest.main()
