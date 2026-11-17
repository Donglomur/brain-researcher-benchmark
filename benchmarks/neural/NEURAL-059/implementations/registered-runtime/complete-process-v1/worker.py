"""Restricted worker dispatcher; scientific/candidate imports happen only in-role."""
import base64
import os
from pathlib import Path
import socket
import struct
import time
from .core import need, keys, parse, encode, pin, read, decode_body, source_body


def send(conn, value, cap):
    raw=encode(value); need(len(raw)<=cap,'whole worker response cap before publication')
    wire=struct.pack('!I',len(raw))+raw; offset=0
    while offset<len(wire):
        n=conn.send(wire[offset:]); need(n>0,'worker frame progress'); offset+=n


def receive(conn, cap):
    body=bytearray(); end=4
    while len(body)<end:
        block=conn.recv(min(65536,end-len(body))); need(block,'complete owner request')
        body.extend(block)
        if len(body)==4:
            n=struct.unpack('!I',body)[0]; need(0<n<=cap,'bounded whole worker input'); end=4+n
    return parse(bytes(body[4:]))


class Actor:
    def __init__(self, boot):
        self.boot=boot; self.payload=boot['payload']; self.fitted=False; self.inferred=False
        self.cap=boot['role_limits']['artifact_bytes']; self.source=None

    def module(self, body):
        need(type(body) is bytes and 0<len(body)<=self.cap,'exact bounded selected candidate source')
        scope={'__name__':'n059_selected_candidate','__file__':'<actual captured N059 candidate>'}
        exec(compile(body,scope['__file__'],'exec'),scope)
        return scope

    def fit(self, payload, tools):
        need(not self.fitted and self.boot['role']=='actor','single original calibration fit')
        policy=read('/input/policy.py',self.cap)
        need(pin(policy)==self.payload['policy_pin'],'loaded policy equals frozen pre-exposure capture')
        source=self.module(policy)
        out=source['fit'](self.payload['calibration'],tools)
        keys(out,('source_body','config_body','state_body'))
        need(all(type(out[k]) is bytes and 0<len(out[k])<=self.cap for k in out),'actual complete fitted artifacts')
        if self.payload['arm']=='F': need(out['source_body']==policy,'F source fixed before every value')
        self.source={k:source_body(v) for k,v in out.items()}; self.fitted=True
        return self.source

    def predict(self,payload,tools):
        need(not self.inferred and self.boot['role']=='actor_predict','one current case per fresh process')
        keys(payload,('view',)); need('y' not in payload['view'],'no held target in candidate request')
        artifacts=self.payload['artifacts']
        bodies={k:decode_body(v,self.cap) for k,v in artifacts.items()}
        keys(bodies,('source_body','config_body','state_body'))
        policy=self.module(bodies['source_body'])
        p=policy['predict'](payload['view'],bodies['config_body'],bodies['state_body'],tools)
        from .scientific.contracts import probability
        self.inferred=True
        return {'p':probability(p),'artifacts':{k:pin(v) for k,v in bodies.items()}}


