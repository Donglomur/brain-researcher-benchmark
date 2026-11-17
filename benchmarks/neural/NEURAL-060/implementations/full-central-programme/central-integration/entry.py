"""Concrete central source entry; early qualification precedes all CLI operands."""
import time
ENTRY_START = time.monotonic()
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import types
ACTUAL_ARGV = list(sys.orig_argv)
ACTUAL_CWD = os.getcwd()
HERE = Path(__file__).absolute().parent
REPO = HERE.parents[5]
PARENT = HERE.parent/'program'
PARENT_PIN = {'bytes':2492,'sha256':'2ca0f30669eb7ae0a5f0a5bbbe04b6f950fa18bfb709890e817ad574bd04d140'}
NAMES = {'entry.py','dispatch.py','host.py','common_io.py','caller_observer.py','BINDINGS.json','CAMPAIGN_SOURCE_CLOSURE.json'}
EXTERNAL = {'tools/neurobench_campaign.py','tools/neurobench_condition_campaign.py','tools/neurobench_campaign_gate.py',
            'authoring/delivery-20261105/common/campaign-exposure-contract-v1/validate.py'}
BOOTSTRAP_READS = 0


def need(ok, why):
    if not ok: raise ValueError(why)


def pin(raw): return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def parse(raw):
    def pairs(rows):
        out = {}
        for k,v in rows: need(k not in out,'duplicate source key');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite source'))


def capture(path, expected):
    global BOOTSTRAP_READS
    need(type(expected) is dict and set(expected)=={'bytes','sha256'} and type(expected['bytes']) is int
         and 0<expected['bytes']<=2097152,'bounded exact source descriptor')
    need(time.monotonic()<ENTRY_START+120,'local bootstrap safety deadline')
    p=Path(path);need(p.is_absolute() and str(path)==str(p) and not str(path).startswith('//')
         and '..' not in p.parts,'canonical absolute source path')
    for parent in p.parents:need(stat.S_ISDIR(parent.lstat().st_mode),'ordinary source parents')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd);need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_size==expected['bytes'],'exact ordinary source')
        BOOTSTRAP_READS+=a.st_size+1;need(BOOTSTRAP_READS<=4194304,'complete bootstrap source reservation')
        parts=[];left=a.st_size
        while left:
            need(time.monotonic()<ENTRY_START+120,'bootstrap source capture deadline')
            body=os.read(fd,min(left,65536));need(body,'short source');parts.append(body);left-=len(body)
        raw=b''.join(parts);z=os.fstat(fd)
        sig=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_nlink,s.st_mtime_ns,s.st_ctime_ns)
        need(not os.read(fd,1) and sig(a)==sig(z)==sig(p.lstat()) and pin(raw)==expected,'stable exact source')
        return raw
    finally:os.close(fd)


def module(raw, path, **bindings):
    m=types.ModuleType('neural060_central_'+Path(path).stem);m.__file__=str(path);m.__dict__.update(bindings)
    exec(compile(raw,str(path),'exec'),m.__dict__);return m


