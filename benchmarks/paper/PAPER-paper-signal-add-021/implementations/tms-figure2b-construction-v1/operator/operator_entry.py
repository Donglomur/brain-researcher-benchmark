#!/usr/bin/env python3
"""Task-local source inspection and explicit-operand paired execution CLI."""
import argparse,hashlib,json,os,stat,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).absolute().parent

def inspect_source():
    deadline=time.monotonic()+10;total=0
    if any(x.is_symlink() for x in [ROOT,*ROOT.parents]):raise ValueError('ordinary source root and ancestors')
    def read(path,cap):
        nonlocal total
        if time.monotonic()>=deadline:raise ValueError('source-inspection deadline')
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            st=os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1 or st.st_size>cap:raise ValueError('ordinary bounded source')
            total+=st.st_size
            if total>4*2**20:raise ValueError('source-inspection byte cap')
            with os.fdopen(fd,'rb',closefd=False) as stream:body=stream.read(st.st_size+1)
            after=os.fstat(fd)
            if len(body)!=st.st_size or (st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):raise ValueError('source changed')
            return body
        finally:os.close(fd)
    raw=read(ROOT/'OPERATOR_LOCK.json',1048576)
    def pairs(rows):
        d={}
        for k,v in rows:
            if k in d:raise ValueError('duplicate key')
            d[k]=v
        return d
    lock=json.loads(raw,object_pairs_hook=pairs)
    if set(lock)!={'schema','files','inherited_source_commit'} or lock['schema']!='tms_figure2b_operator_source_lock_v1':raise ValueError('source lock schema')
    if type(lock['files']) is not dict or not 15<len(lock['files'])<=2048:raise ValueError('complete source extent')
    actual=set();pending=[ROOT];entries=0
    while pending:
        if time.monotonic()>=deadline:raise ValueError('source inventory deadline')
        parent=pending.pop()
        with os.scandir(parent) as stream:
            for entry in stream:
                if time.monotonic()>=deadline:raise ValueError('source inventory deadline')
                entries+=1
                if entries>2048:raise ValueError('source entry cap including directories')
                path=parent/entry.name;rel=path.relative_to(ROOT)
                if len(rel.parts)>64 or entry.is_symlink():raise ValueError('source ancestry')
                if entry.is_dir(follow_symlinks=False):pending.append(path)
                elif rel.as_posix()!='OPERATOR_LOCK.json':actual.add(rel.as_posix())
    if actual!=set(lock['files']):raise ValueError('closed source inventory')
    for name,row in lock['files'].items():
        p=Path(name)
        if p.is_absolute() or '..' in p.parts or set(row)!={'bytes','sha256'} or type(row['bytes']) is not int:raise ValueError('source descriptor')
        body=read(ROOT/p,1048576)
        if len(body)!=row['bytes'] or hashlib.sha256(body).hexdigest()!=row['sha256']:raise ValueError('source pin')
    return {'schema':'tms_figure2b_operator_inspection_v1','source_files':len(lock['files']),
        'source_read_bytes':total,'scope':{'participants':15,'conditions':4,'output_fields':36,'paired_views':['paper+data','paper+data+code']},
        'source_only':True,'native_execution':False,'scientifically_qualified':False,
        'runtime':'explicit Linux cgroup-v2, pinned Harbor/Docker, quota-backed tmpfs and selected Responses configuration required',
        'authority':'no authority issuer; protected reference requires an external exact-plan grant'}

