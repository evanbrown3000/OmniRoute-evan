"""Latest message through the installed Slack MCP implementation, not a new API adapter."""
import csv
import io
import json
import os
from pathlib import Path
import select
import subprocess
import time

import requests


class SlackLatest:
    def __init__(self, credential_path):
        self.credential_path = credential_path
        self.process = None
        self.index = 0

    def _credential(self):
        return self.credential_path() if callable(self.credential_path) else json.loads(Path(self.credential_path).read_text())

    def _start(self):
        value = self._credential()
        env = dict(os.environ)
        env['SLACK_MCP_ADD_MESSAGE_TOOL'] = 'true'
        token = value['token']
        if token.startswith('xoxc-'):
            env['SLACK_MCP_XOXC_TOKEN'] = token
            env['SLACK_MCP_XOXD_TOKEN'] = value.get('xoxd_token') or next(
                (part.strip()[2:] for part in value.get('cookie', '').split(';') if part.strip().startswith('d=')), '')
        elif token.startswith('xoxp-'):
            env['SLACK_MCP_XOXP_TOKEN'] = token
        elif token.startswith('xoxb-'):
            env['SLACK_MCP_XOXB_TOKEN'] = token
        else:
            raise ValueError('Unsupported installed Slack credential type')
        self.process = subprocess.Popen(['/app/slack-mcp-server', '-no-cache'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1, env=env)
        self.index = 0
        self.call('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {},
            'clientInfo': {'name': 'cognilode-prompt-source', 'version': '1'}})
        self.process.stdin.write(json.dumps({'jsonrpc': '2.0', 'method': 'notifications/initialized'}) + '\n')
        self.process.stdin.flush()

    def call(self, method, params):
        if self.process is None:
            self._start()
        self.index += 1
        self.process.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': self.index,
            'method': method, 'params': params}) + '\n')
        self.process.stdin.flush()
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if not select.select([self.process.stdout], [], [], max(.01, deadline - time.monotonic()))[0]:
                break
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError('Installed Slack client exited')
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if message.get('id') == self.index:
                if 'error' in message:
                    raise RuntimeError('Installed Slack operation failed')
                return message['result']
        raise TimeoutError('Slack source read timed out')

    def latest(self, channel_id):
        # Read Slack's original message text. The MCP CSV presentation rewrites
        # some links, so it cannot provide the exact instruction body.
        value = self._credential()
        cookie = value.get('cookie') or ('d=' + value['xoxd_token'] if value.get('xoxd_token') else '')
        with requests.post('https://slack.com/api/conversations.history',
                data={'channel': channel_id, 'limit': 1},
                headers={'Authorization': 'Bearer ' + value['token'], 'Cookie': cookie,
                         'User-Agent': 'Cognilode-Prompt-Source/1', 'Cache-Control': 'no-cache'},
                timeout=(5, 20)) as response:
            response.raise_for_status()
            body = response.json()
        if not body.get('ok') or not body.get('messages'):
            raise RuntimeError('Slack latest-message read failed')
        message = body['messages'][0]
        if not isinstance(message.get('text'), str) or not message['text']:
            raise ValueError('Latest Slack message has no prompt text')
        return {'text': message['text'], 'message_id': message['ts'], 'channel_id': channel_id}

    def close(self):
        if self.process is None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
