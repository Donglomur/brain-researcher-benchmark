#!/usr/bin/env python3
"""53 generated portable partial-layout resume controls; no provider/data execution.

Preserves the public-source assertions from an accepted 69-control private campaign.
Sixteen fixed-host staging/verifier controls are deliberately absent, not skipped.
The detailed result records generated oracles and does not qualify original data.
"""
from __future__ import annotations
import argparse, ast, copy, hashlib, json, math, os, pathlib, stat, sys, types, contextlib, importlib.metadata
import io as streamio
import collections, dataclasses, re, time
from pathlib import Path
SOURCE_READ = 0
SOURCE_OBSERVED = 0
SOURCE_DESCRIPTOR = {'bytes': 1156, 'sha256': 'ea481e9ce9780f751cd2e7f719c783205d237fb25f3c4dfb330d301e795da923'}
EXPECTED_CONTROLS = ['artifact_ok', 'artifact_empty', 'artifact_forced600', 'artifact_zero', 'artifact_short', 'artifact_chmod', 'artifact_chmod_no_effect', 'artifact_fstat_before', 'artifact_fstat_after', 'artifact_fsync', 'artifact_close', 'artifact_chmod_close', 'artifact_fsync_close', 'artifact_parent_open', 'artifact_parent_fsync', 'artifact_parent_close', 'artifact_parent_fsync_close', 'byte_identical_copy_preserves_old600', 'exclusive_collision_old600', 'real_capture_bad_digest', 'actual_decoder_malformed', 'actual_decoder_duplicate', 'actual_decoder_nonfinite', 'all455_admission_full1936', 'admission_raw_manifest_hash', 'admission_last_body_hash', 'admission_last_schema', 'admission_last_experiment', 'admission_last_asset', 'admission_array_decoded', 'admission_asset_version', 'admission_duplicate_seed', 'admission_missing_seed', 'admission_foreign_seed', 'admission_wrong_provenance', 'admission_source_counts', 'admission_partial_bank', 'admission_complete_report', 'admission_duplicate_assets', 'admission_missing_assets', 'finite400_config', 'finite_config_refusal_0', 'finite_config_refusal_True', 'finite_config_refusal_1482', 'core_finite400', 'core_deadline', 'core_copy_failure', 'core_full_union', 'core_partial_bank', 'core_copy_digest', 'entry_valid400', 'entry_last_seed_invalid', 'entry_real_secondary_close']


def read_source(ref):
    global SOURCE_READ, SOURCE_OBSERVED
    assert type(ref['bytes']) is int and 0 <= ref['bytes'] <= 524288
    p = Path(ref['path'])
    s = p.lstat()
    assert stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_size == ref['bytes']
    SOURCE_READ += ref['bytes']+1
    assert SOURCE_READ <= 1048576
    with p.open('rb') as f:
        b = f.read(ref['bytes']+1)
    SOURCE_OBSERVED += len(b)
    assert len(b) == ref['bytes'] and hashlib.sha256(b).hexdigest() == ref['sha256']
    return b

def module_from(name, ref, body):
    m = types.ModuleType(name)
    m.__file__ = ref['path']
    m.__package__ = name.rpartition('.')[0]
    sys.modules[name] = m
    exec(compile(body,ref['path'],'exec'),m.__dict__)
    return m

def refused(fn):
    try:
        fn()
    except (ValueError, TypeError, OSError) as exc:
        return exc
    raise AssertionError('expected refusal')

def put(path, body, mode, tally):
    tally['harness_write_requested'] += len(body)
    tally['write_requested'] += len(body)
    assert tally['harness_write_requested'] + tally['artifact_meter_reserved'] <= 16384
    fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
    try:
        n = os.write(fd,body)
        tally['write_confirmed'] += n
        assert n == len(body)
    finally:
        os.close(fd)

class ForbiddenProvider(BaseException):
    pass

