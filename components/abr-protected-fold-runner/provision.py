"""Render one source-locked ABR owner. This never dispatches a process or reads data.

Run with an explicitly pinned metadata request. The generated selection is false
and contains empty review locators. Source review, native runtime review and fresh
capacity admission are external prerequisites; generation proves none of them.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat

ROOT = Path(__file__).absolute().parent
LIMITS = {'active_seconds':7200,'whole_seconds':7320,'outer_seconds':7350,
          'per_fold_seconds':600,'container_memory_bytes':2147483648,
          'container_cpus':1,'host_rss_bytes':1073741824,
          'managed_read_bytes':21474836480,'retained_bytes':8589934592,
          'model_calls':0,'contexts':10}
VERSIONS = {'python':'3.12.8','numpy':'2.2.6','scipy':'1.15.3','scikit-learn':'1.6.1'}
MODULES = ('builder','common','docker_owner','durable_evidence','fold_context',
           'fold_runner','outer_once','packet','prepared_manifest','run_once','runner_config','score','split')
MEMBERS = {'TASK.md','SUBMISSION_SCHEMA.json',*(f'runtime/{n}.py' for n in MODULES)}

def require(value, message):
    if not value: raise ValueError(message)

def encode(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def decode(raw):
    def pairs(rows):
        out={}
        for k,v in rows:
            require(k not in out,'duplicate JSON key');out[k]=v
        return out
    def bad(x):raise ValueError('nonfinite JSON constant')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)

def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def plain(value):
    require(type(value) is str and value and not any(x in value for x in (',','\n','\r','\0')),
            'plain metadata path, no Docker mount separators')
    p=Path(value)
    require(p.is_absolute() and '..' not in p.parts and str(p)==value and
            not any(x.is_symlink() for x in (p,*p.parents)),'canonical ordinary absolute path')
    return p

def entry(e,cap):
    require(type(e) is dict and set(e)=={'path','bytes','sha256'},'closed operand locator')
    plain(e['path'])
    require(type(e['bytes']) is int and 0<e['bytes']<=cap and
            type(e['sha256']) is str and re.fullmatch('[0-9a-f]{64}',e['sha256']),'exact operand pin')

def read(path,cap):
    p=plain(str(path));fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=cap,'ordinary metadata file')
        chunks=[];left=before.st_size
        while left:
            chunk=os.read(fd,min(left,65536));require(chunk,'complete metadata');chunks.append(chunk);left-=len(chunk)
        keys=('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
        after=os.fstat(fd);named=p.lstat()
        require(all(getattr(before,k)==getattr(after,k)==getattr(named,k) for k in keys),'stable metadata file')
        return b''.join(chunks)
    finally:os.close(fd)

def write(path,raw):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        at=0
        while at<len(raw):
            n=os.write(fd,raw[at:]);require(n>0,'complete write');at+=n
        os.fsync(fd);os.fchmod(fd,0o400)
    finally:os.close(fd)
    return {'path':str(path),**pin(raw)}

def replace_once(raw,old,new):
    require(raw.count(old.encode())==1,'exact reviewed template seam')
    return raw.replace(old.encode(),new.encode())

def render(request, *, source_root=ROOT):
    require(type(request) is dict and set(request)=={'schema','package_root','operation_root','attempt_id',
            'image','daemon_socket','daemon_guard','host_python','operands'},'closed render request')
    require(request['schema']=='abr_fold_render_request_v1','render request schema')
    package=plain(request['package_root']);operation=plain(request['operation_root'])
    py=plain(request['host_python']);socket=plain(request['daemon_socket'])
    require(type(request['attempt_id']) is str and re.fullmatch('[a-z0-9][a-z0-9-]{0,63}',request['attempt_id']),'attempt ID')
    require(type(request['image']) is str and re.fullmatch('sha256:[0-9a-f]{64}',request['image']),'actual immutable image required')
    guard=request['daemon_guard']
    require(type(guard) is dict and set(guard)=={'dev','inode','mode','uid','gid','nlink'} and
            all(type(x) is int and x>=0 for x in guard.values()) and
            stat.S_ISSOCK(guard['mode']) and guard['nlink']>=1,'selected socket identity metadata')
    operands=request['operands']
    require(type(operands) is dict and set(operands)=={'packet_root','completion','manifest','preparation','programs'},'closed data operands')
    packet=plain(operands['packet_root'])
    for n in ('completion','manifest','preparation'):entry(operands[n],1048576)
    require(operands['completion']['path']==str(packet/'evaluator/PACKET_COMPLETION.json') and
            operands['manifest']['path']==str(packet/'evaluator/PRIVATE_MANIFEST.json') and
            operands['preparation']['path']==str(packet/'evaluator/PREPARATION_RECEIPT.json'),'fixed evaluator paths')
    require(type(operands['programs']) is dict and set(operands['programs'])=={'candidate','layout_only'},'two methods')
    for e in operands['programs'].values():entry(e,262144)
    # No parent/child alias can make source construction overwrite, enter or
    # mount a private packet. Existing program paths are read only during a later
    # selected run, never here. Program provenance remains an operator obligation.
    for a,b in ((package,operation),(package,packet),(operation,packet)):
        require(a!=b and a not in b.parents and b not in a.parents,'disjoint roots')
    require(not package.exists() and not operation.exists(),'exclusive fresh render roots')
    source_root=plain(str(source_root));bodies={}
    for n in sorted(MEMBERS):bodies[n]=read(source_root/n,1048576)
    require(sum(map(len,bodies.values()))<2097152,'bounded source template closure')
    lock1=ast.literal_eval(next(node.value for node in ast.parse(bodies['runtime/run_once.py']).body
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='LOCK_MEMBERS' for t in node.targets)))
    lock2=ast.literal_eval(next(node.value for node in ast.parse(bodies['runtime/outer_once.py']).body
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='LOCK_MEMBERS' for t in node.targets)))
    require(lock1==lock2==MEMBERS|{'CONFIG.json'},'both actual owner closures')
    b=bodies['runtime/docker_owner.py']
    b=replace_once(b,"IMAGE='UNSELECTED_ABR_RUNTIME'","IMAGE="+repr(request['image']))
    b=replace_once(b,"DAEMON_SOCKET=Path('/OWNER/runtime/docker.sock')","DAEMON_SOCKET=Path("+repr(str(socket))+")")
    b=replace_once(b,'DAEMON_GUARD=None','DAEMON_GUARD='+repr(guard))
    bodies['runtime/docker_owner.py']=b
    for n in ('run_once','outer_once'):
        key='runtime/'+n+'.py'
        bodies[key]=replace_once(bodies[key],"EXTERNAL=Path('/OWNER/operation')","EXTERNAL=Path("+repr(str(operation))+")")
    bodies['runtime/outer_once.py']=replace_once(bodies['runtime/outer_once.py'],
        "'/OWNER/runtime/python3.11'",repr(str(py)))
    for n,b in bodies.items():
        if n.endswith('.py'):compile(b,str(package/n),'exec')
    cfg={'schema':'abr_fold_owner_configuration_v1','image':request['image'],
         'daemon_socket':str(socket),'daemon_guard':guard,'runtime_versions':VERSIONS,
         'budget':LIMITS,'operands':operands}
    bodies['CONFIG.json']=encode(cfg)
    lock={'schema':'abr_fold_whole_owner_lock_v1','members':{n:pin(b) for n,b in sorted(bodies.items())}}
    package.mkdir(mode=0o700);(package/'runtime').mkdir(mode=0o700)
    operation.mkdir(mode=0o700)
    for n in ('attempts','selections'):(operation/n).mkdir(mode=0o700)
    output=[]
    for n,b in sorted(bodies.items()):output.append(write(package/n,b))
    lockpin=write(package/'EXECUTION_LOCK.json',encode(lock));output.append(lockpin)
    template={'schema':'abr_protected_fold_whole_run_v1','attempt_id':request['attempt_id'],
       'selection':{'root_execution_selected':False,**operands,'budget':LIMITS,
         'runtime_evidence':{'source_review':None,'runtime_review':None,'fresh_capacity':None}}}
    output.append(write(package/'UNSELECTED_RUN.json',encode(template)))
    output.append(write(package/'SOURCE_REVIEW_REQUEST.json',encode({
        'schema':'abr_fold_source_review_v1','whole_source_accepted':False,'members':lock['members']})))
    for p in (package/'runtime',package):os.chmod(p,0o500)
    return {'schema':'abr_fold_render_result_v1','dispatch_performed':False,
            'execution_lock':lockpin,'files':output,
            'required_selection_path':str(operation/'selections'/(request['attempt_id']+'.json')),
            'prospective_outer_argv':[str(py),'-I','-S','-B',str(package/'runtime/outer_once.py'),
                '--source-lock-sha256',lockpin['sha256'],
                '--run-manifest-sha256','REPLACE_WITH_ACCEPTED_SELECTION_SHA256',
                '--attempt-id',request['attempt_id']]}

def main():
    p=argparse.ArgumentParser();p.add_argument('--request',required=True)
    p.add_argument('--request-sha256',required=True);args=p.parse_args()
    raw=read(plain(args.request),65536)
    require(pin(raw)['sha256']==args.request_sha256,'selected render request hash')
    print(encode(render(decode(raw))).decode(),end='')

if __name__=='__main__':main()
