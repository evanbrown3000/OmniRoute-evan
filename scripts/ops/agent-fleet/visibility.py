"""Bounded read-only LibreChat SSE -> Slack presentation; never submits a turn."""
import hashlib
import html
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import quote

import requests
from slack_latest import SlackLatest


def display_text(value):
    if isinstance(value, str):
        value = re.sub(r'<icon\b[^>]*name="arrow-down"[^>]*/>', '↓', value)
        value = re.sub(r'</?(?:box|caption|icon|row|column|title|text|badge)\b[^>]*>', '\n', value)
        return re.sub(r'\n{3,}', '\n\n', html.unescape(value)).strip()
    if isinstance(value, dict):
        return display_text(value.get('value', value.get('text', '')))
    return ''


def part_text(part):
    kind = part.get('type', '')
    if kind in ('text','output_text','input_text'):
        return 'Reply', display_text(part.get('text', ''))
    if kind in ('reasoning','think','thinking'):
        return 'Thinking', display_text(part.get('think') or part.get('text') or part.get('thinking') or '')
    if kind in ('tool_call','function_call','custom_tool_call'):
        call = part.get('tool_call', part)
        name = call.get('name') or call.get('function', {}).get('name') or 'tool'
        return 'Tool · ' + name, display_text(call.get('output') or call.get('result') or call.get('status') or 'working')[:1200]
    if kind == 'error':
        return 'Error', display_text(part.get('error') or part.get('text') or '')
    if kind in ('image_file','image_url','file'):
        return 'Attachment', display_text(part.get('url') or part.get('file_id') or '[attachment retained by source]')
    return '', ''