def artifact_checks(M, root, rows, tally):
    payload = b'{"generated":true}\n'
    class Proxy:
        def __init__(self, fault):
            self.fault, self.fds, self.trace = fault, {}, []
            self.injected = self.fs = 0
        def __getattr__(self, name):
            return getattr(os, name)
        def open(self, path, flags, mode=0o777):
            kind = 'dir' if flags & os.O_DIRECTORY else 'file'
            if kind == 'dir' and self.fault == 'parent_open':
                self.injected += 1
                raise OSError('generated parent open')
            if kind == 'file' and flags & os.O_CREAT and self.fault in ('forced600', 'chmod_no_effect'):
                mode = 0o600
            fd = os.open(path, flags, mode)
            self.fds[fd] = kind
            self.trace.append(('open',kind))
            return fd
        def write(self, fd, body):
            tally['write_requested'] += len(body)
            if self.fault == 'zero':
                n = 0
            elif self.fault == 'short':
                n = os.write(fd, body[:-1])
            else:
                n = os.write(fd, body)
            tally['write_confirmed'] += n
            self.trace.append(('write',n))
            return n
        def fstat(self, fd):
            self.fs += 1
            self.trace.append(('fstat',self.fds[fd]))
            if (self.fault == 'fstat_before' and self.fs == 1) or (self.fault == 'fstat_after' and self.fs == 2):
                self.injected += 1
                raise OSError('generated stat')
            return os.fstat(fd)
        def fchmod(self, fd, mode):
            self.trace.append(('chmod',mode))
            if self.fault in ('chmod', 'chmod_close'):
                self.injected += 1
                raise OSError('generated primary chmod')
            if self.fault == 'chmod_no_effect':
                self.injected += 1
                return
            return os.fchmod(fd,mode)
        def fsync(self, fd):
            kind = self.fds[fd]
            self.trace.append(('fsync',kind))
            if (kind == 'file' and self.fault in ('fsync','fsync_close')) or (kind == 'dir' and self.fault in ('parent_fsync','parent_fsync_close')):
                self.injected += 1
                raise OSError('generated primary sync')
            return os.fsync(fd)
        def close(self, fd):
            kind = self.fds[fd]
            self.trace.append(('close',kind))
            fails = (kind == 'file' and self.fault in ('close','chmod_close','fsync_close')) or (kind == 'dir' and self.fault in ('parent_close','parent_fsync_close'))
            if fails:
                self.injected += 1
                raise OSError('generated secondary close')
            os.close(fd)
            del self.fds[fd]
    modes = ('ok','empty','forced600','zero','short','chmod','chmod_no_effect','fstat_before','fstat_after','fsync','close','chmod_close','fsync_close','parent_open','parent_fsync','parent_close','parent_fsync_close')
    for mode in modes:
        d = root / mode
        d.mkdir()
        proxy = Proxy(mode)
        meter = M.ByteMeter(4096,4096)
        store = M.ArtifactStore(d,meter)
        original = M.os
        result = None
        error = None
        body = b'' if mode == 'empty' else payload
        M.os = proxy
        try:
            try:
                result = store.write('artifact.json',body,role='generated',visibility='operator',producer='generated-regression')
            except Exception as exc:
                error = exc
        finally:
            M.os = original
        cleanup = 0
        for fd in list(proxy.fds):
            os.close(fd)
            del proxy.fds[fd]
            cleanup += 1
        assert meter.write_bytes == len(body)
        tally["artifact_meter_reserved"] += meter.write_bytes
        assert not proxy.fds
        good = mode in ('ok','empty','forced600')
        if good:
            assert error is None and result is not None
            st = (d/'artifact.json').stat()
            assert stat.S_IMODE(st.st_mode) == 0o400 and st.st_nlink == 1
            assert result.bytes == len(body) and result.sha256 == hashlib.sha256(body).hexdigest()
            order = [x[0] for x in proxy.trace]
            assert order.index('chmod') < order.index('fsync') < order.index('close')
            assert proxy.trace[-2:] == [('fsync','dir'),('close','dir')]
        else:
            assert error is not None and result is None
            if mode in ('zero','short'):
                assert sum(x[0] == 'write' for x in proxy.trace) == 1
                assert (d/'artifact.json').stat().st_size == (0 if mode == 'zero' else len(body)-1)
            if mode in ('chmod_close','fsync_close','parent_fsync_close'):
                expected = 'primary chmod' if mode == 'chmod_close' else 'primary sync'
                assert expected in str(error)
                notes = getattr(error,'__notes__',[])
                assert len(notes) == 1 and notes[0].startswith('artifact FD close also failed: ') and len(notes[0]) < 100
        rows.append({'case':'artifact_'+mode,'outcome':'sealed' if good else 'refused','meter_requested':meter.write_bytes,'harness_exact_FD_cleanup':cleanup,'target_close_success_claim':cleanup == 0})
    d = root/'old600'
    d.mkdir()
    old = d/'retained.json'
    put(old,payload,0o600,tally)
    before = old.stat()
    meter = M.ByteMeter(4096,4096)
    store = M.ArtifactStore(d,meter)
    old_ref = M.Artifact(str(old),len(payload),hashlib.sha256(payload).hexdigest(),'generated','operator','generated-regression')
    b = M.capture(old,4096,descriptor=old_ref,meter=meter)
    tally['read_requested'] += len(payload)+1
    assert b == payload
    proxy = Proxy('ok')
    original = M.os
    M.os = proxy
    try:
        copied = store.write('new.json',b,role='generated',visibility='operator',producer='generated-regression')
    finally:
        M.os = original
    assert not proxy.fds and stat.S_IMODE(Path(copied.path).stat().st_mode) == 0o400
    checked = M.capture(copied.path,4096,descriptor=copied,meter=meter)
    tally['read_requested'] += len(payload)+1
    assert checked == payload
    after = old.stat()
    assert (before.st_dev,before.st_ino,before.st_size,before.st_mode,before.st_mtime_ns,before.st_ctime_ns) == (after.st_dev,after.st_ino,after.st_size,after.st_mode,after.st_mtime_ns,after.st_ctime_ns)
    rows.append({'case':'byte_identical_copy_preserves_old600','outcome':'sealed_fresh_copy_old_unchanged'})
    refused(lambda: store.write('retained.json',payload,role='generated',visibility='operator',producer='generated-regression'))
    after = old.stat()
    assert after.st_ino == before.st_ino and after.st_mode == before.st_mode and meter.write_bytes == 2*len(payload)
    tally["artifact_meter_reserved"] += meter.write_bytes
    rows.append({'case':'exclusive_collision_old600','outcome':'refused_without_mutation','charged_requested':len(payload),'os_write_calls':0})
    bad_ref = M.Artifact(str(old),len(payload),'0'*64,'generated','operator','generated-regression')
    refused(lambda: M.capture(old,4096,descriptor=bad_ref,meter=meter))
    tally['read_requested'] += len(payload)+1
    rows.append({'case':'real_capture_bad_digest','outcome':'refused'})
    for name,raw in (('malformed',b'{'),('duplicate',b'{"x":1,"x":2}'),('nonfinite',b'{"x":NaN}')):
        path = d/(name+'.json')
        put(path,raw,0o600,tally)
        ref = M.Artifact(str(path),len(raw),hashlib.sha256(raw).hexdigest(),'generated','operator','generated-regression')
        refused(lambda: store.read_json(ref,roles={'generated'},cap=4096))
        tally['read_requested'] += len(raw)+1
        rows.append({'case':'actual_decoder_'+name,'outcome':'refused'})

