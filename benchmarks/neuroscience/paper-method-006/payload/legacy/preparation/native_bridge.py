"""Closed-operation bridge for literal v4.0.2 construction, never a paper repair.

This file is source only in the present grant. Scientific use requires the owner's
isolated controller, exact read-only source/environment/input mounts, disk quotas,
RAM/CPU/GPU/time supervision and an authority receipt bound to the entire request.
It has no service, shell command, network or arbitrary function-call interface.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import traceback

CATALOG_SHA = 'b4639a6b1d723b38b52ef4ea4d378dbb07717e374176051fea6ae392894fb66c'
OPERATIONS = {
    'waveform_preprocess_source': ('preprocess_wfs_sts', ('waveform_archive','y_chan','x_chan','y_chan_up','x_chan_up'), ('ups','device'), ('wfs','wfs_x','contaminations','sts','cls')),
    'synthetic_source': ('create_simulation', ('st','cl','wfs','wfs_x','contaminations','whiten_mat'), ('filename','n_sim','n_noise','n_batches','batch_size','tsig','tpad','n_chan_bin','drift','drift_range','drift_seed','fast','step','ups'), ('st_sim','cl_sim','amp_sim','wf_sim','cb_sim','wfid_sim','drift_sim_ups')),
    'hybrid_waveforms_source': ('waveforms_from_recording', ('filename_bg','chan_map'), ('NT','n_chan_bin','nt','twav_min'), ('wfs','cinds','chan0')),
    'hybrid_source': ('hybrid_simulation', ('filename_bg','wfs','cinds','chan0'), ('sim_name','n_batches_sim'), ('data','st_sim','cl_sim','ci_sim','wf_sim','cb_sim')),
}


def canonical_bytes(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _bounded_json(path, maximum):
    with open(path,'rb') as f:
        b=f.read(maximum+1)
    if len(b)>maximum:
        raise ValueError('metadata extent exceeded')
    return json.loads(b)


def _nonnegative_int(v):
    return type(v) is int and v >= 0


def _path_under(path, roots):
    p=Path(path)
    if not p.is_absolute() or '..' in p.parts:
        raise ValueError('absolute normalized namespace path required')
    real=p.resolve(strict=True)
    if p != real or not any(real==r or r in real.parents for r in roots):
        raise ValueError('symlink or path outside admitted roots')
    return real


def _verify_pin(desc, roots):
    if not isinstance(desc,dict) or set(desc) != {'path','bytes','sha256'}:
        raise ValueError('exact file pin required')
    p=_path_under(desc['path'],roots)
    if not _nonnegative_int(desc['bytes']) or not re.fullmatch('[0-9a-f]{64}',desc['sha256']):
        raise ValueError('invalid extent/digest')
    h=hashlib.sha256(); total=0
    with p.open('rb') as f:
        while True:
            b=f.read(min(1048576,desc['bytes']-total+1))
            if not b:break
            total+=len(b)
            if total>desc['bytes']:raise ValueError('file extent mismatch')
            h.update(b)
    if total!=desc['bytes'] or h.hexdigest()!=desc['sha256']:
        raise ValueError('file pin mismatch')
    return p,total


def validate_request(request):
    """Pure request validation; safe for invented metadata controls."""
    if not isinstance(request,dict) or request.get('schema')!='kilosort4_literal_constructor_request_v1':
        raise ValueError('wrong constructor schema')
    if request.get('canonical_id')!='PAPER-paper-method-006' or request.get('profile')!='R_source20':
        raise ValueError('literal bridge cannot impersonate paper/I reconstruction')
    if request.get('access_role') not in ('protected_reference','B-R'):
        raise ValueError('selected author constructor forbidden to A and I candidate roles')
    op=request.get('operation')
    if op not in OPERATIONS:raise ValueError('closed operation set')
    _,inputs,parameters,_=OPERATIONS[op]
    if not isinstance(request.get('inputs'),dict) or set(request['inputs']) != set(inputs):
        raise ValueError('all and only declared inputs required, including explicit null options')
    if not isinstance(request.get('parameters'),dict) or set(request['parameters']) != set(parameters):
        raise ValueError('all effective parameters required; implicit source defaults forbidden')
    optional_null={'y_chan_up','x_chan_up','whiten_mat','wfs','cinds','chan0'}
    for name,desc in request['inputs'].items():
        if desc is None:
            if name not in optional_null:raise ValueError('null mandatory constructor input')
            continue
        if not isinstance(desc,dict) or set(desc)!={'pin','encoding','shape','dtype'}:
            raise ValueError('typed input descriptor required before import')
        pin=desc['pin']
        if not isinstance(pin,dict) or set(pin)!={'path','bytes','sha256'} or not isinstance(pin['path'],str) or not _nonnegative_int(pin['bytes']) or not isinstance(pin['sha256'],str) or re.fullmatch('[0-9a-f]{64}',pin['sha256']) is None:
            raise ValueError('input exact pin required')
        expected_encoding=('raw-signal' if name=='filename_bg' else 'native-waveform-archive' if name=='waveform_archive' else 'npy-no-pickle')
        if desc['encoding']!=expected_encoding:raise ValueError('operation input encoding mismatch')
        if not isinstance(desc['shape'],list) or len(desc['shape'])>8 or any(not _nonnegative_int(d) or d>2**63-1 for d in desc['shape']):
            raise ValueError('finite numeric array shape descriptor required')
        if not isinstance(desc['dtype'],str) or not desc['dtype'] or len(desc['dtype'])>32:
            raise ValueError('bounded native dtype required')
    for field in ('source_root','output_root'):
        if not isinstance(request.get(field),str):raise ValueError(field+' required')
    if request['source_root']!='/sources/kilosort-v4.0.2' or request['output_root']!='/work/constructor-output':
        raise ValueError('fixed namespace roots required')
    limits=request.get('limits')
    required=('max_output_bytes','max_receipt_bytes','max_input_bytes','max_source_bytes','wall_seconds','memory_bytes','cpu_seconds','gpu_memory_bytes','scratch_bytes')
    if not isinstance(limits,dict) or set(limits)!=set(required) or any(not _nonnegative_int(limits[k]) or limits[k]==0 for k in required):
        raise ValueError('positive finite complete reservation required')
    if limits['max_receipt_bytes']>1048576:raise ValueError('receipt bound exceeds1MiB')
    for field in ('environment_receipt','dispatch_receipt'):
        desc=request.get(field)
        if not isinstance(desc,dict) or set(desc)!={'path','bytes','sha256'}:raise ValueError(field+' pin required')
    if not isinstance(request.get('sidecars'),dict):raise ValueError('explicit native sidecar inventory required')
    expected_sidecars=set()
    if op in ('hybrid_waveforms_source','hybrid_source'):
        expected_sidecars={'templates.npy','spike_times.npy','spike_clusters.npy'}
        if op=='hybrid_waveforms_source' or request['inputs']['wfs'] is None:
            expected_sidecars|={'ops.npy','cluster_KSLabel.tsv'}
        if op=='hybrid_source':expected_sidecars.add('probe')
    if set(request['sidecars'])!=expected_sidecars:raise ValueError('native implicit sidecar support differs from selected source branch')
    p=request['parameters']
    if op=='synthetic_source' and p['filename']!='/work/constructor-output/simulation.bin':
        raise ValueError('fixed simulation output required')
    if op=='hybrid_source' and (not isinstance(p['sim_name'],str) or re.fullmatch('[A-Za-z0-9_-]{1,64}',p['sim_name']) is None):
        raise ValueError('safe original hardcoded sim_name required')
    for k,v in p.items():
        if k in ('filename','device','sim_name'):continue
        if k in ('drift','fast','step'):
            if type(v) is not bool:raise ValueError('explicit Boolean required')
        elif k in ('tsig','drift_range'):
            if type(v) not in (int,float) or v<0 or v!=v or abs(v)==float('inf'):raise ValueError('finite nonnegative parameter required')
        elif not _nonnegative_int(v):raise ValueError('explicit integer parameter required')
    if op=='waveform_preprocess_source' and p['device'] not in ('cpu','cuda','cuda:0'):
        raise ValueError('device must match pinned controller environment')
    return {'operation':op,'all_effective_parameters_explicit':True,'native_execution_performed':False}


def validate_source_projection(root_names, package_names, members):
    """Pure name-set guard; file bytes are independently pinned before import."""
    if set(root_names) != {'kilosort'}:
        raise ValueError('native source root must be the exact core-source projection')
    if set(package_names) != {Path(x).name for x in members}:
        raise ValueError('unexpected source body, bytecode, model or module-shadowing entry')
    return True


def run_constructor(request):
    """Run one closed native function, only from an already admitted controller.

    No success token is returned on failure. Source-generated/partial files remain
    untouched. The caller retains the process, mounted files and full resource
    receipt even if this wrapper cannot write its terminal JSON.
    """
    validate_request(request)
    out=Path(request['output_root']); started=time.monotonic()
    # The controller creates an empty dedicated directory and makes all other
    # namespaces read-only. This local check does not replace physical isolation.
    if out.resolve(strict=True)!=out or any(out.iterdir()):
        raise ValueError('fresh empty output directory required')
    limits=request['limits']; counts={'logical_source_read_bytes':0,'logical_input_pin_read_bytes':0,'serialized_output_bytes':0}
    receipt={'schema':'kilosort4_constructor_receipt_v1','canonical_id':request['canonical_id'],'operation':request['operation'],'profile':'R_source20','publication_reproduction':False,'native_call_attempted':False,'status':'started','request_sha256':hashlib.sha256(canonical_bytes(request)).hexdigest(),'resource':counts,'outputs':[],'preserved_source_behavior':True}
    terminal=out/'constructor-receipt.json'
    try:
        # Requests are placed by the privileged controller. Its independent
        # authentication/namespace proofs are mandatory external qualification.
        runroots=[Path('/run')]
        dispatch_path,n=_verify_pin(request['dispatch_receipt'],runroots)
        dispatch=_bounded_json(dispatch_path,1048576)
        bind={k:v for k,v in request.items() if k!='dispatch_receipt'}
        if dispatch.get('request_without_dispatch_sha256')!=hashlib.sha256(canonical_bytes(bind)).hexdigest():
            raise ValueError('dispatch receipt request binding mismatch')
        if dispatch.get('mode')!='scientific-constructor' or dispatch.get('source_profile')!='R_source20' or dispatch.get('native_limits_enforced') is not True or dispatch.get('network')!='disabled' or dispatch.get('fresh_namespace') is not True:
            raise ValueError('controller qualification receipt is incomplete')
        _,n=_verify_pin(request['environment_receipt'],runroots)
        source=Path(request['source_root'])
        if source.resolve(strict=True)!=source:raise ValueError('source namespace alias')
        catalog_path=Path(__file__).with_name('NATIVE_SOURCE_MEMBERS.json')
        raw=catalog_path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=CATALOG_SHA:raise ValueError('native source catalog changed')
        counts['logical_source_read_bytes']+=len(raw)
        catalog=json.loads(raw)
        validate_source_projection([x.name for x in source.iterdir()], [x.name for x in (source/'kilosort').iterdir()], catalog['members'])
        if len(raw)+sum(v['bytes'] for v in catalog['members'].values())>limits['max_source_bytes']:
            raise ValueError('source authentication read budget exceeded')
        for member,pin in catalog['members'].items():
            _,n=_verify_pin({**pin,'path':str(source/member)},[source]);counts['logical_source_read_bytes']+=n
        for name,desc in request['sidecars'].items():
            if not isinstance(desc,dict) or set(desc)!={'pin','role'} or desc['role']!='protected_constructor_input':
                raise ValueError('protected native sidecar descriptor required')
            expected=(Path('/home/carsen/.kilosort/probes/neuropixPhase3B1_kilosortChanMap.prb') if name=='probe' else Path(request['inputs']['filename_bg']['pin']['path']).parent/'kilosort4'/name)
            if desc['pin']['path']!=str(expected):raise ValueError('native sidecar path mismatch')
            if counts['logical_input_pin_read_bytes']+desc['pin']['bytes']>limits['max_input_bytes']:raise ValueError('sidecar pin read reservation exceeded')
            _,n=_verify_pin(desc['pin'],[Path('/inputs'),Path('/home/carsen/.kilosort/probes')]);counts['logical_input_pin_read_bytes']+=n
        # No imports of NumPy/Torch/author code happen before all envelope checks.
        sys.dont_write_bytecode=True
        sys.pycache_prefix=str(out/'_never_populated_bytecode')
        if any(k=='kilosort' or k.startswith('kilosort.') for k in sys.modules):
            raise ValueError('author module was already loaded; fresh process required')
        sys.path.insert(0,str(source))
        import numpy as np
        import torch
        from kilosort import simulation
        if Path(simulation.__file__).resolve()!=source/'kilosort/simulation.py':
            raise ValueError('unexpected module resolution')
        args={}
        for name,desc in request['inputs'].items():
            if desc is None:
                if name not in ('y_chan_up','x_chan_up','whiten_mat','wfs','cinds','chan0'):
                    raise ValueError('null mandatory input')
                args[name]=None;continue
            if not isinstance(desc,dict) or set(desc)!={'pin','encoding','shape','dtype'}:
                raise ValueError('typed input descriptor required')
            size=desc['pin']['bytes']
            if counts['logical_input_pin_read_bytes']+size>limits['max_input_bytes']:
                raise ValueError('input authentication read budget exceeded')
            f,n=_verify_pin(desc['pin'],[Path('/inputs')]);counts['logical_input_pin_read_bytes']+=n
            if name in ('filename_bg','waveform_archive'):
                if desc['encoding'] not in ('raw-signal','native-waveform-archive'):
                    raise ValueError('native filename encoding mismatch')
                args[name]=str(f)
            else:
                if desc['encoding']!='npy-no-pickle':raise ValueError('numeric input requires NPY without pickle')
                a=np.load(f,allow_pickle=False)
                if a.dtype.hasobject or list(a.shape)!=desc['shape'] or str(a.dtype)!=desc['dtype']:
                    raise ValueError('array schema mismatch')
                args[name]=a
        p=request['parameters'].copy()
        if request['operation']=='waveform_preprocess_source':
            p['device']=torch.device(p['device'])
            args['filename']=args.pop('waveform_archive')
        # No source global or default is changed, and no native exception is
        # caught to fabricate a repaired result.
        if request['operation']=='hybrid_source':
            hardcoded=Path('/media/carsen/ssd1/spikesorting')/('sim_'+p['sim_name'])
            probe=Path('/home/carsen/.kilosort/probes/neuropixPhase3B1_kilosortChanMap.prb')
            if not hardcoded.is_dir() or any(hardcoded.iterdir()) or not probe.is_file():
                raise ValueError('original hybrid output/probe mounts missing or nonempty')
        receipt['native_call_attempted']=True
        op=request['operation']
        if op=='waveform_preprocess_source':values=simulation.preprocess_wfs_sts(**args,**p)
        elif op=='synthetic_source':values=simulation.create_simulation(**args,**p)
        elif op=='hybrid_waveforms_source':values=simulation.waveforms_from_recording(**args,**p)
        elif op=='hybrid_source':
            data,params=simulation.hybrid_simulation(**args,**p)
            values=(data,*params)
        else:raise AssertionError('closed operation dispatch drift')
        names=OPERATIONS[op][3]
        if not isinstance(values,tuple) or len(values)!=len(names):raise ValueError('native output arity mismatch')
        # Reserve all array serializations before writing the first one. Native
        # side-effect files remain separately quota-controlled/accounted outside.
        projected=0
        for name,a in zip(names,values):
            if not isinstance(a,np.ndarray) or a.dtype.hasobject:raise ValueError('native output not a numeric ndarray')
            projected+=a.nbytes+4096
        if projected>limits['max_output_bytes']:raise ValueError('full output serialization reservation exceeded')
        for name,a in zip(names,values):
            f=out/(name+'.npy')
            with f.open('xb') as handle:np.save(handle,a,allow_pickle=False)
            size=f.stat().st_size;counts['serialized_output_bytes']+=size
            receipt['outputs'].append({'name':name,'path':str(f),'bytes':size,'shape':list(a.shape),'dtype':str(a.dtype),'role':'protected_constructor_output','integrity_status':'requires_controller_full_digest_and_custody'})
        receipt['status']='native-returned-unqualified'
        receipt['scientific_status']='required-unscorable until complete source/full-support/native/numeric/qualification joins'
        receipt['native_side_effects']={'synthetic_source':['simulation.bin','simulation.meta','simulation_params.npz'],'hybrid_source':['original hardcoded output directory /sim.imec0.ap.bin and metadata/params']}.get(op,[])
        return receipt
    except BaseException as exc:
        receipt['status']='native-failed' if receipt['native_call_attempted'] else 'pre-dispatch-refused'
        receipt['failure']={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc(limit=16)}
        raise
    finally:
        receipt['wall_seconds_wrapper']=time.monotonic()-started
        receipt['physical_measurements']='Controller receipt required; logical counts here omit native reads/allocations/sideeffects'
        data=canonical_bytes(receipt)+b'\n'
        if len(data)>limits['max_receipt_bytes']:
            # Do not truncate an evidence-bearing receipt into a success report.
            raise RuntimeError('terminal receipt exceeds reserved extent; controller must preserve stderr/output namespace')
        with terminal.open('xb') as f:f.write(data)


def main(argv=None):
    args=sys.argv[1:] if argv is None else argv
    if len(args)!=1 or args[0]!='/run/request.json':
        raise SystemExit('Only fixed isolated /run/request.json is accepted')
    request=_bounded_json(args[0],1048576)
    run_constructor(request)


if __name__=='__main__':main()