def admit_runtime_imports():
    """Require an explicit isolated startup and empty read-only cache namespace.

    The trusted operator provisions this prefix before launching Python. Immutable
    source/interpreter custody remains an independent runtime prerequisite.
    """
    if not (sys.flags.isolated and sys.flags.ignore_environment and sys.flags.dont_write_bytecode==1 and sys.dont_write_bytecode):
        raise ValueError('runtime requires -I -B and explicit -X pycache_prefix')
    if any(name in ('tms_operator','tms_figure') or name.startswith(('tms_operator.','tms_figure.')) for name in sys.modules):
        raise ValueError('fresh project import namespace required')
    if type(sys.pycache_prefix) is not str or sys._xoptions.get('pycache_prefix')!=sys.pycache_prefix:raise ValueError('explicit runtime -X cache prefix')
    prefix=Path(sys.pycache_prefix)
    if not prefix.is_absolute() or str(prefix)!=os.path.normpath(str(prefix)):
        raise ValueError('literal runtime cache prefix')
    if prefix==ROOT or prefix.is_relative_to(ROOT):raise ValueError('cache prefix outside source')
    if any(x.is_symlink() for x in [prefix,*prefix.parents]):raise ValueError('cache prefix aliases')
    st=prefix.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid!=os.geteuid() or stat.S_IMODE(st.st_mode)!=0o500:
        raise ValueError('operator-owned read-only cache prefix')
    with os.scandir(prefix) as entries:
        if next(entries,None) is not None:raise ValueError('fresh empty runtime cache namespace')
    sys.path.insert(0,str(ROOT))

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inspect',action='store_true')
    p.add_argument('action',nargs='?',choices=['stage','run-pair','grade-pair'])
    for name in ['request','request-sha256']:p.add_argument('--'+name)
    for name in ['request-bytes','read-bytes','write-bytes','max-output-bytes']:p.add_argument('--'+name,type=int)
    p.add_argument('--seconds',type=float);a=p.parse_args(argv)
    if a.inspect:
        if a.action is not None or any(getattr(a,n) is not None for n in ('request','request_sha256','request_bytes','read_bytes','write_bytes','max_output_bytes','seconds')):p.error('inspection accepts only --inspect')
        print(json.dumps(inspect_source(),sort_keys=True));return
    if a.action is None or any(getattr(a,n) is None for n in ('request','request_sha256','request_bytes','read_bytes','write_bytes','max_output_bytes','seconds')):p.error('all request pin and resource operands are required')
    inspect_source() # source-only fixed cap, distinct from the explicit runtime budget
    admit_runtime_imports() # Before the first project import; -B alone still reads caches.
    from tms_operator.schema import Budget,load,keys,require,integer,bounded_json
    from tms_operator import operator
    budget=Budget(a.read_bytes,a.write_bytes,a.seconds);integer(a.max_output_bytes)
    req=load(a.request,{'bytes':a.request_bytes,'sha256':a.request_sha256},budget)
    if a.action=='stage':
        names={'schema','stage_root','selections','capsule_path','capsule_pin','runtime_path','runtime_pin','qualification_path','qualification_pin','resource_limits','trials','absolute_tolerance','relative_tolerance','tolerance_justification','operator_lock_pin','source_lock_pin'}
        keys(req,names);require(req['schema']=='tms_figure2b_stage_request_v1','stage request')
        result=operator.stage_pair(**{k:v for k,v in req.items() if k!='schema'},budget=budget)
    elif a.action=='run-pair':
        keys(req,{'schema','stage','execution_plan'});require(req['schema']=='tms_figure2b_run_request_v1','run request')
        result=operator.run_pair(stage=req['stage'],execution_plan_pin=req['execution_plan'],budget=budget)
    else:
        keys(req,{'schema','stage','request','authority','metadata_read_reservation'});keys(req['authority'],{'path','pin'})
        require(req['schema']=='tms_figure2b_grade_request_operand_v1','grade request')
        result=operator.grade_pair(stage=req['stage'],request_pin=req['request'],authority_path=req['authority']['path'],authority_pin=req['authority']['pin'],metadata_read_reservation=req['metadata_read_reservation'],budget=budget)
    body=bounded_json(result,a.max_output_bytes);budget.charge(write=2*len(body));sys.stdout.buffer.write(body+b'\n')

if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'state':'refused','error_type':type(error).__name__,'scientifically_qualified':False}),file=sys.stderr)
        raise SystemExit(1)