def sources(source):
    global BOOTSTRAP_READS
    before=BOOTSTRAP_READS
    raw=capture(HERE/'SOURCE_MANIFEST.json',source);manifest=parse(raw)
    need(manifest.get('schema')=='neural060_central_source_v1' and set(manifest['files'])==NAMES
         and manifest['parent_source']==PARENT_PIN,'exact central and original source closure')
    bodies={n:capture(HERE/n,p) for n,p in manifest['files'].items()}
    binding=parse(bodies['BINDINGS.json']);expected_parent={'path':str((PARENT/'SOURCE_MANIFEST.json').relative_to(REPO)),**PARENT_PIN}
    need(binding['schema']=='neural060_central_bindings_v1' and binding['task_id']=='NEURAL-060'
         and binding['parent_source']==expected_parent and set(binding['external_source'])==EXTERNAL,'fixed exact parent and campaign dependencies')
    pm=parse(capture(PARENT/'SOURCE_MANIFEST.json',PARENT_PIN))
    bootraw=capture(PARENT/'bootstrap.py',pm['files']['bootstrap.py'])
    boot=module(bootraw,PARENT/'bootstrap.py')
    parent=boot.Sources(PARENT,PARENT_PIN)
    BOOTSTRAP_READS+=parent.read_bytes
    need(BOOTSTRAP_READS<=4194304 and parent.pins==pm['files'],'captured complete original source and charged rereads')
    package=binding['parent_package'];package_raw=capture(REPO/package['path'],{k:package[k] for k in ('bytes','sha256')})
    package_rows=parse(package_raw)['files'];inventory={r['path']:{k:r[k] for k in ('bytes','sha256')} for r in package_rows}
    need(len(inventory)==len(package_rows),'unique original package members')
    for name,descriptor in parent.pins.items():
        need(inventory[str((PARENT/name).relative_to(REPO))]==descriptor,'runtime is exact reviewed parent package')
    definitions={}
    for d in binding['definition_source']:
        need(type(d['path']) is str and not Path(d['path']).is_absolute() and '..' not in Path(d['path']).parts,
             'confined scientific/roster definition source')
        definitions[d['path']]=capture(REPO/d['path'],{k:d[k] for k in ('bytes','sha256')})
    external={n:capture(REPO/n,p) for n,p in binding['external_source'].items()}
    closure=parse(bodies['CAMPAIGN_SOURCE_CLOSURE.json'])
    for row in closure['files']:
        need(row['path'].startswith('authoring/delivery-20261105/common/campaign-exposure-contract-v1/')
             and '..' not in Path(row['path']).parts,'fixed campaign contract source')
        capture(REPO/row['path'],{k:row[k] for k in ('bytes','sha256')})
    source_rows={str(HERE/'SOURCE_MANIFEST.json'):source, **{str(HERE/n):p for n,p in manifest['files'].items()},
                 str(PARENT/'SOURCE_MANIFEST.json'):PARENT_PIN, **{str(PARENT/n):p for n,p in parent.pins.items()},
                 str(REPO/package['path']):{k:package[k] for k in ('bytes','sha256')}}
    for d in [*binding['definition_source'],*closure['files'],
              *[{'path':n,**p} for n,p in binding['external_source'].items()]]:
        name=str(REPO/d['path']);q={k:d[k] for k in ('bytes','sha256')}
        need(name not in source_rows or source_rows[name]==q,'consistent source recheck descriptors')
        source_rows[name]=q
    io=module(bodies['common_io.py'],HERE/'common_io.py')
    gate=module(external['tools/neurobench_campaign_gate.py'],REPO/'tools/neurobench_campaign_gate.py')
    vn='authoring/delivery-20261105/common/campaign-exposure-contract-v1/validate.py'
    need(pin(external[vn])==gate.VALIDATOR,'captured exact validator')
    validator=module(external[vn],REPO/vn);gate.validator=lambda repo:(validator,Path(repo)/gate.CONTRACT)
    base=module(external['tools/neurobench_campaign.py'],REPO/'tools/neurobench_campaign.py')
    need(pin(external['tools/neurobench_campaign_gate.py'])==base.CAMPAIGN_HELPER,'captured campaign helper')
    base._campaign_module=lambda repo=REPO:gate
    caller=module(bodies['caller_observer.py'],HERE/'caller_observer.py')
    host=module(bodies['host.py'],HERE/'host.py',u=io,caller=caller)
    dispatch=module(bodies['dispatch.py'],HERE/'dispatch.py',u=io)
    return {'source':source,'manifest':manifest,'binding':binding,'bodies':bodies,'parent':parent,'parent_bootstrap':boot,
            'parent_core':parent.module('core'),'parent_gate':parent.module('authority'),'parent_outer':parent.module('outer'),
            'source_rows':source_rows,'definitions':definitions,'external':external,'gate':gate,'base':base,'io':io,'caller':caller,'host':host,
            'dispatch':dispatch,'source_reads':BOOTSTRAP_READS-before,'here':HERE,'repo':REPO,'parent_root':PARENT}


def main(argv=None):
    p=argparse.ArgumentParser()
    for k in ('program','output','review','source-sha256'):p.add_argument('--'+k,required=True)
    for k in ('source-bytes','other-reserve-bytes'):p.add_argument('--'+k,type=int,required=True)
    a=p.parse_args(argv)
    need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated/no-site/no-bytecode central entry')
    def expired(*_):raise TimeoutError('central inherited deadline')
    old={n:signal.signal(n,expired) for n in (signal.SIGALRM,signal.SIGINT,signal.SIGTERM)}
    signal.setitimer(signal.ITIMER_REAL,max(.001,ENTRY_START+120-time.monotonic()))
    host=None
    try:
        env=sources({'bytes':a.source_bytes,'sha256':a.source_sha256})
        host=env['host'].Host(ENTRY_START,env['source_reads'])
        cli={**vars(a),'actual_argv':ACTUAL_ARGV,'actual_cwd':ACTUAL_CWD}
        return env['dispatch'].execute(cli,env,host)
    except BaseException as error:
        print(json.dumps({'status':'refused','error_type':type(error).__name__,'automatic_retry':False,
              'costs':host.record() if host is not None else {'bootstrap_read_reservations':BOOTSTRAP_READS,
                        'physical_IO_measured':False}}),file=sys.stderr)
        return 2
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        for n,handler in old.items():signal.signal(n,handler)


if __name__=='__main__':raise SystemExit(main())