def generated_cohort(M, R):
    expected = {'experiments':1936,'sessions':703,'mice':107,'rois':133066}
    rows, values, bodies, entries, planes = [], [], {}, [], []
    seeded = {i*4 for i in range(455)}
    counts = {}
    for i in range(1936):
        eid, sid, mouse = str(100000+i), str(200000+i%703), i%107
        rows.append({'ophys_experiment_id':eid,'ophys_session_id':sid,'mouse_id':str(mouse),
                     'split':'train' if mouse<73 else ('validation' if mouse<88 else 'test')})
        asset = {'experiment':eid,'url':'https://generated.invalid/'+eid,
                 'version_id':'generated-v1','etag':'"generated-'+eid+'"','extent_bytes':4096,
                 'provider_blake2b':'0'*128}
        values.append({**asset,'session':sid})
        counts[sid] = counts.get(sid,0)+1
        plane = {'experiment':eid,'session':sid,'status':'complete' if i in seeded else 'unattempted',
                 'stage':'layouts','artifacts':[]}
        if i in seeded:
            ah = hashlib.sha256(M.canonical(asset)).hexdigest()
            body = M.canonical({'schema':'neural063_range_layout_v1','experiment':eid,
                                'asset_sha256':ah,'fields':{},'array_values_decoded':False,
                                'full_object_BLAKE2b_verified':False})
            name = 'layout_'+eid+'.json'
            bodies[name] = body
            entry = {'experiment':eid,'session':sid,'name':name,'bytes':len(body),
                     'sha256':hashlib.sha256(body).hexdigest(),'asset_sha256':ah}
            entries.append(entry)
            plane.update(artifact_sha256=entry['sha256'],artifacts=[{
                'name':name,'bytes':len(body),'sha256':entry['sha256'],'role':'range_layout'}])
        planes.append(plane)
    assets = {'schema':'neural063_versioned_range_assets_v1','selection_sha256':R.SELECTION_SHA,
              'source_counts':expected,'assets':values}
    report = {'schema':'neural063_full_census_report_v1','stage':'layouts','complete':False,
              'bank':None,'source_counts':expected,'selection_sha256':R.SELECTION_SHA,
              'dff_values_decoded':False,'benchmark_ready':False,'full_object_BLAKE2b_verified':False,
              'planes':planes,'sessions':[{'session':s,'required_planes':n} for s,n in sorted(counts.items())]}
    seed = {'schema':'neural063_partial_layout_seed_v1','source_counts':expected,
            'selection_sha256':R.SELECTION_SHA,'assets_snapshot':None,'report':None,
            'source_root':'/generated/retained/old0600','seed_count':455,
            'body_bytes':sum(map(len,bodies.values())),'entries':entries}
    return {'rows':rows,'assets':assets,'report':report,'seed':seed,'bodies':bodies}

