"""Concrete framed Unix transport; no science-result executor callbacks."""
import base64
import os
import socket
import stat
import struct
from pathlib import Path
from .wire import need, integer, token, encode, decode, body_pin, pin, check_pin, Cleanup
from .store import read_exact

METHOD_CUTOFF={'read_committed_program':'scientific','stage_exact':'scientific','launch_exact':'scientific',
    'read_closed_output':'scientific','commit_all_programs':'scientific','close_job':'closeout',
    'close_dispatch':'closeout','record_failure':'closeout'}
METHOD_CUTOFF.update({'read_committed_observed':'scientific','stage_observed':'scientific',
                     'launch_observed':'scientific','read_observed_output':'scientific','finish_transport':'closeout'})

def deployment(path, expected, ledger, role):
    # A deployment file must itself be selected independently by the owner.
    # Its semantic/issuer authentication is an external deployment obligation,
    # not established by the digest comparison below. The shipped file refuses.
    raw=read_exact(path,expected,ledger,65536);d=decode(raw,65536)
    need(d.get('execution_enabled') is True and d.get('independently_installed') is True,
         'production deployment is not independently installed')
    required={'schema','execution_enabled','independently_installed','provider_endpoint','observer_endpoint',
              'runtime_source_environment_admission','spend_authority','peers','max_message_bytes',
              'authority_receipt','source_digest','investigator'}
    need(set(d)==required and d['schema']=='ach_transport_deployment_v1','exact deployed transport policy')
    need(d['provider_endpoint']!=d['observer_endpoint'],'separate provider and observer endpoints')
    check_pin(d['runtime_source_environment_admission']);check_pin(d['authority_receipt'])
    need(type(d['peers']) is dict and set(d['peers'])=={'provider','observer'},'role-specific independently admitted peers')
    for peer in d['peers'].values():
        need(type(peer) is dict and set(peer)=={'uid','pid'},'peer fields');integer(peer['uid']);integer(peer['pid'],1)
    need(d['peers']['provider']['pid']!=d['peers']['observer']['pid'],'independent observer process')
    integer(d['max_message_bytes'],1)
    need(type(d['source_digest']) is str and len(d['source_digest'])==64,'deployed source digest')
    selected=d[role+'_endpoint'];need(type(selected) is str and Path(selected).is_absolute(),'fixed absolute endpoint')
    return d

