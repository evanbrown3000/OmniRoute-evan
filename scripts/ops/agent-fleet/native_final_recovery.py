"""Recover omitted visible finals into the existing native presentation buffer.

On-demand recovery only: no turn submission, credential mutation, or scheduler.
Run inside the existing controller, whose Accounts runtime owns readback access.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

def recover_projection(snapshot, conversation, select_final, message_text):
    """Only reconcile the exact bound conversation and submitted current-branch turn."""
    cid = snapshot.get('conversation_id')
    if not cid or conversation.get('conversation_id') != cid:
        raise ValueError('Native conversation identity mismatch')
    if not (snapshot.get('binding') or {}).get('conversation_id'):
        raise ValueError('Application conversation binding required')
    expected = snapshot.get('prompt_sha256')
    mapping = conversation.get('mapping') or {}
    node, seen, prompt = conversation.get('current_node'), set(), None
    while node and node not in seen:
        seen.add(node)
        entry = mapping.get(node) or {}
        message = entry.get('message') or {}
        if (message.get('author') or {}).get('role') == 'user':
            candidate = message_text(message)
            if hashlib.sha256(candidate.encode()).hexdigest() == expected:
                prompt = candidate
            # Never recover an earlier turn across a later owner instruction.
            break
        node = entry.get('parent')
    if prompt is None:
        raise ValueError('Current native turn does not match submitted prompt')
    final = select_final(conversation, prompt)
    result = dict(snapshot)
    messages = [dict(m) for m in snapshot.get('messages', []) if m.get('id') != final['id']]
    messages.append({
        'id': final['id'], 'kind': 'final', 'author': final.get('author'),
        'channel': final.get('channel'), 'recipient': final.get('recipient'),
        'content_type': (final.get('content') or {}).get('content_type'),
        'text': message_text(final), 'preview': False, 'title': '',
        'status': final.get('status'), 'end_turn': True,
        'parent_id': (mapping.get(final['id']) or {}).get('parent'),
        'source': 'chatgpt-product-conversation-readback',
    })
    result.update(messages=messages, terminal_seen=True, status='turn ended',
                  final_recovered_at=time.time())
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', default='/native/native-visibility')
    parser.add_argument('--limit', type=int, default=3)
    parser.add_argument('--conversation-id', help='Only reconcile this exact native conversation')
    args = parser.parse_args()
    if not 1 <= args.limit <= 3:
        parser.error('--limit must be between 1 and 3')
    sys.path.insert(0, '/opt/adapter')
    from unified_prompting.native_readback import read_conversation, select_final, text
    from networks.integrations.accounts.controller_service import ControllerAccountsRuntime
    runtime = ControllerAccountsRuntime(json.loads(Path('/state/accounts.json').read_text()))
    credential = os.environ['COGNILODE_NATIVE_READBACK_CREDENTIAL_REF']
    directory = Path(args.directory)
    attempted = recovered = 0
    for path in sorted(directory.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:80]:
        before = path.read_bytes()
        snapshot = json.loads(before)
        if args.conversation_id and snapshot.get('conversation_id') != args.conversation_id:
            continue
        if snapshot.get('status') != 'turn ended' or time.time() - path.stat().st_mtime < 30:
            continue
        if any(m.get('kind') == 'final' and m.get('end_turn') and m.get('text', '').strip()
               for m in snapshot.get('messages', [])):
            continue
        if not snapshot.get('conversation_id') or not snapshot.get('binding'):
            continue
        attempted += 1
        try:
            conversation = read_conversation(snapshot['conversation_id'], runtime.reader, credential)
            result = recover_projection(snapshot, conversation, select_final, text)
            # Do not replace a producer snapshot changed while the network read ran.
            if path.read_bytes() != before:
                print(json.dumps({'status': 'producer_changed', 'stream_id': snapshot.get('stream_id')}), flush=True)
            else:
                temp = path.with_suffix('.recovery.tmp')
                temp.write_text(json.dumps(result, ensure_ascii=False))
                temp.chmod(0o600)
                os.chown(temp, path.stat().st_uid, path.stat().st_gid)
                temp.replace(path)
                recovered += 1
                print(json.dumps({'status': 'final_recovered',
                    'conversation_id': snapshot['conversation_id'],
                    'message_id': result['messages'][-1]['id']}), flush=True)
        except Exception as error:
            print(json.dumps({'status': 'not_recovered', 'error_type': type(error).__name__,
                'conversation_id': snapshot.get('conversation_id')}), flush=True)
        if attempted >= args.limit:
            break
    print(json.dumps({'attempted': attempted, 'recovered': recovered}), flush=True)

if __name__ == '__main__':
    main()