def pack_cohort(M, f):
    asset_body = M.canonical(f['assets'])
    assets_pin = {'bytes':len(asset_body),'sha256':hashlib.sha256(asset_body).hexdigest()}
    rb = M.canonical(f['report'])
    report_pin = {'bytes':len(rb),'sha256':hashlib.sha256(rb).hexdigest()}
    f['seed']['assets_snapshot'] = assets_pin
    f['seed']['report'] = {'path':f['seed']['source_root']+'/census_report.json',**report_pin}
    mb = M.canonical(f['seed'])
    config = {'manifest':{'bytes':len(mb),'sha256':hashlib.sha256(mb).hexdigest()},
              'report':report_pin,'seed_count':455,'seed_body_bytes':f['seed']['body_bytes'],
              'max_new_planes':400,'seed_read_bytes':len(mb)+len(rb)+f['seed']['body_bytes']+914,
              'provenance_bytes':1048576}
    return config,mb,rb,assets_pin

def rewrite_seed_body(M, f, mutate):
    entry = f['seed']['entries'][-1]
    body = M.decode(f['bodies'][entry['name']])
    mutate(body)
    raw = M.canonical(body)
    f['bodies'][entry['name']] = raw
    entry['bytes'], entry['sha256'] = len(raw),hashlib.sha256(raw).hexdigest()
    f['seed']['body_bytes'] = sum(e['bytes'] for e in f['seed']['entries'])
    p = next(p for p in f['report']['planes'] if p['experiment']==entry['experiment'])
    p.update(artifact_sha256=entry['sha256'],artifacts=[{
        'name':entry['name'],'bytes':entry['bytes'],'sha256':entry['sha256'],'role':'range_layout'}])

def admission_checks(M, R, base, rows):
    f = copy.deepcopy(base)
    config,mb,rb,ap = pack_cohort(M,f)
    calls = []
    def reader(name,size,sha):
        calls.append(name)
        return f['bodies'][name]
    admitted = R.admit_partial_layouts(config,mb,rb,f['assets'],reader,assets_pin=ap)
    assert len(calls)==455 and calls == [x['name'] for x in f['seed']['entries']]
    assert len(admitted['items'])==455 and admitted['new_provider_requests_for_import']==0
    rows.append({'case':'all455_admission_full1936','outcome':'admitted','body_callbacks':455,
                 'scope':'Actual typed admission; generated bodies and canonical roster in memory, not455 physical files.'})
    bads = ('raw_manifest_hash','last_body_hash','last_schema','last_experiment','last_asset',
            'array_decoded','asset_version','duplicate_seed','missing_seed','foreign_seed',
            'wrong_provenance','source_counts','partial_bank','complete_report','duplicate_assets','missing_assets')
    for kind in bads:
        f = copy.deepcopy(base)
        if kind == 'last_schema':
            rewrite_seed_body(M,f,lambda x:x.update(schema='wrong'))
        elif kind == 'last_experiment':
            rewrite_seed_body(M,f,lambda x:x.update(experiment='999999'))
        elif kind == 'last_asset':
            rewrite_seed_body(M,f,lambda x:x.update(asset_sha256='f'*64))
        elif kind == 'array_decoded':
            rewrite_seed_body(M,f,lambda x:x.update(array_values_decoded=True))
        elif kind == 'asset_version':
            eid=f['seed']['entries'][-1]['experiment']
            next(x for x in f['assets']['assets'] if x['experiment']==eid)['version_id']='different'
        elif kind == 'duplicate_seed':
            f['seed']['entries'][-1]=copy.deepcopy(f['seed']['entries'][0])
        elif kind == 'missing_seed':
            f['seed']['entries'].pop()
        elif kind == 'foreign_seed':
            f['seed']['entries'][-1]['experiment']='999999'
        elif kind == 'source_counts':
            f['seed']['source_counts']['experiments']=1935
        elif kind == 'partial_bank':
            f['report']['bank']={'schema':'neural063_range_layout_bank_v1'}
        elif kind == 'complete_report':
            f['report']['complete']=True
        elif kind == 'duplicate_assets':
            f['assets']['assets'][-1]=copy.deepcopy(f['assets']['assets'][0])
        elif kind == 'missing_assets':
            f['assets']['assets'].pop()
        config,mb,rb,ap=pack_cohort(M,f)
        if kind=='raw_manifest_hash':
            mb+=b' '
        elif kind=='wrong_provenance':
            bad=M.decode(mb);bad['report']['path']='/generated/wrong/census_report.json'
            mb=M.canonical(bad);config['manifest']={'bytes':len(mb),'sha256':hashlib.sha256(mb).hexdigest()}
        calls=[]
        def reader(name,size,sha):
            calls.append(name)
            b=f['bodies'][name]
            return b+b' ' if kind=='last_body_hash' and name==f['seed']['entries'][-1]['name'] else b
        exc=refused(lambda:R.admit_partial_layouts(config,mb,rb,f['assets'],reader,assets_pin=ap))
        if kind in ('last_body_hash','last_schema','last_experiment','last_asset','array_decoded'):
            assert len(calls)==455
        rows.append({'case':'admission_'+kind,'outcome':'refused','body_callbacks':len(calls),
                     'exception':type(exc).__name__,'provider_calls':0})
    config,mb,rb,ap=pack_cohort(M,copy.deepcopy(base))
    wrapper={'stage':'layouts','input_json_bytes':1048576,'local_read_bytes':4194304}
    R.validate_partial_config(config,wrapper)
    rows.append({'case':'finite400_config','outcome':'accepted'})
    for limit in (0,True,1482):
        mutant={**config,'max_new_planes':limit}
        refused(lambda:R.validate_partial_config(mutant,wrapper))
        rows.append({'case':'finite_config_refusal_'+str(limit),'outcome':'refused'})
    return admitted