def serve(boot):
    need(boot['schema']=='n059_worker_boot_v1','selected exact worker boot')
    kind=boot['role']; cap=boot['role_limits']; worker=None; sequence=0; closed=False
    socket_path=Path('/channel/rpc.sock')
    need(os.getuid()==65534 and os.getgid()==65534 and not socket_path.exists(),'fresh nonroot worker channel')
    work_fs=os.statvfs('/work'); channel_fs=os.statvfs('/channel')
    need(0<work_fs.f_blocks*work_fs.f_frsize<=cap['tmpfs_bytes'] and
         0<work_fs.f_files<=cap['work_files'] and
         0<channel_fs.f_blocks*channel_fs.f_frsize<=cap['channel_bytes'] and
         0<channel_fs.f_files<=cap['channel_files'], 'actual worker work/channel byte and inode ceilings')
    server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    server.bind(str(socket_path)); os.chmod(socket_path,0o600); server.listen(1)
    server.settimeout(max(.001,boot['deadline']-time.monotonic()))
    try:
        while not closed:
            need(time.monotonic()<boot['deadline'],'complete original worker lifetime')
            conn,_=server.accept()
            with conn:
                pid,uid,gid=struct.unpack('3i',conn.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                need(uid==0,'owner-only root peer; no candidate-to-candidate channel')
                conn.settimeout(max(.001,boot['deadline']-time.monotonic()))
                req=receive(conn,cap['request_bytes']); sequence+=1
                keys(req,('sequence','operation','payload','selection_identity'))
                need(req['sequence']==sequence and req['selection_identity']==boot['selection_identity'],
                     'same frozen study and chronological request')
                operation=req['operation']; payload=req['payload']
                class Tools:
                    def model(self,request):
                        need(kind in ('actor','actor_predict'),'only actor model capability')
                        send(conn,{'sequence':sequence,'kind':'model','request':request},cap['response_bytes'])
                        reply=receive(conn,cap['request_bytes'])
                        need(reply.get('sequence')==sequence and reply.get('kind')=='model_result','actual owner model return')
                        return reply['result']
                try:
                    if operation=='close':
                        result=worker.close() if kind=='reference' and worker is not None else {'closed':True}
                        if kind=='reference':
                            need(result.get('object_handles_closed') is True and not result.get('closure_errors'),
                                 'all original reference handles closed before successful retirement')
                        result={**result,'closed':True,'process_exit_verified':False}; closed=True
                    elif kind in ('actor','actor_predict'):
                        if worker is None: worker=Actor(boot)
                        need(operation==('fit' if kind=='actor' else 'predict'),'exact actor phase')
                        result=getattr(worker,operation)(payload,Tools())
                    elif kind=='reference':
                        from .reference_worker import ReferenceWorker
                        if worker is None:
                            need(operation=='fit','reference construction precedes inference')
                            worker=ReferenceWorker({**boot['payload'],'native_authorization':payload['authorization']})
                        need(operation in ('fit','infer'),'reference fixed fit/inference operations')
                        result=worker.fit() if operation=='fit' else worker.infer(payload)
                    elif kind=='model':
                        from .local_model import ResidentModel
                        if operation=='initialize':
                            need(worker is None and payload=={},'one arm-owned resident initialization')
                            worker=ResidentModel(boot['payload']['configuration'])
                            result={'initialized':True,'arm':boot['payload']['arm'],'qualification':False}
                        else:
                            need(operation=='generate' and worker is not None,'initialized resident model')
                            keys(payload,('owner','request','call_deadline'))
                            need(payload['owner']['arm']==boot['payload']['arm'] and
                                 payload['owner']['condition'] in ('SH','SHN','SBH','SBHN') and
                                 type(payload['owner']['session_id']) is str and
                                 time.monotonic()<payload['call_deadline']<=boot['deadline'],
                                 'explicit request owner and original bounded call')
                            result={'owner':payload['owner'],**worker.generate(payload['request'],payload['call_deadline'])}
                    elif kind=='grade':
                        need(operation in ('primary','diagnostic') and worker is None,'one protected model-free grade')
                        from .scientific import evaluation
                        if operation=='primary':
                            result=evaluation.score_panel(payload['prepared'],payload['predictions'],
                                                          expected_methods=payload['methods'])
                        else:
                            result=evaluation.score_diagnostic_change(payload['prepared'],payload['primary'],
                                payload['diagnostic'],primary_methods=payload['primary_methods'],
                                diagnostic_methods=payload['diagnostic_methods'],tag=payload['tag'],replicate=payload['replicate'])
                        worker=True
                    else: need(False,'closed worker role set')
                    send(conn,{'sequence':sequence,'kind':'result','result':result},cap['response_bytes'])
                except BaseException as error:
                    failure={'type':type(error).__name__,'message':str(error),'physical_exit_verified':False}
                    if kind=='reference' and worker is not None:
                        failure['reference_failure_records']=worker.failure_records
                        failure['reference_fit_records']=worker.fit_records
                        failure['reference_inference_records']=[] if worker.runtime is None else worker.runtime.inference_records
                    try:
                        send(conn,{'sequence':sequence,'kind':'error','failure':failure},cap['response_bytes'])
                    except BaseException as secondary:
                        error.add_note('Bounded failure transport also failed: '+type(secondary).__name__)
                    raise

    finally:
        server.close()
        # The host must separately observe natural process exit and entire
        # cgroup absence. This unlink is not a completion certificate.
        socket_path.unlink(missing_ok=True)
