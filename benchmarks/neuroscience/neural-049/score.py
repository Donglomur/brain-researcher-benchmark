"""Externally authenticated entry; capture definitions before selected operands."""
import time
ENTRY_START = time.monotonic()
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types

REL = 'authoring/delivery-20261105/common/remaining-builds-wave33/neural049-complete-design/curated-retrospective-design-v1/implementation-v1/central-integration-v1/implementation-v1'
SCORE_ALIAS = 'benchmarks/neuroscience/neural-049/score.py'
CENTRAL_FILES = {'entry.py','io.py','routing.py','dispatch.py','readback.py','BINDINGS.json'}


def sources(repo, expected, start):
    """Stage A: no parent code/import or operand capture before qualification."""
    here = repo/REL
    ledger = {'read_reserved':0,'read_observed':0,'attempted':[]}
    rows = {}; raws = {}
    def tick():
        if not start <= time.monotonic() < start+120:
            raise TimeoutError('local source startup')
    def capture(rel, desc):
        tick()
        if type(rel) is not str or Path(rel).is_absolute() or any(x in ('','.','..') for x in rel.split('/')) or '\\' in rel:
            raise ValueError('literal source relative path')
        path = repo/rel
        for par in reversed(path.parents):
            if not stat.S_ISDIR(os.lstat(par).st_mode): raise ValueError('ordinary source parents')
        n = desc['bytes']; h = desc['sha256']
        if type(n) is not int or not 0 <= n <= 2*1048576 or type(h) is not str or len(h) != 64:
            raise ValueError('bounded source pin')
        ledger['read_reserved'] += n+1; ledger['attempted'].append(rel)
        if ledger['read_reserved'] > 16*1048576: raise ValueError('source capture ceiling')
        fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != n:
                raise ValueError('exact ordinary source')
            body = bytearray()
            while len(body) < n:
                tick(); block = os.read(fd,min(65536,n-len(body)))
                ledger['read_observed'] += len(block)
                if not block: raise ValueError('short source')
                body.extend(block)
            extra = os.read(fd,1); ledger['read_observed'] += len(extra)
            stamp = lambda s: (s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            if extra or stamp(before) != stamp(os.fstat(fd)) or stamp(before) != stamp(os.lstat(path)):
                raise ValueError('source capture identity')
            if hashlib.sha256(body).hexdigest() != h: raise ValueError('source hash')
        finally:
            first = sys.exception()
            try: os.close(fd)
            except BaseException as later:
                if first is not None: raise BaseExceptionGroup('capture and close',[first,later]) from None
                raise
        if stamp(before) != stamp(os.lstat(path)): raise ValueError('source postclose identity')
        tick(); rows[rel] = desc; raws[rel] = bytes(body)
        return raws[rel]
    def module(name, rel, inject=None):
        tick(); m = types.ModuleType(name); m.__file__ = str(repo/rel)
        if inject: m.__dict__.update(inject)
        exec(compile(raws[rel],m.__file__,'exec',dont_inherit=True),m.__dict__)
        tick(); return m
    try:
        manifest = json.loads(capture(REL+'/SOURCE_MANIFEST.json',expected))
        if manifest.get('schema') != 'neural049_central_runtime_source_v1' or set(manifest['files']) != CENTRAL_FILES:
            raise ValueError('exact central source schema and members')
        for leaf,desc in manifest['files'].items(): capture(REL+'/'+leaf,desc)
        bindings = json.loads(raws[REL+'/BINDINGS.json'])
        if bindings.get('schema') != 'neural049_central_bindings_v1' or bindings.get('shared_adoption_selected') is not True:
            raise ValueError('actual separately adopted shared source required')
        for row in bindings['external_sources']:
            rel = row['path']
            if rel in rows: raise ValueError('duplicate source member')
            capture(rel,{'bytes':row['bytes'],'sha256':row['sha256']})
        pd = bindings['parent_manifest']; parent_manifest = json.loads(raws[pd['path']])
        if parent_manifest.get('schema') != 'neural049_runtime_source_v1' or len(parent_manifest['files']) != 70:
            raise ValueError('complete current seventy-member parent')
        parent_root = repo/bindings['parent_root']
        for name,desc in parent_manifest['files'].items():
            if rows.get(bindings['parent_root']+'/'+name) != desc: raise ValueError('exact full raw parent capture')
        if parent_manifest.get('overrides') != {'preparation/prepare.py':'owner-helper-repairs-v1/preparation_prepare.py','references/r2/budget.py':'owner-helper-repairs-v1/r2_budget.py'}:
            raise ValueError('original and effective helper overlay closure')
        u = module('_neural049_central_io',REL+'/io.py')
        shared = bindings['shared']
        gate = module('_neural049_central_gate',shared['gate'])
        base = module('_neural049_central_base',shared['base'])
        contract = module('_neural049_central_contract',shared['validator'])
        # Substitute only captured definitions at the original loader seams;
        # actual validation/qualification/route functions still run unchanged.
        gate.validator = lambda _: (contract,(repo/shared['validator']).parent)
        base._campaign_module = lambda _: gate
        components = {name:module('_neural049_central_'+name,REL+'/'+name+'.py',{'u':u})
                      for name in ('routing','dispatch','readback')}
        freeze = dict(rows); freeze[SCORE_ALIAS] = manifest['files']['entry.py']
        return {'repo':repo,'here':here,'source':expected,'manifest':manifest,'bindings':bindings,
                'source_rows':rows,'raws':raws,'freeze_files':freeze,'u':u,'base':base,'gate':gate,'components':components,
                'parent_root':parent_root,'parent_manifest_path':repo/pd['path'],'parent_pin':pd['pin'],
                'parent_manifest':parent_manifest,'source_accounting':ledger,'parent_context':None,
                'parent':None,'captured_parent':None,'source_read_reserved':ledger['read_reserved']}
    except BaseException as error:
        error.source_accounting = ledger
        raise


def bind_parent(env, review, authority, host):
    """Stage B: real inherited origin before any captured parent import."""
    u = env['u']; origin = u.finite(review['original_origin'])
    end = u.finite(authority['clock']['readback_end'])
    u.need(origin == authority['clock']['origin'] and origin <= host.entry_start <= time.monotonic() < min(host.entry_start+120,end),
           'original clock and local startup before parent definitions')
    cap = env['parent_pin']['bytes']+1+sum(p['bytes']+1 for p in env['parent_manifest']['files'].values())
    host.reserve(cap)
    context = {'origin':origin,'deadline':min(host.entry_start+120,end),'read_cap':cap,
               'read_reserved':0,'read_observed':0,'attempted_paths':[]}
    env['parent_context'] = context
    path = env['bindings']['parent_root']+'/program/bootstrap.py'
    bootstrap = types.ModuleType('_neural049_central_parent_bootstrap'); bootstrap.__file__ = str(env['repo']/path)
    host.tick(end); exec(compile(env['raws'][path],bootstrap.__file__,'exec',dont_inherit=True),bootstrap.__dict__); host.tick(end)
    captured = bootstrap.load(str(env['parent_root']),str(env['parent_manifest_path']),env['parent_pin'],context)
    host.tick(min(host.entry_start+120,end))
    # Source definitions may remain available for the explicitly later public
    # audit. Qualify/child execution retain their separate ORIGINAL endpoints.
    context['deadline'] = review['central_validation_deadline']
    import importlib
    parent = {name:importlib.import_module(name) for name in
              ('core','authority','configuration','outer','launch_code','caller_observer','contracts','schedule','admission')}
    host.tick(min(host.entry_start+120,end))
    env['captured_parent'] = captured; env['parent'] = parent
    return parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--operation',choices=['collect','grade'],required=True)
    parser.add_argument('--panel',choices=['curated_retrospective_full_v1','review'],required=True)
    parser.add_argument('--condition',choices=['default','curated_retrospective_full_v1'],default='default')
    for name in ('program','output','review','source-sha256'): parser.add_argument('--'+name,required=True)
    for name in ('other-reserve-bytes','source-bytes'): parser.add_argument('--'+name,type=int,required=True)
    args = parser.parse_args(); cli = vars(args)
    cli['condition'] = None if args.condition == 'default' else args.condition
    cli.update(actual_argv=list(sys.orig_argv),actual_cwd=os.getcwd(),source_pin={'bytes':args.source_bytes,'sha256':args.source_sha256})
    env = host = None
    try:
        repo = Path(cli['actual_cwd'])
        if str(Path(__file__).absolute()) not in (str(repo/REL/'entry.py'),str(repo/SCORE_ALIAS)):
            raise ValueError('fixed source entry or installed exact score alias')
        env = sources(repo,cli['source_pin'],ENTRY_START)
        host = env['u'].Host(ENTRY_START); host.reads = env['source_read_reserved']
        host.read(Path(__file__).absolute(),2*1048576,env['manifest']['files']['entry.py'])
        env['bind_parent'] = bind_parent
        result = env['components']['dispatch'].execute(cli,env,host)
        print(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False)); return 0
    except BaseException as error:
        record = {'status':'failed','error_type':type(error).__name__,
                  'source':getattr(error,'source_accounting',None if env is None else env['source_accounting']),
                  'parent_source':None if env is None else env['parent_context'],
                  'central_costs':None if host is None else host.record(),
                  'failure':getattr(error,'failure_record',None),'automatic_retry':False}
        raw = json.dumps(record,sort_keys=True,separators=(',',':'),allow_nan=False)
        print(raw if len(raw.encode()) <= 60000 else json.dumps({'status':'failed','error_type':type(error).__name__,
              'failure_record_truncated':True,'central_costs':None if host is None else host.record()}))
        return 1


if __name__ == '__main__': raise SystemExit(main())