def census_profile(C):
    return copy.deepcopy(TEST_PROFILE)

def real_primary_close_failure(M, root, body, tally):
    root.mkdir()
    meter=M.ByteMeter(4096,4096)
    store=M.ArtifactStore(root,meter)
    owned=[]
    class P:
        def __getattr__(self,n):return getattr(os,n)
        def open(self,*a,**kw):
            fd=os.open(*a,**kw);owned.append(fd);return fd
        def write(self,fd,b):
            tally['write_requested']+=len(b)
            n=os.write(fd,b);tally['write_confirmed']+=n;return n
        def fchmod(self,fd,mode):raise OSError('generated primary chmod for report')
        def close(self,fd):raise OSError('generated secondary close for report')
    old=M.os
    M.os=P()
    try:
        store.write('partial.json',body,role='generated',visibility='operator',producer='generated-regression')
    finally:
        M.os=old
        tally['artifact_meter_reserved']+=meter.write_bytes
        for fd in owned:os.close(fd)
    raise AssertionError('failure was required')

def core_environment(M,C,base,root,*,fail=None,tally=None):
    event=[]
    assets={}
    for row in base['assets']['assets']:
        assets[row['experiment']]=types.SimpleNamespace(**{k:row[k] for k in
            ('experiment','url','version_id','etag','extent_bytes','provider_blake2b')})
    data={}
    class Store:
        def __init__(self,path,meter):
            self.root=Path(path);self.meter=meter;self.data={};self.bodies={};self.oracle_bytes=0
            data['store']=self
        def write(self,name,body,**kw):
            self.meter.write(len(body))
            self.oracle_bytes+=len(body)
            assert self.oracle_bytes<=33554432
            event.append(('write',name))
            if fail=='copy_failure' and name=='layout_'+base['seed']['entries'][-1]['experiment']+'.json':
                exc=OSError('generated memory-store refusal')
                exc.add_note('artifact FD close also failed: OSError')
                raise exc
            if fail=='real_close_failure' and name.startswith('layout_'):
                real_primary_close_failure(M,root/'cross_layer_fd',body,tally)
            self.data[name]=M.decode(body)
            self.bodies[name]=body
            return M.Artifact(str(self.root/name),len(body),hashlib.sha256(body).hexdigest(),
                              kw['role'],kw['visibility'],kw['producer'],kw.get('media_type','application/json'))
    seeded={x['experiment'] for x in base['seed']['entries']}
    opened=[]
    class Context:
        def __enter__(self):return 'generated-layout-file'
        def __exit__(self,*a):return False
    def open_versioned(asset,ranges,versions):
        eid=asset.experiment
        if eid in seeded:raise ForbiddenProvider('seed reached provider seam')
        assert len([x for x in event if x[0]=='write' and x[1].startswith('layout_')])>=455
        assert ('write','partial_layout_provenance.json') in event
        opened.append(eid);event.append(('open',eid))
        if fail=='deadline' and len(opened)==2:raise TimeoutError('generated deadline')
        return Context()
    budget_calls=[]
    class Limits:
        def __init__(self,**kw):self.kw=kw
        def validate(self):return self
    class Budget:
        def __init__(self,limits):
            budget_calls.append('constructed')
            event.append(('budget',None))
        def receipt(self):return {'failed':False,'ranges':[{'experiment':e} for e in opened],'generated':True}
    digest=lambda x:hashlib.sha256(M.canonical(x)).hexdigest()
    pipe=types.SimpleNamespace(full_scope=lambda x:base['rows'],validate_assets=lambda a,s:assets,
        digest=digest,SELECTION_SHA256=base['assets']['selection_sha256'],EXPECTED=base['assets']['source_counts'],
        field_layouts=lambda file,native:{})
    rng=types.SimpleNamespace(canonical=M.canonical,open_versioned=open_versioned,Limits=Limits,Budget=Budget)
    deps=types.SimpleNamespace(pipeline=pipe,range=rng,native=object(),io=M,
                              manifest=types.SimpleNamespace(validate_assets=lambda a,s:None))
    return types.SimpleNamespace(Store=Store,deps=deps,data=data,event=event,opened=opened,budget_calls=budget_calls)

