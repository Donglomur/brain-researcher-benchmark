"""Selected full8 public-input investigation producer and support admission; numerical grade separate."""
import time
ORIGIN = time.monotonic()
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import types

HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[3]
READ_CAP = 500000


def need(ok, message):
    if not ok: raise ValueError(message)


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate metadata key'); result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda _: need(False,'nonfinite metadata'))


def pin(raw): return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def descriptor(value, cap=32768):
    need(type(value) is dict and set(value)=={'bytes','sha256'}
        and type(value['bytes']) is int and 0<value['bytes']<=cap
        and type(value['sha256']) is str and len(value['sha256'])==64
        and all(c in '0123456789abcdef' for c in value['sha256']), 'exact bounded descriptor')
    return value


def literal(value):
    need(type(value) is str and 0<len(value.encode())<=512
        and not any(c in value for c in '\0\r\n,'),'bounded literal path')
    p=Path(value)
    need(p.is_absolute() and '..' not in p.parts and str(p)==value
        and not any(x.is_symlink() for x in (p,*p.parents)),'canonical unlinked path')
    return p


class Captures:
    def __init__(self,end): self.end=end; self.read_bytes=0
    def tick(self):need(time.monotonic()<self.end,'original startup/whole clock')
    def read(self,path,cap,expected=None):
        self.tick();p=literal(str(path));self.tick()
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            a=os.fstat(fd)
            need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and 0<a.st_size<=cap,'ordinary bounded metadata/source')
            if expected is not None:need(a.st_size==descriptor(expected,cap)['bytes'],'source extent')
            charge=a.st_size+1;need(self.read_bytes+charge<=READ_CAP,'adapter read reservation cap');self.read_bytes+=charge
            self.tick()
            with os.fdopen(fd,'rb',closefd=False) as f:raw=f.read(charge)
            keys=('st_dev','st_ino','st_mode','st_nlink','st_size','st_uid','st_gid','st_mtime_ns','st_ctime_ns')
            need(len(raw)==a.st_size and all(getattr(a,k)==getattr(os.fstat(fd),k)==getattr(p.lstat(),k) for k in keys),'stable captured object')
            need(expected is None or pin(raw)==expected,'exact captured pin');self.tick();return raw
        finally:os.close(fd)


def own(captures,expected):
    raw=captures.read(HERE/'SOURCE_MANIFEST.json',32768,descriptor(expected));m=parse(raw)
    need(set(m)=={'schema','files'} and m['schema']=='neural078_full8_central_adapter_source_v1'
        and set(m['files'])=={'adapter.py','BINDING.json','README.md'},'exact adapter source closure')
    return {n:captures.read(HERE/n,50000,descriptor(q,50000)) for n,q in m['files'].items()}


def loaded(raw,name,path,**bindings):
    m=types.ModuleType(name);m.__file__=str(path);m.__dict__.update(bindings);exec(compile(raw,str(path),'exec'),m.__dict__);return m


def binding(args,captures,source_pin,b):
    need(type(args.other_reserve_bytes)is int and args.other_reserve_bytes>=0,'fresh explicit OTHER')
    rp=literal(args.review);review_raw=captures.read(rp,32768);review=parse(review_raw)
    keys={'schema','task_id','approved','adapter_source','selection','external_output','authoring_context_id','source_exposure','numeric_grade_authorized','adapter_additional_read_cap','adapter_additional_retained_bytes'}
    need(type(review)is dict and set(review)==keys,'exact root-selected review')
    need(review['schema']=='neural078_full8_central_review_v1' and review['task_id']=='NEURAL-078' and review['approved'] is True and review['numeric_grade_authorized'] is False,'full investigation producer; numerical grade unauthorized')
    need(descriptor(review['adapter_source'])==source_pin,'exact selected adapter source')
    need(type(review['authoring_context_id'])is str and 0<len(review['authoring_context_id'])<=512,'one-program root-attested context')
    need(json.dumps(review['source_exposure'],sort_keys=True,separators=(',',':'))==json.dumps(dict(condition='full8_investigation',agent_mode='frozen_program',public_files=15,primitive_files=8,private_source_visible=False,source_history_attested_by_root=True),sort_keys=True,separators=(',',':')),'exact externally attested public-only exposure')
    need(review['source_exposure']['private_source_visible'] is False and review['source_exposure']['source_history_attested_by_root'] is True,'strict exposure attestation booleans')
    need(type(review['adapter_additional_read_cap'])is int and review['adapter_additional_read_cap']==READ_CAP and type(review['adapter_additional_retained_bytes'])is int and review['adapter_additional_retained_bytes']==0,'explicit additive adapter budget')
    selected=review['selection'];need(type(selected)is dict and set(selected)=={'path','bytes','sha256'},'exact selected original descriptor')
    path=literal(selected['path']);sp=descriptor({k:selected[k] for k in ('bytes','sha256')})
    s=parse(captures.read(path,32768,sp))
    directory=ROOT/b['directory'];manifest=parse(captures.read(directory/'SOURCE_MANIFEST.json',32768,b['source']))
    need(manifest['schema']=='neural078_full8_program_source_v1' and len(manifest['files'])==13,'complete original source format')
    for name,key in [('common.py','common'),('policy.py','policy'),('observe.py','observer')]:need(manifest['files'][name]==b[key],'source-bound original interface')
    common=loaded(captures.read(directory/'common.py',10000,b['common']),'pinned078_common',directory/'common.py')
    policy=loaded(captures.read(directory/'policy.py',10000,b['policy']),'pinned078_policy',directory/'policy.py',c=common)
    policy.selection(s,b['source'])
    need(s['repository']==str(ROOT),'same central repository')
    need(type(s['other_future_bytes'])is int and s['other_future_bytes']==args.other_reserve_bytes,'same fresh outside custody')
    need(literal(s['program']['path'])==literal(args.program) and literal(s['output'])==literal(args.output),'same candidate/output operands')
    need(s['scope']==b['scope'] and s['support_admission_authorized'] is True and s['numeric_grading_authorized'] is False,'full8 public-schema-only producer')
    out=literal(review['external_output']);owner=literal(s['output'])
    need(out!=owner and owner not in out.parents and out not in owner.parents and not os.path.lexists(out) and not os.path.lexists(owner),'fresh separate receipt/attempt')
    need(not os.path.lexists(str(out)+'.UNUSED-PYCACHE'),'fresh original worker cache')
    return dict(review_path=rp,review_pin=pin(review_raw),selection_path=path,selection_pin=sp,selection=s,external_output=out,whole_seconds=policy.whole(s['candidate_seconds']))