def peer_identity(sock):
    if hasattr(socket,'SO_PEERCRED'):
        pid,uid,gid=struct.unpack('3i',sock.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
        return {'pid':pid,'uid':uid,'gid':gid}
    # UID-only getpeereid cannot prove the independently selected server PID.
    raise ValueError('full Unix peer PID credentials unavailable; no UID-only downgrade')

def receive(sock, n, ledger, deadline, cutoff='scientific'):
    integer(n);parts=[];left=n
    while left:
        ledger.tick(cutoff);remaining=(deadline-ledger.clock())/1e9;need(remaining>0,'original socket cutoff')
        extent=min(left,65536);ledger.reserve({'read_bytes':extent},'attempted bounded socket read',cutoff=cutoff)
        sock.settimeout(remaining);block=sock.recv(extent);need(block,'unexpected framed EOF')
        parts.append(block);left-=len(block)
    return b''.join(parts)

class Client:
    role=None
    def __init__(self, endpoint, deployment_path, deployment_pin, ledger):
        self.ledger=ledger;self.admission=deployment(deployment_path,deployment_pin,ledger,self.role)
        need(endpoint==self.admission[self.role+'_endpoint'],'same admitted endpoint')
        self.endpoint=endpoint;self.serial=0

    def request(self, method, payload, origin, deadline, *, cutoff=None):
        need(origin==self.ledger.origin and deadline==self.ledger.scientific,'original transport interval')
        need(method in METHOD_CUTOFF and (cutoff is None or cutoff==METHOD_CUTOFF[method]),'fixed method cutoff')
        cutoff=METHOD_CUTOFF[method];end=self.ledger.scientific if cutoff=='scientific' else self.ledger.closeout
        self.ledger.tick(cutoff);self.serial+=1;cap=self.admission['max_message_bytes']
        request={'schema':'ach_supervisor_request_v1','role':self.role,'method':method,'sequence':self.serial,
                 'origin_ns':origin,'scientific_deadline_ns':deadline,'source_digest':self.admission['source_digest'],
                 'closeout_deadline_ns':self.ledger.closeout,'outer_deadline_ns':self.ledger.outer,
                 'authority_receipt':self.admission['authority_receipt'],'payload':payload}
        raw=encode(request,cap);self.ledger.reserve({'requests':1,'write_bytes':len(raw)+8},'supervisor request',cutoff=cutoff)
        with self.ledger.live(3*cap+len(raw),'bounded request/reply',cutoff=cutoff):
            status=os.stat(self.endpoint,follow_symlinks=False);need(stat.S_ISSOCK(status.st_mode),'ordinary admitted Unix socket')
            with Cleanup(self.ledger) as cleanup:
                sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
                cleanup.defer('close transport client socket',sock.close)
                sock.settimeout(max(.001,(end-self.ledger.clock())/1e9));sock.connect(self.endpoint)
                identity=peer_identity(sock)
                need(identity['uid']==self.admission['peers'][self.role]['uid'] and identity['pid']==self.admission['peers'][self.role]['pid'],
                     'exact independently admitted supervisor peer')
                self.ledger.tick(cutoff);sock.sendall(struct.pack('!Q',len(raw))+raw)
                size=struct.unpack('!Q',receive(sock,8,self.ledger,end,cutoff))[0];need(size<=cap,'reply extent before read')
                reply=decode(receive(sock,size,self.ledger,end,cutoff),cap)
                need(set(reply)=={'request_pin','source_digest','sequence','status','payload'} and
                     reply['request_pin']==body_pin(raw) and reply['source_digest']==self.admission['source_digest'] and
                     reply['sequence']==self.serial,'exact source-bound request/reply identity')
                need(reply['status']=='ok','supervisor refused: '+str(reply['payload'])[:512])
                self.ledger.tick(cutoff);return reply['payload']

    def finish_transport(self):
        return self.request('finish_transport',{},self.ledger.origin,self.ledger.scientific)

class ProviderClient(Client):
    role='provider'
    def read_committed_program(self, descriptor):
        result=self.request('read_committed_program',{'descriptor':descriptor},self.ledger.origin,self.ledger.scientific)
        need(set(result)=={'body_base64'},'exact source reply');raw=base64.b64decode(result['body_base64'],validate=True)
        need(body_pin(raw)=={k:descriptor[k] for k in ('bytes','sha256')},'committed source body');return raw
    def stage_exact(self, context, files, view, binding, origin, deadline):
        token(context);need(type(files) is dict and all(type(v) is bytes for v in files.values()),'exact source files')
        extent=sum(4*((len(v)+2)//3) for v in files.values());need(extent<=self.admission['max_message_bytes'],'staged base64 extent')
        self.ledger.reserve({'read_bytes':sum(map(len,files.values()))},'staged source encoding')
        with self.ledger.live(2*extent,'staged source base64'):
            encoded={k:base64.b64encode(v).decode('ascii') for k,v in files.items()}
            result=self.request('stage_exact',{'context':context,'files_base64':encoded,'view':view,'binding':binding},origin,deadline)
        need(set(result)=={'context','binding','token'} and result['context']==context and result['binding']==binding,'staged token identity')
        return result['token']
    def launch_exact(self, stage_token, argv, binding, origin, deadline):
        result=self.request('launch_exact',{'token':stage_token,'argv':argv,'binding':binding},origin,deadline)
        need(type(result) is dict and set(result)=={'index'},'exact index result');return result
    def read_closed_output(self, context, name, offset, count):
        integer(offset);integer(count)
        result=self.request('read_closed_output',{'context':context,'name':name,'offset':offset,'count':count},
                            self.ledger.origin,self.ledger.scientific)
        need(set(result)=={'body_base64'},'output byte response');raw=base64.b64decode(result['body_base64'],validate=True)
        need(len(raw)<=count,'bounded returned output');return raw

class ObserverClient(Client):
    role='observer'
    def commit_all_programs(self, freeze, origin, deadline):
        return self.request('commit_all_programs',{'freeze':freeze},origin,deadline)
    def close_job(self, context, job_id, result, primary, binding, origin, deadline):
        error=None if primary is None else {'type':type(primary).__name__,'message':str(primary)[:1024]}
        return self.request('close_job',{'context':context,'job_id':job_id,'result':result,'primary':error,'binding':binding},origin,deadline)
    def close_dispatch(self, binding, origin, deadline):
        return self.request('close_dispatch',{'binding':binding},origin,deadline)
    def record_failure(self, binding, descriptor, completed_prefix, origin, deadline):
        return self.request('record_failure',{'binding':binding,'descriptor':descriptor,'completed_prefix':completed_prefix},
                            origin,deadline,cutoff='closeout')