def core_checks(M,R,C,base,admitted,root,rows,tally):
    profile=census_profile(C)
    original=C.structure_admission
    C.structure_admission=lambda file,native,p:None
    try:
        for case in ('finite400','deadline','copy_failure','full_union','partial_bank','copy_digest'):
            env=core_environment(M,C,base,root,fail=case,tally=tally)
            store=env.Store(root/case,M.ByteMeter(4194304,profile['total_artifact_reservation_bytes']))
            part=copy.deepcopy(admitted)
            if case=='full_union':part['max_new_planes']=1481
            if case=='copy_digest':part['items'][-1]['body']+=b' '
            if case in ('partial_bank','copy_digest'):
                refused(lambda:C.run_census({},base['assets'],deps=env.deps,store=store,ranges=object(),
                    profile=profile,input_bank={} if case=='partial_bank' else None,partial_layouts=part))
                assert not env.opened and not store.data
                rows.append({'case':'core_'+case,'outcome':'refused_before_provider_and_publication'})
                continue
            C.run_census({},base['assets'],deps=env.deps,store=store,ranges=object(),
                         profile=profile,partial_layouts=part)
            report=store.data['census_report.json']
            eligible=[r['ophys_experiment_id'] for r in base['rows'] if r['ophys_experiment_id'] not in
                      {x['entry']['experiment'] for x in part['items']}]
            assert len(eligible)==1481
            if case=='finite400':
                assert env.opened==eligible[:400]
                assert report['bounded_step_complete'] is True and report['complete'] is False and report['bank'] is None
                assert sum(p['status']=='complete' for p in report['planes'])==855
                assert len(report['planes'])==1936 and len(report['sessions'])==703
            elif case=='full_union':
                assert env.opened==eligible and report['complete'] is True and report['bank'] is not None
                bank=store.data['layout_bank.json']
                assert [x['experiment'] for x in bank['entries']]==[r['ophys_experiment_id'] for r in base['rows']]
            else:
                assert report['bounded_step_complete'] is False and report['complete'] is False and report['bank'] is None
                assert len(env.opened)==(2 if case=='deadline' else 0)
                if case=='copy_failure':
                    assert report['failure_evidence']['secondary_close_failure_recorded'] is True
                    assert report['uncertified_write_attempts'][-1]['certified_artifact'] is False
            rows.append({'case':'core_'+case,'outcome':'expected_disposition','opened_oracle_count':len(env.opened),
                         'complete':report['complete'],'bounded_step_complete':report['bounded_step_complete'],
                         'scope':'Actual core/Writer; generated full roster and bounded memory-store/structural-reader oracles.'})
    finally:C.structure_admission=original