def invoke(captures,b,admitted):
    directory=ROOT/b['directory'];raw=captures.read(directory/'observe.py',20000,b['observer'])
    observer=loaded(raw,'pinned078_full8_observer',directory/'observe.py')
    observer.ORIGIN=ORIGIN
    previous=sys.argv
    try:
        sys.argv=[str(directory/'observe.py'),'--source-pin',json.dumps(b['source']),
            '--selection',str(admitted['selection_path']),'--selection-pin',json.dumps(admitted['selection_pin']),
            '--external-output',str(admitted['external_output'])]
        captures.tick();return observer.main()
    finally:sys.argv=previous


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source-sha256','program','output','review'):parser.add_argument('--'+name,required=True)
    for name in ('source-bytes','other-reserve-bytes'):parser.add_argument('--'+name,required=True,type=int)
    args=parser.parse_args(argv);saved={};armed=False;result=2;end=ORIGIN+120;success_end=end;restore_errors=[]
    try:
        need(signal.getitimer(signal.ITIMER_REAL)==(0.,0.),'no inherited timer')
        saved={s:signal.getsignal(s) for s in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT)}
        def stop(*_):raise TimeoutError('original startup/whole deadline or stop')
        for s in saved:signal.signal(s,stop)
        need(time.monotonic()<end,'original startup clock');signal.setitimer(signal.ITIMER_REAL,end-time.monotonic());armed=True
        need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and sys.pycache_prefix,'isolated no-site no-write startup')
        cache=literal(sys.pycache_prefix);need(not os.path.lexists(cache),'fresh unused adapter cache')
        source_pin=descriptor({'bytes':args.source_bytes,'sha256':args.source_sha256});captures=Captures(end)
        bodies=own(captures,source_pin);b=parse(bodies['BINDING.json']);admitted=binding(args,captures,source_pin,b)
        whole=ORIGIN+admitted['whole_seconds'];end=whole+60;success_end=whole
        result=invoke(captures,b,admitted)
        need(type(result) is int and result in (0,2),'original observer exit classification')
        captures.end=whole if result==0 else end
        captures.tick();signal.setitimer(signal.ITIMER_REAL,max(.001,captures.end-time.monotonic()))
        captures.read(admitted['review_path'],32768,admitted['review_pin'])
        captures.read(admitted['selection_path'],32768,admitted['selection_pin'])
        own(captures,source_pin)
        captures.read(ROOT/b['directory']/'SOURCE_MANIFEST.json',32768,b['source'])
        captures.read(ROOT/b['directory']/'observe.py',20000,b['observer'])
        need(not os.path.lexists(cache),'no adapter cache writes');captures.tick()
    except BaseException:result=2
    finally:
        if armed:
            try:signal.setitimer(signal.ITIMER_REAL,0)
            except BaseException as e:restore_errors.append(type(e).__name__)
        for s,handler in saved.items():
            try:signal.signal(s,handler)
            except BaseException as e:restore_errors.append(type(e).__name__)
    return result if not restore_errors and time.monotonic()<(success_end if result==0 else end) else 2


if __name__=='__main__':raise SystemExit(main())
