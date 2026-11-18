"""Explicitly admitted original Figure3b runner; no default native provider.

The source schedule is42 jobs/5685 callbacks, not a mandated API/process count.
The optional fresh-exec baseline requires its own real target qualification.
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
import reference as ref

KEYS={'schema','scope','source_pins','store_root','store_sha256','store_read_limit','store_working_limit',
      'schedule_sha256','provider_config','provider_admission','output_root','provider_evidence_root',
      'limits','operator_joint_admission_bytes','numpy_version','reference_path','reference_sha256','source_support_sha256'}


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
    e.need(type(p) is dict and set(p)==KEYS and p['schema']=='language-selected-figure3b-execution-protocol/v1'
           and p['scope']=='original_figure3b_improvement','Exact separately admitted original Figure3b endpoint only')
    caps=e.limits_snapshot(p['limits'])
    e.need(type(p['source_pins']) is dict and set(p['source_pins'])=={'execution.py','producer.py','reader.py','provider.py','reference.py'},
           'All five actual source seams pinned')
    for sha in p['source_pins'].values():e.J.P.digest(sha)
    for name in ('store_sha256','schedule_sha256','source_support_sha256','reference_sha256'):e.J.P.digest(p[name])
    e.read_source(HERE/'execution.py',p['source_pins']['execution.py'])
    e.read_source(HERE/'reference.py',p['source_pins']['reference.py'])
    e.need(p['reference_sha256']==ref.REFERENCE_SHA and p['source_support_sha256']==ref.CENSUS_SHA,
           'Exact accepted author-reference and original support identities')
    for name in ('store_root','output_root','provider_evidence_root','reference_path'):
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
    e.need(native.get('max_jobs')==42 and native.get('max_requests')==5685,
           'Exact adopted Figure3b software schedule')
    e.need(e.integer(native.get('working_bytes'),1),'Explicit provider working allowance')
    # Separate conservative component allowances are additive, not falsely
    # presented as a single1GiB process allowance. OS limits belong to admission.
    joint=3*caps['working_bytes']+caps['cache_working_bytes']+p['store_working_limit']+native['working_bytes']
    e.need(p['operator_joint_admission_bytes']>=joint,'Complete simultaneous operator component admission')
    e.need(type(p['numpy_version']) is str and p['numpy_version']==e.np.__version__,
           'Exact declared NumPy scoring runtime; no inherited full-reproduction permutations')
    return json.loads(e.encoded(p))


def load_reader(source_pins):
    producer=e.load_pinned('_language_execution_store_producer','original-figure3b-store-v1','producer.py',source_pins['producer.py'])
    prior=sys.modules.get('producer')
    try:
        sys.modules['producer']=producer
        return e.load_pinned('_language_execution_store_reader','original-figure3b-store-v1','reader.py',source_pins['reader.py'])
    finally:
        if prior is None:sys.modules.pop('producer',None)
        else:sys.modules['producer']=prior


def phase_cost_bounds(p):
    """Additive phase ceilings; not a claim of one shared meter or total RSS.

    The external admission must cover these plus separately enumerated cache,
    provider, authority and packed I/O. A hard timeout also covers indivisible
    source imports, reads and numerical operations between cooperative checks.
    """
    return {'source_reader_traversals':2,
        'source_reader_logical_read_ceiling_bytes':2*p['store_read_limit'],
        'saved_reference_read_ceiling_bytes':ref.REFERENCE_BYTES+1,
        'collection_plus_recovery_cooperative_wall_ceiling_seconds':2*p['limits']['wall_seconds'],
        'collection_plus_recovery_receipt_output_ceiling_bytes':2*p['limits']['receipt_output_bytes'],
        'additional_separate_counters':['cache reads','frozen bundles','dispatched bundles','authority reads/output',
            'packed reads/output','provider tree/feature/kernel/staging/pipe/journal counters'],
        'whole_entrypoint_external_hard_timeout_required':True,
        'single_shared_phase_meter_claimed':False}


def run_protocol(p):
    p=validate_protocol(p)
    reader_module=load_reader(p['source_pins'])
    provider_module=e.load_pinned('_language_execution_native_provider','original-exec-provider-v1','provider.py',p['source_pins']['provider.py'])
    config=provider_module.config_snapshot(p['provider_config'])
    e.need(config['provider_source_sha256']==provider_module.identity(),'Complete admitted provider source identity')
    reference=ref.load(p['reference_path'])
    provider=None;reader=None
    try:
        # NativeProvider refuses unsupported/unqualified hosts and absent exact
        # admission before source arrays, participant inputs or output creation.
        provider=provider_module.NativeProvider(config,p['provider_admission'],evidence_root=p['provider_evidence_root'])
        reader=reader_module.StoreReader(p['store_root'],expected_store_sha256=p['store_sha256'],
            read_limit=p['store_read_limit'],working_limit=p['store_working_limit'])
        e.need(reader.scope=='original_figure3b_improvement','Complete authenticated selected original store')
        run=e.J.make_run(store_sha256=p['store_sha256'],candidate_sha256=config['candidate_sha256'],
            schedule_sha256=p['schedule_sha256'],provider_source_sha256=config['provider_source_sha256'],
            condition=config['condition'],working_limit=p['limits']['working_bytes'])
        collected,pin=e.collect(reader,provider,run,p['output_root'],limits=p['limits'])
        reader=None;provider=None
        recovery_reader=reader_module.StoreReader(p['store_root'],expected_store_sha256=p['store_sha256'],
            read_limit=p['store_read_limit'],working_limit=p['store_working_limit'])
        result,recovery_pin=e.recover(recovery_reader,run,p['output_root'],collected,
            collection_sha256=pin['sha256'],limits=p['limits'],source_support_sha256=p['source_support_sha256'],
            reference=reference,reference_sha256=e.sha(e.encoded(reference)))
        return {'collection':pin,'recovery':recovery_pin,'scope':p['scope'],
                'phase_cost_bounds':phase_cost_bounds(p),'scientific_qualification':False}
    finally:
        e.close_owned(provider,reader)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',required=True)
    parser.add_argument('--protocol-sha256',required=True)
    args=parser.parse_args(argv)
    print(json.dumps(run_protocol(read_protocol(args.protocol,args.protocol_sha256))))


if __name__=='__main__':main()
