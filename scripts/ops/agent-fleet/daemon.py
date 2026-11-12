"""Recurring prompt admission; prompt/target are files, responses stay elsewhere."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from typing import TypedDict
from urllib.parse import quote
import uuid

import requests

CONFIG = Path(os.environ.get('COGNILODE_WORKER_CONFIG', '/config'))
STATE = Path(os.environ.get('COGNILODE_WORKER_STATE', '/state'))
STATE.mkdir(parents=True, exist_ok=True)
STOP = threading.Event()
SESSION = requests.Session()
SESSION.headers.update({'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36'})
LOGIN = None
TOKEN = None
SLACK = None
CONTEXT = None
LOGIN_LOCK = threading.RLock()


class Tick(TypedDict, total=False):
    tick_id: str
    status: str
    observed_at: float
    prompt_sha256: str
    conversation_id: str
    message_id: str
    admission: dict
    error_type: str
    prompt_source: dict
    prompt_number: int
    model: str
    reasoning_effort: str


def settings():
    return json.loads((CONFIG / 'target.json').read_text())


def select_owner_message(messages, binding):
    anchor = next((m for m in messages if m.get('ts') == binding['owner_message_id']), None)
    owner = binding.get('owner_user_id') or (anchor or {}).get('user')
    if not owner:
        raise ValueError('Designated owner identity unavailable')
    for message in sorted(messages, key=lambda m: m.get('ts', ''), reverse=True):
        text = message.get('text')
        if message.get('user') != owner or not isinstance(text, str) or not text:
            continue
        designated = message.get('ts') == binding['owner_message_id']
        app_sent = (message.get('bot_id') or message.get('app_id') or
                    message.get('subtype') == 'bot_message' or '*sent using*' in text.lower())
        if app_sent and not designated:
            continue
        return {'text': text, 'message_id': message['ts'], 'channel_id': binding['channel_id'],
                'owner_user_id': owner, 'source_selection': 'designated-owner-or-native-owner-message'}
    raise ValueError('No owner-authored instruction available')


def read_owner_instruction(slack, channel):
    binding_path = Path('/application-session/owner-instruction-source.json')
    if not binding_path.exists():
        return slack.latest(channel)
    binding = json.loads(binding_path.read_text())
    if binding['channel_id'] != channel:
        return slack.latest(channel)
    access = slack._credential()
    cookie = access.get('cookie') or ('d=' + access['xoxd_token'] if access.get('xoxd_token') else '')
    headers = {'Authorization': 'Bearer ' + access['token'], 'Cookie': cookie,
               'User-Agent': 'Cognilode-Prompt-Source/1', 'Cache-Control': 'no-cache'}
    def history(parameters):
        response = requests.post('https://slack.com/api/conversations.history',
                                 data={'channel': channel, **parameters}, headers=headers, timeout=(5, 20))
        response.raise_for_status(); body = response.json()
        if not body.get('ok'): raise RuntimeError('Slack owner-message read failed')
        return body.get('messages', [])
    messages = history({'limit': 100})
    if not any(m.get('ts') == binding['owner_message_id'] for m in messages):
        messages += history({'oldest': binding['owner_message_id'], 'latest': binding['owner_message_id'],
                             'inclusive': 'true', 'limit': 1})
    return select_owner_message(messages, binding)


def prepare(state):
    global SLACK
    cfg = settings()
    if cfg.get('paused'):
        return {'status': 'paused', 'observed_at': time.time()}
    source = {}
    if cfg.get('prompt_source', {}).get('kind') == 'slack_latest':
        if SLACK is None:
            from slack_latest import SlackLatest
            SLACK = SlackLatest(CONFIG / 'slack.private.json')
        try:
            source = read_owner_instruction(SLACK, cfg['prompt_source']['channel_id'])
            cache = STATE / 'owner-instruction.json'
            cache.write_text(json.dumps(source)); cache.chmod(0o600)
        except Exception:
            SLACK.close()
            SLACK = None
            cache = STATE / 'owner-instruction.json'
            if not cache.exists(): raise
            source = json.loads(cache.read_text())
            source['cached_owner_instruction'] = True
        prompt = source.pop('text')
        (STATE / 'prompt.md').write_text(prompt)
        (STATE / 'prompt.md').chmod(0o600)
    else:
        prompt = (CONFIG / 'prompt.md').read_text()
    unresolved = STATE / 'unresolved.json'
    if unresolved.exists() and not cfg.get('independent_turns'):
        intent = json.loads(unresolved.read_text())
        if time.time() - intent.get('submitted_at', time.time()) >= cfg.get('uncertainty_grace_seconds', 300):
            # User-selected policy: uncertainty must not freeze the fleet.
            # Preserve the original intent; release a fresh conversation seat,
            # rather than replay the same original POST identity.
            previous = STATE / 'last_uncertain.json'
            previous.write_text(json.dumps(intent)); previous.chmod(0o600)
            unresolved.unlink()
            rotor = STATE / 'rotor.json'
            rotor.write_text(json.dumps({'conversation_id':str(uuid.uuid4()),'submitted':0,'parent_message_id':None,'last_submitted_at':time.time()-cfg.get('interval_seconds',300)}))
            rotor.chmod(0o600)
            status = 'ready'
        else:
            status = 'reconciliation_required'
    elif not prompt.strip() or not cfg.get('agent'):
        status = 'waiting_configuration'
    else:
        status = 'ready'
    return {'status': status, 'observed_at': time.time(),
            'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
            'prompt_source': source}


def authenticate():
    with LOGIN_LOCK:
        return _authenticate()


def _authenticate():
    global TOKEN, LOGIN
    if TOKEN:
        return
    access = json.loads((CONFIG / 'access.private.json').read_text())
    if LOGIN is None:
        namespace = {'__name__': 'retained_application_access'}
        exec(compile((CONFIG / 'access_method.py').read_text(), 'accounts:librechat-access', 'exec'), namespace)
        LOGIN = namespace['native_login']
    session, _, _ = LOGIN(access)
    TOKEN = session['token']
    SESSION.headers.update({'Authorization': 'Bearer ' + TOKEN})


def dispatch(state):
    global TOKEN
    if state['status'] != 'ready':
        return {}
    cfg = settings()
    if cfg.get('transport') == 'omniroute':
        return dispatch_omniroute(state, cfg)
    authenticate()
    origin = json.loads((CONFIG / 'access.private.json').read_text())['origin'].rstrip('/')
    rotor_path = STATE / 'rotor.json'
    rotor = json.loads(rotor_path.read_text()) if rotor_path.exists() else {}
    if not rotor.get('conversation_id'):
        rotor = {'conversation_id': cfg.get('conversation_id') or str(uuid.uuid4()),
                 'submitted': 0, 'parent_message_id': cfg.get('parent_message_id')}
    last_submitted = max(rotor.get('last_submitted_at', 0), rotor.get('last_attempt_at', 0)) or (rotor_path.stat().st_mtime if rotor_path.exists() else 0)
    changed = state.get('prompt_sha256') != rotor.get('last_prompt_sha256')
    due_in = float(cfg.get('interval_seconds',300)) - (time.time()-last_submitted)
    if due_in > 0 and not changed:
        return {'status':'not_due','conversation_id':rotor['conversation_id'],'next_due_in':due_in}
    if cfg.get('independent_turns'):
        # Each new assignment/recurrence has its own seat. Missing END on another
        # conversation is neither a lock nor a reason to abort that provider turn.
        rotor = {'conversation_id': str(uuid.uuid4()), 'submitted': 0, 'parent_message_id': None}
        active = []
    else:
        active = None
    # The compact active-job index avoids fetching aggregated response content.
    if active is None:
        response = SESSION.get(origin + '/api/agents/chat/active', timeout=15)
        if response.status_code == 401:
            TOKEN = None
            authenticate()
            response = SESSION.get(origin + '/api/agents/chat/active', timeout=15)
        response.raise_for_status()
        active = response.json().get('activeJobIds', [])
    if rotor['conversation_id'] in active:
        recent = None
        for path in Path('/native/native-visibility').glob('*.json'):
            try:
                value = json.loads(path.read_text())
                if (value.get('binding') or {}).get('conversation_id') == rotor['conversation_id']:
                    if recent is None or value.get('last_event_at',0)>recent.get('last_event_at',0):recent=value
            except (OSError,ValueError):continue
        last_progress = (recent or {}).get('last_event_at') or last_submitted
        grace = cfg.get('quiet_seat_recovery_seconds',300)
        if time.time()-last_progress < grace or len(active)>=20:
            return {'status': 'already_active', 'conversation_id': rotor['conversation_id'],
                    'prompt_number': rotor['submitted']}
        # A quiet, unconfirmed transport does not freeze recurring work. Keep
        # its original identity and allow it to finish; open a fresh seat rather
        # than replaying or aborting the original mutation. Active source cap 20.
        previous = STATE / 'last_quiet_seat.json'
        previous.write_text(json.dumps({'conversation_id':rotor['conversation_id'],
            'last_progress_at':last_progress,'released_at':time.time()}));previous.chmod(0o600)
        rotor={'conversation_id':str(uuid.uuid4()),'submitted':0,'parent_message_id':None}
    if rotor['submitted'] >= int(cfg.get('prompts_per_conversation', 3)):
        rotor = {'conversation_id': str(uuid.uuid4()), 'submitted': 0, 'parent_message_id': None}
    message_id = str(uuid.uuid4())
    assistant_id = str(uuid.uuid4())
    prompt_path = STATE / 'prompt.md' if cfg.get('prompt_source', {}).get('kind') == 'slack_latest' else CONFIG / 'prompt.md'
    prompt = prompt_path.read_text()
    # Current owner instruction: no introductions, identifier substitutions,
    # team-context appendix, post-notes or other instruction text.
    context_receipt = {}
    body = {'text': prompt,
        'endpoint': cfg['agent'], 'endpointType': 'custom', 'model': cfg.get('model', 'auto'),
        'reasoning_effort': cfg.get('reasoning_effort'),
        'conversationId': rotor['conversation_id'], 'messageId': message_id,
        'overrideUserMessageId': message_id, 'clientRequestId': state['tick_id'],
        'responseMessageId': assistant_id,
        'parentMessageId': rotor.get('parent_message_id') or '00000000-0000-0000-0000-000000000000',
        'isContinued': False, 'isTemporary': False}
    intent = {'tick_id': state['tick_id'], 'conversation_id': rotor['conversation_id'],
              'message_id': message_id, 'assistant_message_id': assistant_id, 'submitted_at': time.time(),
              'prompt_sha256': state.get('prompt_sha256')}
    admissions = STATE / 'admissions'
    admissions.mkdir(exist_ok=True, mode=0o700)
    receipt = admissions / (intent['conversation_id'] + '.json')
    receipt.write_text(json.dumps(intent)); receipt.chmod(0o600)
    # Record attempts, including uncertain ones, so an outage cannot cause a POST
    # on every observer poll. A genuinely new prompt is independently admissible.
    rotor.update(last_attempt_at=time.time(), last_prompt_sha256=state.get('prompt_sha256'))
    rotor_path.write_text(json.dumps(rotor)); rotor_path.chmod(0o600)
    # An uncertain POST must not become another scheduled submission.
    unresolved = STATE / 'unresolved.json'
    unresolved.write_text(json.dumps(intent))
    unresolved.chmod(0o600)
    response = SESSION.post(origin + '/api/agents/chat/' + quote(cfg['agent'], safe=''),
        json=body, timeout=(10, 20), stream=True)
    if response.status_code == 401:
        # Admission rejected the expired application session, so no provider turn
        # was accepted. Refresh through the retained login method and retry this
        # same intent once. Never replay an ambiguous or accepted provider POST.
        response.close()
        TOKEN = None
        authenticate()
        response = SESSION.post(origin + '/api/agents/chat/' + quote(cfg['agent'], safe=''),
            json=body, timeout=(10, 20), stream=True)
    response.raise_for_status()
    admission = response.json() if 'application/json' in response.headers.get('Content-Type', '') else {'http_status': response.status_code}
    response.close()
    intent['admission'] = admission
    receipt.write_text(json.dumps(intent)); receipt.chmod(0o600)
    rotor.update(submitted=rotor['submitted'] + 1, parent_message_id=assistant_id, last_submitted_at=time.time())
    rotor_path.write_text(json.dumps(rotor))
    rotor_path.chmod(0o600)
    unresolved.unlink()
    return {'status': 'submitted', 'conversation_id': rotor['conversation_id'],
            'message_id': message_id, 'admission': admission, 'prompt_number': rotor['submitted'],
            'model': cfg.get('model'), 'reasoning_effort': cfg.get('reasoning_effort'),
            'team_context':context_receipt,
            'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest()}


def dispatch_omniroute(state, cfg):
    """Reuse the independent timer for a registered OmniRoute website provider."""
    rotor_path = STATE / 'rotor.json'
    rotor = json.loads(rotor_path.read_text()) if rotor_path.exists() else {}
    changed = state.get('prompt_sha256') != rotor.get('last_prompt_sha256')
    due = float(cfg.get('interval_seconds', 300)) - (time.time() - rotor.get('last_attempt_at', 0))
    if due > 0 and not changed:
        return {'status': 'not_due', 'conversation_id': rotor.get('conversation_id'), 'next_due_in': due}
    identity = str(uuid.uuid4())
    directory = STATE / 'admissions'; directory.mkdir(exist_ok=True, mode=0o700)
    path = directory / (identity + '.json')
    record = {'tick_id': state['tick_id'], 'conversation_id': identity,
              'submitted_at': time.time(), 'prompt_sha256': state['prompt_sha256'],
              'platform': cfg['platform'], 'model': cfg['model'], 'status': 'dispatching', 'parts': {}}
    def save():
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(record)); temporary.chmod(0o600); temporary.replace(path)
    save()
    rotor = {'conversation_id': identity, 'submitted': 0, 'last_attempt_at': time.time(),
             'last_prompt_sha256': state['prompt_sha256']}
    rotor_path.write_text(json.dumps(rotor)); rotor_path.chmod(0o600)
    prompt = (STATE / 'prompt.md').read_text()
    def run():
        try:
            access = json.loads(Path(cfg['gateway_access_file']).read_text())
            headers = {'Authorization': 'Bearer ' + access['api_key'], 'Content-Type': 'application/json',
                       'X-Request-ID': identity}
            stream = not cfg.get('server_owned_tools', False)
            body = {'model': cfg['model'], 'messages': [{'role': 'user', 'content': prompt}], 'stream': stream}
            if cfg.get('reasoning_effort'): body['reasoning_effort'] = cfg['reasoning_effort']
            text, thinking, finished = '', '', False
            with requests.post(access['origin'].rstrip('/') + '/v1/chat/completions',
                               headers=headers, json=body, stream=True, timeout=(10, 90)) as response:
                record['http_status'] = response.status_code
                response.raise_for_status()
                record.update(status='working', accepted_at=time.time()); save()
                if not stream:
                    result = response.json()
                    choice = result.get('choices', [{}])[0]
                    message = choice.get('message') or {}
                    reply = message.get('content') or ''
                    if isinstance(reply, list):
                        reply = ''.join(part.get('text', '') for part in reply if isinstance(part, dict))
                    thinking = message.get('reasoning_content') or ''
                    finished = choice.get('finish_reason') in ('stop', 'end_turn')
                    record.update(parts={'reply': ['Final reply' if finished else 'Reply', reply],
                                         'thinking': ['Thinking', thinking]},
                                  status='completed' if finished else 'awaiting_tool_or_final',
                                  completed_at=time.time() if finished else None,
                                  server_owned_tools=True, usage=result.get('usage'))
                    save()
                    return
                for line in response.iter_lines():
                    if not line or not line.startswith(b'data:'): continue
                    value = line[5:].strip()
                    if value == b'[DONE]': break
                    event = json.loads(value)
                    if event.get('error'):
                        record.update(status='provider_error', error_type='upstream_error'); save(); return
                    for choice in event.get('choices', []):
                        delta = choice.get('delta') or {}
                        if isinstance(delta.get('content'), str): text += delta['content']
                        if isinstance(delta.get('reasoning_content'), str): thinking += delta['reasoning_content']
                        if choice.get('finish_reason') is not None: finished = True
                    record['parts'] = {'reply': ['Final reply' if finished else 'Reply', text],
                                       'thinking': ['Thinking', thinking]}
                    if event.get('claude_web'): record['native_metadata'] = event['claude_web']
                    record['last_progress_at'] = time.time(); save()
                record['status'] = 'completed' if finished else 'stream_ended_without_final'
                record['completed_at'] = time.time() if finished else None
                save()
        except Exception as error:
            record.update(status='error', error_type=type(error).__name__); save()
    threading.Thread(target=run, daemon=True, name='omniroute-' + identity[:8]).start()
    return {'status': 'dispatching', 'conversation_id': identity, 'model': cfg['model']}


def fleet_main():
    """Admit registered HTTP website connections into this same recurring worker."""
    cfg = settings()
    fleet = cfg['fleet']
    access = json.loads(Path(fleet['management_access_file']).read_text())
    origin = access['origin'].rstrip('/')
    headers = {'Authorization': 'Bearer ' + access['api_key']}
    allowed = set(fleet['providers'])
    ignored = set(fleet.get('externally_managed_connection_ids', []))
    children = {}
    root = STATE / 'accounts'
    root.mkdir(exist_ok=True)
    def private(path, value):
        path.write_text(json.dumps(value)); path.chmod(0o600)
    try:
        while not STOP.is_set():
            try:
                response = requests.get(origin + '/api/providers', headers=headers, timeout=60)
                response.raise_for_status()
                live = set()
                for row in response.json().get('connections', []):
                    identity = row['id']
                    if row.get('provider') not in allowed or identity in ignored or row.get('isActive') is False:
                        continue
                    model = row.get('defaultModel')
                    if not model:
                        continue
                    live.add(identity)
                    if identity in children and children[identity].poll() is None:
                        continue
                    directory = root / identity
                    config = directory / 'config'; state = directory / 'state'
                    config.mkdir(parents=True, exist_ok=True); state.mkdir(exist_ok=True)
                    gateway = config / 'gateway.private.json'
                    if not gateway.exists():
                        result = requests.post(origin + '/api/keys', headers=headers, json={
                            'name': 'Recurring website ' + identity,
                            'allowedModels': [row['provider'] + '/' + model],
                            'allowedConnections': [identity]}, timeout=15)
                        result.raise_for_status(); key = result.json()
                        private(gateway, {'origin': origin, 'api_key': key['key'], 'key_id': key['id']})
                    slack = config / 'slack.private.json'
                    if not slack.exists(): slack.symlink_to(CONFIG / 'slack.private.json')
                    target = {k: v for k, v in cfg.items() if k != 'fleet'}
                    target.update(transport='omniroute', platform=row['provider'], agent=row['provider'],
                                  model=row['provider'] + '/' + model, connection_id=identity,
                                  gateway_access_file=str(gateway), lane=identity,
                                  lane_title=row.get('name') or row['provider'])
                    target['server_owned_tools'] = bool(cfg.get('server_owned_tools') and
                        row['provider'] in fleet.get('server_owned_tool_providers', []))
                    private(config / 'target.json', target)
                    env = dict(os.environ, COGNILODE_WORKER_CONFIG=str(config), COGNILODE_WORKER_STATE=str(state))
                    children[identity] = subprocess.Popen([sys.executable, '/app/daemon.py'], env=env)
                    print(json.dumps({'component': 'fleet-admission', 'connection_id': identity,
                                      'provider': row['provider'], 'status': 'recurring_worker_started'}), flush=True)
                for identity in list(children):
                    if identity not in live:
                        children.pop(identity).terminate()
            except Exception as error:
                print(json.dumps({'component': 'fleet-admission', 'error_type': type(error).__name__}), flush=True)
            STOP.wait(30)
    finally:
        for child in children.values():
            if child.poll() is None: child.terminate()


def main():
    global CONTEXT
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: STOP.set())
    if settings().get('fleet'):
        return fleet_main()
    from visibility import Visibility
    from context import TeamContext
    CONTEXT=TeamContext(CONFIG,STOP)
    CONTEXT.start()
    visibility = Visibility(CONFIG, STATE, STOP, authenticate, SESSION)
    visibility.start()
    while not STOP.is_set():
        started = time.monotonic()
        tick = str(uuid.uuid4())
        try:
            state = {'tick_id': tick, **prepare({})}
            state.update(dispatch(state))
        except Exception as error:
            state = {'tick_id': tick, 'status': 'error', 'error_type': type(error).__name__,
                     'observed_at': time.time()}
            if isinstance(error, requests.HTTPError) and error.response is not None:
                state['http_status'] = error.response.status_code
            failure = STATE / 'last_error.json'
            failure.write_text(json.dumps(state)); failure.chmod(0o600)
        (STATE / 'latest.json').write_text(json.dumps(state))
        print(json.dumps(state), flush=True)
        try:
            interval = max(5, float(settings().get('interval_seconds', 300)))
        except Exception:
            interval = 300
        poll = max(5, float(settings().get('poll_interval_seconds', interval)))
        STOP.wait(max(.1, min(interval,poll,state.get('next_due_in',interval)) - (time.monotonic() - started)))
    if SLACK is not None:
        SLACK.close()


if __name__ == '__main__':
    main()