def entry_checks(M,R,C,base,root,rows,tally):
    import contextlib
    import io as streamio
    import importlib.metadata
    original_version=importlib.metadata.version
    old={n:getattr(R,n) for n in ('read_profile','validate_operation_profile','load_sources','capture_input','os')}
    old_structure=C.structure_admission
    try:
        importlib.metadata.version=lambda name:C.RUNTIME[name]
        C.structure_admission=lambda file,native,p:None
        for case in ('valid400','last_seed_invalid','real_secondary_close'):
            f=copy.deepcopy(base)
            config,mb,rb,ap=pack_cohort(M,f)
            env=core_environment(M,C,f,root/case,fail='real_close_failure' if case=='real_secondary_close' else None,tally=tally)
            profile=copy.deepcopy(TEST_OPERATION_PROFILE)
            profile.update(selected=True,runtime_qualified=True,partial_layouts=config)
            profile['input_pins']['assets']=ap
            callbacks=[]
            def capture(path,cap,*,descriptor=None,meter=None):
                name=Path(path).name
                if name=='seed_manifest.json':b=mb
                elif name=='census_report.json':b=rb
                else:
                    callbacks.append(name)
                    b=f['bodies'][name]
                    if case=='last_seed_invalid' and name==f['seed']['entries'][-1]['name']:b+=b' '
                if meter:meter.read(len(b))
                return b
            io_oracle=types.SimpleNamespace(**{n:getattr(M,n) for n in
                ('Artifact','ByteMeter','canonical','ordinary')},ArtifactStore=env.Store,capture=capture)
            env.deps.io=io_oracle
            old_budget=env.deps.range.Budget
            def budget(limits):
                assert len(callbacks)==455
                env.event.append(('all455_validated',None))
                return old_budget(limits)
            env.deps.range.Budget=budget
            R.read_profile=lambda *a:profile
            R.load_sources=lambda *a:(C,env.deps)
            R.capture_input=lambda path,desc,role,deps,meter:({'original_selection':{}} if role=='source_selection' else f['assets'])
            class OS:
                def __getattr__(self,n):return getattr(os,n)
                def statvfs(self,p):return types.SimpleNamespace(f_bavail=1000000000,f_frsize=4096)
            R.os=OS()
            parent=root/case
            parent.mkdir()
            argv=['--profile',str(parent/'profile.json'),'--profile-sha256','0'*64,
                  '--selection',str(parent/'selection.json'),'--assets',str(parent/'assets.json'),
                  '--range-source-root',str(parent/'range'),'--original-root',str(parent/'original'),
                  '--partial-layouts',str(parent/'seed_manifest.json'),'--partial-root','/generated/retained/old0600',
                  '--output',str(parent/'output'),'--execute-authentic']
            stream=streamio.StringIO()
            with contextlib.redirect_stdout(stream):rc=R.main(argv)
            assert len(stream.getvalue())<=8192
            store=env.data['store']
            receipt=store.data['operation_receipt.json']
            assert len(callbacks)==455
            if case=='last_seed_invalid':
                assert rc==1 and not env.budget_calls and not env.opened
                assert list(store.data)==['operation_receipt.json'] and receipt['scope_entered'] is False
                assert receipt['failure'] is not None and receipt['bounded_step_complete'] is False
            elif case=='valid400':
                assert rc==0 and len(env.budget_calls)==1 and len(env.opened)==400
                assert receipt['complete'] is False and receipt['bounded_step_complete'] is True and receipt['bank'] is None
                assert env.event.index(('all455_validated',None))<env.event.index(('budget',None))
            else:
                assert rc==1 and len(env.budget_calls)==1 and not env.opened
                report=store.data['census_report.json']
                evidence=report['failure_evidence']
                assert evidence['message']=='generated primary chmod for report'
                assert evidence['secondary_close_failure_recorded'] is True
                assert evidence['descriptor_custody']=='not_established_by_error_receipt'
                assert report['uncertified_write_attempts'][0]['failure_evidence']['secondary_close_failure_recorded'] is True
                assert receipt['complete'] is False and receipt['bounded_step_complete'] is False
            rows.append({'case':'entry_'+case,'outcome':'expected_entry_sequence','seed_callbacks':len(callbacks),
                         'budget_constructors':len(env.budget_calls),'open_oracles':len(env.opened),
                         'scope':'Actual main/admission/core with explicit bootstrap/runtime/capture/store/structure oracles; actual original/provider execution forbidden.'})
    finally:
        for n,v in old.items():setattr(R,n,v)
        C.structure_admission=old_structure
        importlib.metadata.version=original_version

