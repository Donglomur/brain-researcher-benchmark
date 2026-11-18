"""Explicitly admitted full-reproduction runner; no default native mode.

The separate Figure3b scientific selector is not run through the old collector's
generated-fixture mode. This CLI retains the complete original reproduction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import execution as e

KEYS={'schema','scope','source_pins','store_root','store_sha256','store_read_limit','store_working_limit',
      'schedule_sha256','provider_config','provider_admission','output_root','provider_evidence_root',
      'limits','operator_joint_admission_bytes','permutation_budget','numpy_version','scipy_version'}


def read_protocol(path,expected):
    e.J.P.digest(expected)
    path=Path(path).absolute()
    e.need(not any(p.is_symlink() for p in (path,*path.parents)),'No protocol symlink')
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
    with os.fdopen(fd,'rb') as stream:
        before=os.fstat(stream.fileno())
        e.need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=65536,'Bounded ordinary protocol')
        raw=stream.read(before.st_size+1)
        e.need(len(raw)==before.st_size and e.sha(raw)==expected and e.stamp(before)==e.stamp(os.fstat(stream.fileno()))==e.stamp(path.lstat()),
               'Externally pinned stable exact protocol')
    value=e.J.P.parse(raw)
    e.need(e.encoded(value)==raw,'Canonical explicit execution protocol')
    return validate_protocol(value)


def validate_protocol(p):
    e.need(type(p) is dict and set(p)==KEYS and p['schema']=='language-full-original-execution-protocol/v1'
           and p['scope']=='original_full_reproduction','Exact separately admitted full reproduction only')
    caps=e.limits_snapshot(p['limits'])
    e.need(type(p['source_pins']) is dict and set(p['source_pins'])=={'execution.py','producer.py','reader.py','provider.py'},
           'All four actual source seams pinned')
    for sha in p['source_pins'].values():e.J.P.digest(sha)
    for name in ('store_sha256','schedule_sha256'):e.J.P.digest(p[name])
    e.need(p['source_pins']['execution.py']==e.sha((HERE/'execution.py').read_bytes()),'Exact admitted coordinator source')
    for name in ('store_root','output_root','provider_evidence_root'):
        e.need(type(p[name]) is str and 0<len(p[name])<=4096 and Path(p[name]).is_absolute(),'Absolute explicit operator paths')
    paths=[Path(p[k]) for k in ('store_root','output_root','provider_evidence_root')]
    e.need(all(a!=b and a not in b.parents and b not in a.parents for i,a in enumerate(paths) for b in paths[i+1:]),
           'Private store, output and provider evidence have disjoint roots')
    e.need(e.integer(p['store_read_limit'],1) and e.integer(p['store_working_limit'],1,4*1024**3)
           and e.integer(p['operator_joint_admission_bytes'],1),'Finite source/aggregate operator allowances')
    config=p['provider_config']
    e.need(type(config) is dict and config.get('store_sha256')==p['store_sha256']
           and config.get('schedule_sha256')==p['schedule_sha256']
           and type(config.get('caps')) is dict,'Exact provider-to-source/run identity')
    native=config['caps']
    e.need(native.get('max_jobs')==58926 and native.get('max_requests')==6776076,
           'Full original software schedule, not a convenient subset')
    e.need(e.integer(native.get('working_bytes'),1),'Explicit provider working allowance')
    # Separate conservative component allowances are additive, not falsely
    # presented as a single1GiB process allowance. OS limits belong to admission.
    joint=3*caps['working_bytes']+caps['cache_working_bytes']+p['store_working_limit']+native['working_bytes']
    e.need(p['operator_joint_admission_bytes']>=joint,'Complete simultaneous operator component admission')
    e.need(p['permutation_budget']==900000 and type(p['numpy_version']) is str and type(p['scipy_version']) is str,
           'Complete explicit original inference runtime and draw budget')
    return json.loads(e.encoded(p))


def load_reader(source_pins):
    producer=e.load_pinned('_language_execution_store_producer','original-store-producer-v1','producer.py',source_pins['producer.py'])
    prior=sys.modules.get('producer')
    try:
        sys.modules['producer']=producer
        return e.load_pinned('_language_execution_store_reader','original-store-producer-v1','reader.py',source_pins['reader.py'])
    finally:
        if prior is None:sys.modules.pop('producer',None)
        else:sys.modules['producer']=prior


def run_protocol(p):
    p=validate_protocol(p)
    reader_module=load_reader(p['source_pins'])
    provider_module=e.load_pinned('_language_execution_native_provider','original-exec-provider-v1','provider.py',p['source_pins']['provider.py'])
    config=provider_module.config_snapshot(p['provider_config'])
    e.need(config['provider_source_sha256']==provider_module.identity(),'Complete admitted provider source identity')
    provider=None;reader=None
    try:
        # NativeProvider refuses unsupported/unqualified hosts and absent exact
        # admission before source arrays, participant inputs or output creation.
        provider=provider_module.NativeProvider(config,p['provider_admission'],evidence_root=p['provider_evidence_root'])
        reader=reader_module.StoreReader(p['store_root'],expected_store_sha256=p['store_sha256'],
            read_limit=p['store_read_limit'],working_limit=p['store_working_limit'])
        e.need(reader.scope=='original_full_source','Complete authenticated original store')
        run=e.J.make_run(store_sha256=p['store_sha256'],candidate_sha256=config['candidate_sha256'],
            schedule_sha256=p['schedule_sha256'],provider_source_sha256=config['provider_source_sha256'],
            condition=config['condition'],working_limit=p['limits']['working_bytes'])
        collected,pin=e.collect(reader,provider,run,p['output_root'],limits=p['limits'])
        reader=None;provider=None
        recovery_reader=reader_module.StoreReader(p['store_root'],expected_store_sha256=p['store_sha256'],
            read_limit=p['store_read_limit'],working_limit=p['store_working_limit'])
        result,recovery_pin=e.recover(recovery_reader,run,p['output_root'],collected,
            collection_sha256=pin['sha256'],limits=p['limits'],summarize=True,
            permutation_budget=p['permutation_budget'],expected_numpy_version=p['numpy_version'],expected_scipy_version=p['scipy_version'])
        return {'collection':pin,'recovery':recovery_pin,'scope':p['scope'],'scientific_qualification':False}
    finally:
        e.close_owned(provider,reader)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',required=True)
    parser.add_argument('--protocol-sha256',required=True)
    args=parser.parse_args(argv)
    print(json.dumps(run_protocol(read_protocol(args.protocol,args.protocol_sha256))))


if __name__=='__main__':main()