class Visibility:
    def __init__(self, config, state, stop, authenticate, session):
        self.config, self.state, self.stop = Path(config), Path(state), stop
        self.authenticate, self.session = authenticate, session
        self.lock = threading.RLock()
        self.parts, self.status = {}, 'waiting for admission'
        self.native_parents={}
        self.conversation, self.generation = None, None
        self.receipt_path = self.state / 'visibility.json'
        self.receipts = json.loads(self.receipt_path.read_text()) if self.receipt_path.exists() else {}
        self.slack = None
        self.history_cursor = 0

    def start(self):
        threading.Thread(target=self.follow, daemon=True, name='conversation-sse').start()
        threading.Thread(target=self.publish_loop, daemon=True, name='slack-presentation').start()

    def cfg(self):
        return json.loads((self.config/'target.json').read_text())

    def request(self, path, **kwargs):
        self.authenticate()
        access = json.loads((self.config/'access.private.json').read_text())
        headers = dict(self.session.headers)
        return requests.get(access['origin'].rstrip('/')+path, headers=headers, **kwargs)

    def snapshot(self, value):
        content = value.get('aggregatedContent') or (value.get('resumeState') or {}).get('aggregatedContent') or []
        with self.lock:
            for i, part in enumerate(content[:64]):
                label, text = part_text(part)
                if label and text:
                    self.parts[str(i)] = (label,text[-65536:])

    def event(self, value):
        if value.get('sync'):
            self.snapshot(value.get('resumeState') or {})
        data = value.get('data') or {}
        if value.get('event') == 'on_message_delta':
            for part in (data.get('delta') or {}).get('content', []):
                label,text=part_text(part)
                if not label or not text:continue
                index=str(part.get('index',0))
                with self.lock:
                    old=self.parts.get(index,(label,''))[1]
                    self.parts[index]=(label,(old+text)[-65536:])
        if value.get('final'):
            response=value.get('responseMessage') or {}
            self.snapshot({'aggregatedContent':response.get('content') or []})
            if response.get('text'):
                with self.lock:self.parts['final']=('Final reply',display_text(response['text'])[-65536:])
            with self.lock:self.status='turn ended'
        elif value.get('error'):
            with self.lock:self.status='stream error: '+str(value['error'])[:300]

    def follow(self):
        completed=None
        while not self.stop.is_set():
            try:
                cfg=self.cfg()
                if not cfg.get('visibility',{}).get('enabled'):
                    self.stop.wait(5);continue
                if cfg.get('transport')=='omniroute':
                    rotor_path=self.state/'rotor.json'
                    if rotor_path.exists():
                        rotor=json.loads(rotor_path.read_text());cid=rotor.get('conversation_id')
                        record_path=self.state/'admissions'/(str(cid)+'.json')
                        if record_path.exists():
                            record=json.loads(record_path.read_text())
                            with self.lock:
                                self.conversation=cid;self.generation=int(record['submitted_at']*1000)
                                self.parts={k:tuple(v)for k,v in record.get('parts',{}).items()if v[1]}
                                self.status=record.get('status','working')
                    self.stop.wait(2);continue
                latest_path=self.state/'latest.json'
                if not latest_path.exists():self.stop.wait(1);continue
                latest=json.loads(latest_path.read_text());cid=latest.get('conversation_id')
                if not cid and (self.state/'rotor.json').exists():cid=json.loads((self.state/'rotor.json').read_text()).get('conversation_id')
                if not cid:self.stop.wait(2);continue
                epoch=(latest.get('admission')or{}).get('generationCreatedAt')
                if epoch is None and self.conversation==cid:epoch=self.generation
                key=(cid,epoch)
                if key==completed:self.stop.wait(2);continue
                status=self.request('/api/agents/chat/status/'+quote(cid,safe=''),timeout=20)
                status.raise_for_status();s=status.json();epoch=s.get('createdAt')or epoch
                with self.lock:
                    if (self.conversation,self.generation)!=(cid,epoch):
                        self.parts={};self.conversation,self.generation=cid,epoch
                    self.status=s.get('status') or ('working' if s.get('active') else 'turn ended')
                self.snapshot(s)
                if not s.get('active'):
                    messages=self.request('/api/messages/'+quote(cid,safe=''),timeout=20)
                    messages.raise_for_status();rows=messages.json()
                    for m in (rows if isinstance(rows,list)else rows.get('messages',[]))[-3:]:
                        if not m.get('isCreatedByUser'):
                            self.snapshot({'aggregatedContent':m.get('content')or[]})
                            if m.get('text'):
                                with self.lock:self.parts['final']=('Final reply',display_text(m['text'])[-65536:])
                    completed=key;self.stop.wait(2);continue
                params={'resume':'true'}
                if epoch is not None:params['generationCreatedAt']=epoch
                with self.request('/api/agents/chat/stream/'+quote(cid,safe=''),params=params,
                                  stream=True,timeout=(10,45)) as response:
                    response.raise_for_status()
                    while not self.stop.is_set():
                        line=response.raw.readline(2*1024*1024)
                        if not line:break
                        # A lost END must not pin the viewer to an older seat.
                        current=json.loads(latest_path.read_text()).get('conversation_id')
                        if current and current!=cid:break
                        if line.startswith(b'data: '):
                            self.event(json.loads(line[6:]))
                # Lost END is a transport observation, not a stop condition.
                self.stop.wait(3)
            except Exception as error:
                with self.lock:self.status='reconnecting · '+type(error).__name__
                self.stop.wait(5)

    def send(self, name, arguments):
        if self.slack is None:self.slack=SlackLatest(self.config/'slack.private.json')
        if name=='conversations_add_message':
            # One explicit block also avoids the upstream Markdown converter
            # creating more than fifty blocks from tool-heavy paragraphs.
            arguments=dict(arguments,blocks=json.dumps([{'type':'section','text':{
                'type':'mrkdwn','text':arguments['text']}}]))
        from filelock import FileLock
        pacing=Path('/application-session/slack-pacing')
        with FileLock(str(pacing)+'.lock',timeout=20):
            previous=float(pacing.read_text()) if pacing.exists() else 0
            time.sleep(max(0,min(1.1,1.1-(time.time()-previous))))
            result=self.slack.call('tools/call',{'name':name,'arguments':arguments})
            pacing.write_text(str(time.time()));pacing.chmod(0o600)
        if result.get('isError'):
            body=' '.join(x.get('text','') for x in result.get('content',[]) if x.get('type')=='text')
            code=next((x for x in ('invalid_blocks','msg_too_long','ratelimited','invalid_auth','channel_not_found','message_not_found','not_in_channel','not enabled') if x in body.lower()),'upstream_error')
            raise RuntimeError('Slack projection rejected: '+code)
        return '\n'.join(x.get('text','')for x in result.get('content',[])if x.get('type')=='text')

    def save(self):
        p=self.receipt_path.with_suffix('.tmp');p.write_text(json.dumps(self.receipts));p.chmod(0o600);p.replace(self.receipt_path)
        from context import worker_observation
        worker_observation(self.config,self.state,self.receipts,self.status)

    def native_snapshot(self, cid):
        directory=Path('/native/native-visibility')
        if not directory.exists():return
        latest=json.loads((self.state/'latest.json').read_text())
        prompt_hash=latest.get('prompt_sha256')
        epoch=(latest.get('admission')or{}).get('generationCreatedAt')or(self.generation if self.conversation==cid else None)
        chosen=None
        for path in sorted(directory.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:64]:
            try:
                value=json.loads(path.read_text())
                bound=(value.get('binding')or{}).get('conversation_id')
                # Different workers often receive the same exact owner prompt.
                # A prompt hash alone must never join their native responses.
                if bound==cid and (epoch is None or value.get('created_at',0)>=epoch/1000-2):
                    chosen=value;break
            except (OSError,ValueError):continue
        if not chosen:return
        self.receipts['native_conversation_id']=chosen.get('conversation_id')
        self.receipts['native_conversation_url']=chosen.get('conversation_url')
        self.receipts['native_stream_id']=chosen.get('stream_id')
        self.receipts['observed_model']=chosen.get('observed_model')
        self.receipts['observed_effort']=chosen.get('observed_effort')
        with self.lock:
            native_messages=chosen.get('messages',[])
            self.native_parents={m['id']:m.get('parent_id') for m in native_messages}
            selected_ids={m['id'] for m in native_messages if m.get('kind') not in ('user','tool_call','tool_result')}
            for key in list(self.parts):
                if key.startswith('native:') and key!='native:activity' and key[7:]not in selected_ids:self.parts.pop(key)
            tool_lines=[]
            for message in native_messages:
                kind=message.get('kind')
                if kind=='user':continue
                label={'thoughts':'Thinking','tool_call':'Tool call','tool_result':'Tool result','reply':'Reply','final':'Final reply'}.get(kind,'Activity')
                title=display_text(message.get('title',''))
                recipient=message.get('recipient')
                if recipient and recipient not in ('all','user'):label+=' · '+recipient
                text=display_text(message.get('text',''))
                if kind in ('tool_call','tool_result'):
                    if kind=='tool_call':
                        try:
                            args=json.loads(message.get('text',''))
                            path=args.get('path','');parameters=args.get('args')or{}
                            operation=path.rsplit('/',1)[-1].replace('_',' ')
                            target=next((str(parameters[k]) for k in ('path','repo','repository','url','query') if parameters.get(k)), '')
                            text=title or (operation+' · '+target[:220]).strip(' ·') or 'Provider tool running'
                        except (ValueError,AttributeError):text=title or 'Provider tool running'
                    else:
                        text=title or 'Provider tool result received'
                    tool_lines.append(text+' · `'+message['id']+'`')
                    continue
                elif title:text=title+'\n'+text
                if text:self.parts['native:'+message['id']]=(label,text)
                while len(self.parts)>96:self.parts.pop(next(iter(self.parts)))
            if tool_lines:self.parts['native:activity']=('Recent tool activity','\n'.join(tool_lines[-8:]))
            if any(m.get('kind')=='final' and m.get('end_turn') for m in chosen.get('messages',[])):self.status='turn ended'
            elif chosen.get('status')=='turn ended':self.status='native activity observed; turn completion unconfirmed'
            elif chosen.get('status'):self.status=chosen['status']

    def publish(self):
        cfg=self.cfg();vis=cfg.get('visibility')or{}
        if not vis.get('enabled'):return
        with self.lock:cid,epoch,parts,status=self.conversation,self.generation,dict(self.parts),self.status
        if not cid and (self.state/'rotor.json').exists():cid=json.loads((self.state/'rotor.json').read_text()).get('conversation_id')
        if not cid:return
        self.native_snapshot(cid)
        with self.lock:parts=dict(self.parts);status=self.status
        channel=vis['channel_id'];root=self.receipts.get('thread_ts')
        if not root:
            title=cfg.get('lane_title')or cfg.get('lane')or'Portfolio worker'
            text=('*'+title+'*\n'+cfg.get('platform','ChatGPT')+' hosted worker · '+cfg.get('model','')+'\n'
                  'Prompted through LibreChat every 5 minutes. Progress below is observed output, not an agent status claim.\n'
                  'Origin: '+cfg.get('origin_label','enrolled laptop → LibreChat API → chat2api → ChatGPT.com')+'\n'
                  'Accounts access: '+cfg.get('accounts_installation_ref','retained application access')+'\n'
                  'Native provider/tool details will be shown when supplied by the source; no browser session is inferred.')
            # Reconcile an uncertain root write by its exact text, not blind retry.
            pending=self.receipts.get('root_pending')
            if pending:
                result=self.send('conversations_history',{'channel_id':channel,'limit':'30'})
                import csv,io
                row=next((r for r in csv.DictReader(io.StringIO(result))if r.get('Text')==text),None)
                if row:root=row['MsgID']
                else:self.receipts.pop('root_pending',None)
            if not root:
                self.receipts['root_pending']=True;self.save()
                result=self.send('conversations_add_message',{'channel_id':channel,'text':text})
                found=re.search(r'ts[=:]\s*([0-9]+\.[0-9]+)',result)
                if not found:raise RuntimeError('Slack did not expose message identity')
                root=found.group(1)
            self.receipts.update(thread_ts=root,channel_id=channel);self.receipts.pop('root_pending',None);self.save()
        chunks={'status':('*'+status+'*\nConversation `'+cid+'` · generation `'+str(epoch)+'`\n'
                          '<'+vis.get('ui_origin','http://localhost:3080')+'/c/'+cid+'|Open LibreChat conversation>'
                          + ('\nNative `'+self.receipts['native_conversation_id']+'` · <'+self.receipts['native_conversation_url']+'|Open ChatGPT conversation>' if self.receipts.get('native_conversation_id') else ''))}
        for key,(label,text)in parts.items():
            # The installed Slack method generates section blocks, whose text
            # limit is 3000 characters even though a message allows much more.
            for offset in range(0,min(len(text),30000),2400):
                body='*'+label+'*\n'+text[offset:offset+2400]
                if key.startswith('native:') and key!='native:activity':
                    mid=key[7:];parent=self.native_parents.get(mid)
                    body+='\n\n_Native message `'+mid+'`'+(' · parent `'+parent+'`' if parent else '')+'_'
                chunks[cid+':'+str(epoch)+':'+key+':'+str(offset//2400)]=body
        previous=self.state/'last_quiet_seat.json'
        if previous.exists():
            old=json.loads(previous.read_text());old_id=old['conversation_id']
            chunks['previous-seat:'+old_id]='Earlier unconfirmed seat retained: `'+old_id+'` · <'+vis.get('ui_origin','http://localhost:3080')+'/c/'+old_id+'|Open earlier conversation>'
        sent=self.receipts.setdefault('messages',{})
        def priority(pair):
            key,text=pair
            return 0 if text.startswith('*Final')else 1 if '*Thinking*'in text else 2 if key=='status'else 3 if '*Reply*'in text else 4
        writes=0
        for key,text in sorted(chunks.items(),key=priority):
            if writes>=4:break
            digest=hashlib.sha256(text.encode()).hexdigest();old=sent.get(key)
            if old and old.get('digest')==digest:continue
            if old:
                self.send('conversations_edit_message',{'channel_id':channel,'ts':old['ts'],'text':text})
                old['digest']=digest
            else:
                result=self.send('conversations_add_message',{'channel_id':channel,'thread_ts':root,'text':text})
                match=re.search(r'ts[=:]\s*([0-9]+\.[0-9]+)',result)
                if not match:raise RuntimeError('Slack message acknowledgment has no identity')
                sent[key]={'ts':match.group(1),'digest':digest}
            # Keep cursor metadata bounded; source conversations remain elsewhere.
            while len(sent)>128:sent.pop(next(iter(sent)))
            self.receipts['last_published_at']=time.time();self.save();writes+=1

    def publish_loop(self):
        while not self.stop.is_set():
            try:
                self.publish()
                self.publish_history()
            except Exception as error:
                print(json.dumps({'component':'slack-visibility','error_type':type(error).__name__,'reason':str(error)[:160]}),flush=True)
                if self.slack:
                    self.slack.close();self.slack=None
            self.stop.wait(30)
        if self.slack:self.slack.close()

    def publish_history(self):
        """Keep observing prior admitted seats after the rotor advances, without resubmitting."""
        if not self.cfg().get('visibility',{}).get('enabled') or not self.receipts.get('thread_ts'):
            return
        directory=self.state/'admissions'
        if not directory.exists():return
        records=sorted(directory.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)
        candidates=[]
        for record in records:
            admission=json.loads(record.read_text())
            if admission.get('conversation_id')==self.conversation:continue
            root=self.state/'visibility-turns'/admission['conversation_id']
            receipt=root/'visibility.json'
            old=json.loads(receipt.read_text()) if receipt.exists()else{}
            if old.get('final_published'):continue
            candidates.append((admission,root))
            if len(candidates)>=64:break
        if not candidates:return
        admission,root=candidates[self.history_cursor%len(candidates)]
        self.history_cursor+=1
        root.mkdir(parents=True,exist_ok=True,mode=0o700)
        latest=root/'latest.json';latest.write_text(json.dumps(admission));latest.chmod(0o600)
        observer=Visibility(self.config,root,self.stop,self.authenticate,self.session)
        observer.conversation=admission['conversation_id']
        observer.generation=(admission.get('admission')or{}).get('generationCreatedAt')
        observer.receipts.update(thread_ts=self.receipts['thread_ts'],channel_id=self.receipts.get('channel_id'))
        try:
            if self.cfg().get('transport')=='omniroute':
                observer.parts={k:tuple(v)for k,v in admission.get('parts',{}).items()if v[1]}
                observer.status=admission.get('status','working')
                observer.publish()
                if observer.status=='completed':observer.receipts['final_published']=True
                observer.save()
                return
            observer.native_snapshot(observer.conversation)
            # Read the exact admitted assistant, not the latest global reply.
            response=observer.request('/api/messages/'+quote(observer.conversation,safe=''),timeout=15)
            if response.ok:
                value=response.json();messages=value if isinstance(value,list)else value.get('messages',[])
                for message in messages:
                    if message.get('messageId')!=admission.get('assistant_message_id'):continue
                    observer.snapshot({'aggregatedContent':message.get('content')or[]})
                    if message.get('text'):
                        observer.parts['application-reply']=('Reply',display_text(message['text'])[-65536:])
            observer.publish()
            if observer.status=='turn ended' and any(label=='Final reply' for label,text in observer.parts.values()):
                observer.receipts['final_published']=True
            observer.save()
        finally:
            if observer.slack:observer.slack.close()