def main():
    global TEST_PROFILE, TEST_OPERATION_PROFILE
    if sys.flags.optimize:
        raise ValueError("assertion-enabled interpreter required")
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--artifact-root',required=True)
    args=ap.parse_args()
    component=Path(__file__).absolute().parents[1]
    descriptor_ref={'path':str(component/'tests'/'PARTIAL_RESUME_SOURCES.json'),**SOURCE_DESCRIPTOR}
    descriptor=json.loads(read_source(descriptor_ref))
    if descriptor['schema']!='neural063-public-partial-resume-sources/v1' or set(descriptor['sources'])!={'io','run','census','dependencies','profile'}:
        raise ValueError('exact portable source closure required')
    refs={key:{**ref,'path':str(component/ref['path'])} for key,ref in descriptor['sources'].items()}
    sources={key:read_source(ref) for key,ref in refs.items()}
    artifact_root=Path(args.artifact_root).absolute()
    if artifact_root.exists() or artifact_root.is_symlink() or not artifact_root.parent.is_dir():
        raise ValueError('fresh artifact namespace with existing parent required')
    if component==artifact_root or component in artifact_root.parents:
        raise ValueError('artifact namespace must be outside component source')
    artifact_root.mkdir(mode=0o700)
    root=artifact_root/'fixtures'
    root.mkdir(mode=0o700)
    result_path=artifact_root/'RESULT.json'
    source_paths={str(Path(__file__).absolute()),str(Path(descriptor_ref['path']).absolute())}
    source_paths.update(str(Path(ref['path']).absolute()) for ref in refs.values())
    forbidden=[]
    def audit(event,values):
        if event in ('subprocess.Popen','os.system','os.posix_spawn','os.fork','os.exec',
                     'socket.__new__','socket.connect','socket.getaddrinfo'):
            forbidden.append(event)
            raise ForbiddenProvider(event)
        if event=='open' and isinstance(values[0],(str,bytes,os.PathLike)):
            path=Path(os.fsdecode(values[0])).absolute()
            flags=values[2] if len(values)>2 and isinstance(values[2],int) else 0
            write=bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
            allowed=(path==root or root in path.parents or path==result_path)
            if write and not allowed:raise ForbiddenProvider('write outside generated namespace')
            if not write and not allowed and str(path) not in source_paths:
                raise ForbiddenProvider('read outside selected source/generated namespace')
        if event in ('os.mkdir','os.remove','os.rmdir','os.rename','os.scandir'):
            target=values[0]
            if isinstance(target,(str,bytes,os.PathLike)):
                path=Path(os.fsdecode(target)).absolute()
                if path!=root and root not in path.parents:raise ForbiddenProvider('filesystem action outside fixture')
    sys.addaudithook(audit)
    rows=[];phase='source_import';failure=None
    tally={'write_requested':0,'write_confirmed':0,'harness_write_requested':0,
           'artifact_meter_reserved':0,'read_requested':0}
    try:
        M=module_from('generated_partial_io',refs['io'],sources['io'])
        R=module_from('generated_partial_run',refs['run'],sources['run'])
        C=module_from('generated_partial_census',refs['census'],sources['census'])
        TEST_OPERATION_PROFILE=json.loads(sources['profile'])
        assert TEST_OPERATION_PROFILE['selected'] is False and TEST_OPERATION_PROFILE['runtime_qualified'] is False
        TEST_OPERATION_PROFILE['component_pins']={name:{key:refs[label][key] for key in ('bytes','sha256')}
            for name,label in (('run.py','run'),('census.py','census'),('DEPENDENCIES.json','dependencies'))}
        TEST_OPERATION_PROFILE['input_pins']['selection']={'bytes':R.SELECTION_BYTES,'sha256':R.SELECTION_SHA}
        TEST_PROFILE=TEST_OPERATION_PROFILE['core']
        phase='artifact_sealing';artifact_root_fixture=root/'artifacts';artifact_root_fixture.mkdir()
        artifact_checks(M,artifact_root_fixture,rows,tally)
        phase='cohort_admission';base=generated_cohort(M,R)
        admitted=admission_checks(M,R,base,rows)
        phase='core';core_root=root/'core';core_root.mkdir()
        core_checks(M,R,C,base,admitted,core_root,rows,tally)
        phase='entry';entry_root=root/'entry';entry_root.mkdir()
        entry_checks(M,R,C,base,entry_root,rows,tally)
        assert [row['case'] for row in rows]==EXPECTED_CONTROLS and not forbidden
        assert tally['harness_write_requested']+tally['artifact_meter_reserved']<=16384
        assert tally['read_requested']<=32768
    except BaseException as exc:
        frames=[];tb=exc.__traceback__
        while tb is not None and len(frames)<8:
            frames.append({'file':Path(tb.tb_frame.f_code.co_filename).name,
                           'function':tb.tb_frame.f_code.co_name,'line':tb.tb_lineno})
            tb=tb.tb_next
        failure={'class':type(exc).__name__,'message':str(exc)[:256],'phase':phase,'frames':frames}
    result={'schema':'neural063-public-partial-resume-generated-result/v1',
            'status':'passed' if failure is None else 'failed','expected':53,'count':len(rows),
            'failure':failure,'cases':rows,'sources':descriptor['sources'],
            'source_read_requested':SOURCE_READ,'source_read_observed':SOURCE_OBSERVED,
            'generated_effects':tally,'denied_process_network_events':forbidden,
            'original_data_provider_Docker_native_calls':0,'excluded_private_controls':16,
            'scope':['Real small generated-file/FD sealing and immutable old-file checks.',
                     'Actual typed admission/main/core/Writer control flow uses explicit full1936/455/855 metadata and structural/runtime/publication oracles.',
                     'No private host driver, host staging or host output-verifier controls are imported or claimed.',
                     'No claim of physical455 seed or855 output custody, actual maintained transport, container resources, original data or benchmark readiness.',
                     'Memory-store meter/serialization counts are generated in-memory oracle effects, not filesystem writes or acquired data.',
                     'Injected close failures are not called successful cleanup; the harness closes only its exact remaining generated FDs.']}
    body=(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    assert len(body)<=24576
    fd=os.open(result_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        n=os.write(fd,body)
        if n!=len(body):raise RuntimeError('partial result write; preserve, no retry')
    finally:os.close(fd)
    summary={'controls':[{'id':row['case'],'status':'pass'} for row in rows],
             'generated_only':True,'provider_requests':0,'original_array_reads':0,
             'benchmark_ready':False,'excluded_private_controls':16,
             'status':'passed' if failure is None else 'failed'}
    print(json.dumps(summary,sort_keys=True,separators=(',',':')))
    return 0 if failure is None else 1
if __name__=='__main__':
    raise SystemExit(main())
