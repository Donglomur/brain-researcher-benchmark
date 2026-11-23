"""REVE development -> frozen programme -> full unlabeled test source owner.

Enforces custody/files/chronology, not semantic inductivity or GPU authority.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
RECIPE = HERE.parent/'matched-reference-v1/recipe.py'
RECIPE_SHA = '83a85f43997b83839e2462470778af36558beda0e9c7707db060395b4323b470'
raw = RECIPE.read_bytes()
if hashlib.sha256(raw).hexdigest() != RECIPE_SHA: raise ValueError('matched recipe source changed')
spec = importlib.util.spec_from_file_location('_reve_boundary_recipe',RECIPE)
r = importlib.util.module_from_spec(spec);exec(compile(raw,str(RECIPE),'exec'),r.__dict__)
a = r.adapter()
need = r.need
ARTIFACT_FILES = {'selected.py','model.bin'}
CHANNELS = a.materials_module().CHANNELS
PROFILES = ('original-like-no-target-calibration-v1','frozen-program-full-test-context-v1')


def pin_json(document): return a.pin(a.canonical(document)+b'\n')


def views_module():
    spec=importlib.util.spec_from_file_location('_reve_boundary_views',HERE/'views.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def file_mount(path, purpose, pin):
    path = Path(path);need(path.is_absolute(), 'absolute private host source path')
    a.descriptor(pin)
    return {'path':str(path),'kind':'file','purpose':purpose,'files':{path.name:dict(pin)}}


def development_mounts(info, data_mount, paper_path, common_root, common_files, program, code_path=None):
    mounts={'/input':data_mount,'/paper/paper.pdf':file_mount(paper_path,'paper',{k:info['paper'][k] for k in ('bytes','sha256')}),
            '/common':r.primary_common(common_root,common_files),
            '/candidate/develop.py':file_mount(program['path'],'program',program['pin'])}
    if info['role']=='B':
        need(code_path is not None,'official source required for code arm')
        mounts['/official/code.tar.gz']=file_mount(code_path,'historical_author_source',{k:info['official_code'][k] for k in ('bytes','sha256')})
    else:need(code_path is None,'no official source in primary paper arm')
    return mounts


def inference_mounts(data_mount,artifact):
    mounts={'/input':data_mount}
    for name,pin in artifact['files'].items():mounts['/candidate/'+name]=file_mount(Path(artifact['root'])/name,'program',pin)
    mounts['/candidate/FROZEN.json']=file_mount(Path(artifact['root'])/'FROZEN.json','contract',artifact['manifest_pin'])
    return mounts


def phase_request(*, phase_id, role, image, exposure, mounts, kind, origin, deadline, resources):
    _,contract,_ = a.transport_package()
    need(kind in ('development','inference'), 'known REVE boundary phase')
    command = ['/usr/local/bin/python','-I','-B', '/candidate/develop.py' if kind == 'development' else '/candidate/selected.py']
    source_files = {target:desc['files'] for target,desc in mounts.items() if target.startswith('/candidate/')}
    request = {'schema':'osl_owned_phase_request_v1','phase_id':phase_id,'action':'held_attempt','role':role,
               'image':image,'command':command,'workdir':'/work','source':a.pin(a.canonical(source_files)),
               'exposure':a.descriptor(exposure),'clock':{'origin':origin,'phase_deadline':deadline},
               'resources':dict(resources),'output':{'kind':'generic','manifest':'OUTPUTS.json'}}
    contract.validate_request(request,mounts,deadline)
    minimum = 2*sum(pin['bytes'] for desc in mounts.values() for pin in desc['files'].values())
    need(resources['source_read_bytes'] > minimum, 'full before/after mount authentication plus overhead')
    need(resources['max_directories'] == 1 and resources['max_files'] == (4 if kind == 'development' else 2), 'exact phase output cardinality')
    if kind == 'inference':
        need(resources['max_file_bytes'] <= a.RESULT_CAP and resources['manifest_bytes'] <= 65536, 'one bounded complete test result')
    return {'kind':kind,'request':request,'mounts':mounts,'minimum_hash_reads':minimum}


def only_pin(desc):
    need(type(desc) is dict and set(desc)=={'path','kind','purpose','files'} and desc['kind']=='file' and
         set(desc['files'])=={Path(desc['path']).name}, 'one exact file bind; no parent directory exposure')
    pin=next(iter(desc['files'].values()));a.descriptor(pin);return pin


def observe_capture(provider, bundle, returned, deadline, *, output_names):
    """Exact same Provider observer, with REVE phase-specific output admission."""
    p,contract,bounds = a.transport_package()
    need(type(provider) is p.Provider, 'exact pinned provider only')
    request = bundle['request']; request_sha = a.pin(p.encoded(request))['sha256']
    observed = provider.observe(request['phase_id'],request_sha,returned['receipt_pin'],deadline)
    receipt = observed['receipt']; need(receipt == returned['receipt'], 'independent receipt differs')
    need(receipt['schema'] == 'osl_owned_phase_receipt_v1' and receipt['status'] == 'captured' and
         receipt['phase_id'] == request['phase_id'] and receipt['request_sha256'] == request_sha and
         all(receipt[k] == request[k] for k in ('action','role','image','source','exposure')), 'current exact phase binding')
    need(receipt['all_native_resources_closed'] is True and receipt['cli_reaped'] is True and
         receipt['producer_closed_before_capture'] is True and receipt['error'] is None and receipt['oom'] is False and
         receipt['deadline_exceeded'] is False, 'successful complete closure before any exposure transition')
    closed = receipt['retired_resources']
    need(len(closed) == 3 and sorted(x['kind'] for x in closed) == ['container','container','volume'] and
         len({x['name'] for x in closed}) == 3 and all(x['closed'] is True and x.get('absence_observed') is True and
         x.get('creation_outcome_unknown') is False for x in closed), 'three distinct absent owned resources')
    p.validate_cli_records(receipt['command_metadata'],p.caps(request['resources']['inventory_bytes']))
    p.validate_natural_exit(receipt['natural_exit'])
    need(receipt['input_before'] == receipt['input_after'] == bounds.mount_identity(bundle['mounts']) and
         receipt['enforced_resource_limits'] == request['resources'] and
         receipt['timing']['original_deadline'] == deadline and receipt['qualification_inherited'] is False and
         receipt['scientific_qualification'] is False, 'unchanged phase inputs/budget/original clock')
    timing=receipt['timing']
    need(all(type(timing[k]) in (int,float) and math.isfinite(timing[k]) for k in ('started','finished')) and
         request['clock']['origin'] <= timing['started'] <= timing['finished'] <= deadline,
         'finite ordered receipt chronology within original episode')
    capture = receipt['output_inventory']; need(capture['complete'] is True and
        set(capture['files']) == set(output_names)|{'OUTPUTS.json'}, 'exact phase-specific output files')
    root = provider.quarantine_root/request['phase_id']
    need(Path(receipt['quarantine_root']) == root, 'private owned capture root')
    remaining = provider.read_limit-provider.read_used
    need(remaining > 0, 'whole provider read budget exhausted')
    meter = bounds.Meter(remaining,1,deadline)
    try:
        envelope = p.parse(bounds.body(root/'OUTPUTS.json',capture['files']['OUTPUTS.json'],meter,65536))
        inventory = {'files':[{'name':name,'bytes':pin['bytes']} for name,pin in capture['files'].items()]}
        declared = contract.output_files(envelope,request,request_sha,inventory)
        need(set(declared) == set(output_names), 'complete declared output membership')
        result = p.parse(bounds.body(root/'RESULT.json',declared['RESULT.json'],meter,a.RESULT_CAP if bundle['kind']=='inference' else 65536))
    finally: provider.read_used += meter.read_bytes
    return {'result':result,'files':declared,'root':str(root),'receipt_pin':returned['receipt_pin'],
            'receipt_started':timing['started'],'receipt_finished':timing['finished'],'retired_resources':deepcopy(closed)}


def promote_selected(provider,capture, output, freeze_fields, deadline):
    """Owned exact-byte copy, using the already reviewed material publication code.

    Prospective copied extents are charged conservatively even on a partial
    failure. This is preparation, not execution/chronology authority.
    """
    m = a.materials_module(); output = Path(output)
    need(output.is_absolute() and not output.exists(), 'fresh explicit frozen artifact destination')
    pins = {name:capture['files'][name] for name in ARTIFACT_FILES}
    for pin in pins.values(): a.descriptor(pin)
    artifact = {'schema':'reve-frozen-candidate-v2',**deepcopy(freeze_fields),'files':pins}
    artifact['artifact_identity'] = r.identity(artifact)
    stage = output.parent/(output.name+'.staging')
    need(not stage.exists(), 'fresh owned staging tree')
    charge = sum(pin['bytes'] for pin in pins.values()) + len(a.canonical(artifact))+1
    read_charge=sum(pin['bytes']+1 for pin in pins.values())
    need(time.monotonic()<deadline and provider.read_used+read_charge<=provider.read_limit and
         provider.write_used+charge<=provider.write_limit,'prospective whole-provider promotion allowance')
    # Conservative debit is retained on all failures; no budget refresh/refund.
    provider.read_used+=read_charge;provider.write_used+=charge
    stage.mkdir(mode=0o700); stat = stage.stat(); owner = (stat.st_dev,stat.st_ino)
    try:
        for name,pin in pins.items():
            digest=hashlib.sha256()
            with m.regular(Path(capture['root'])/name,pin['bytes']) as (source,size):
                need(size==pin['bytes'],'exact selected artifact extent')
                with (stage/name).open('xb') as out:
                    remaining=size
                    while remaining:
                        need(time.monotonic()<deadline,'original deadline during promotion')
                        chunk=source.read(min(1024*1024,remaining));need(chunk,'truncated selected artifact')
                        need(out.write(chunk)==len(chunk),'complete artifact write');digest.update(chunk);remaining-=len(chunk)
                    need(source.read(1)==b'' and digest.hexdigest()==pin['sha256'],'unchanged selected artifact')
                    out.flush();os.fchmod(out.fileno(),0o444);os.fsync(out.fileno())
        need(time.monotonic()<deadline,'original deadline before publication')
        m._write_json(stage/'FROZEN.json',artifact); m.publish(stage,output)
    except BaseException as error:
        error.conservative_copy_write_charge_bytes = charge
        if stage.exists(): m.discard_owned_tree(stage,owner)
        raise
    return {**artifact,'root':str(output),'manifest_pin':pin_json(artifact),
            'conservative_copy_write_charge_bytes':charge,'conservative_copy_read_charge_bytes':read_charge}


class Episode:
    """Trusted, in-memory, non-resumable chronology; JSON cannot resume it.

    This owner cannot prove semantic inductivity, supply GPU qualification, or
    admit a campaign budget. Execution retains the existing closed runtime gate.
    One distinct Provider per episode; the admitted campaign owns total budgets.
    """
    def __init__(self, document, *, expected_materials_identity, expected_panel_identity,
                 episode_id, origin, deadline, profile, declaration,
                 development_resources, inference_resources):
        v=views_module()
        compiled=v.compile_views(document,expected_materials_identity,expected_panel_identity)
        self.info=compiled['info'];self.development=compiled['development'];self.test=compiled['test']
        need(type(episode_id)is str and a.HEX.fullmatch(episode_id),'externally planned episode identity')
        need(type(origin)in(int,float) and type(deadline)in(int,float) and math.isfinite(origin) and
             math.isfinite(deadline) and 0<=origin<deadline,'one original episode clock')
        need(profile in PROFILES,'explicit supported scientific access profile')
        need(type(declaration)is dict and set(declaration)=={'uses_unlabeled_test_context','description'} and
             type(declaration['uses_unlabeled_test_context'])is bool and type(declaration['description'])is str and
             0<len(declaration['description'])<=4096,'bounded predeclared method; not semantic qualification')
        need(profile!=PROFILES[0] or declaration['uses_unlabeled_test_context'] is False,
             'current original-like condition cannot declare target-context adaptation')
        _,contract,_=a.transport_package()
        for resources in (development_resources,inference_resources):
            need(type(resources)is dict and set(resources)==contract.RESOURCE_KEYS and
                 all(type(value)is int and value>0 for value in resources.values()),'fixed prospective resource operands')
        span=sum(resources[k] for resources in (development_resources,inference_resources)
                 for k in ('setup_seconds','producer_seconds','capture_seconds','cleanup_seconds'))
        need(deadline-origin>span,'original clock must accommodate both phases and freeze')
        self.id=episode_id;self.origin=origin;self.deadline=deadline;self.profile=profile
        self.declaration=deepcopy(declaration)
        self.development_resources=deepcopy(development_resources);self.inference_resources=deepcopy(inference_resources)
        self.state='development';self.artifact=None;self.results=None;self.barrier=None
        self.freeze_time=None;self.freeze_receipt_pin=None;self.image=None;self.closed_names=set();self.phase_ids=set()
        self.provider=None;self.provider_binding=None;self.exposures=None;self.last_read_used=None;self.last_write_used=None
        self.design_identity=r.identity(self._design())

    def _design(self):
        return {'episode_id':self.id,'role':self.info['role'],'data_identity':self.info['data_identity'],
                'materials_identity':self.info['materials_identity'],'development':self.development['view_identity'],
                'test':self.test['view_identity'],'profile':self.profile,'declaration':self.declaration,
                'development_resources':self.development_resources,'inference_resources':self.inference_resources,
                'origin':self.origin,'deadline':self.deadline}

    def _unchanged(self):
        need(r.identity(self._design())==self.design_identity,'episode design fixed before development')
        views_module().validate_view(self.development);views_module().validate_view(self.test)

    def _provider_identity(self,provider):
        return (provider.control_root,provider.quarantine_root,provider.binary,provider.socket,
                provider.read_limit,provider.write_limit,a.canonical(provider.engine_pin))

    def _clock_and_role(self,bundle,kind):
        self._unchanged();request=bundle['request']
        need(bundle['kind']==kind and request['role']==self.info['role'] and
             request['clock']=={'origin':self.origin,'phase_deadline':self.deadline},'same role and original clock')
        need(time.monotonic()<self.deadline,'original episode expired')
        rebuilt=phase_request(phase_id=request['phase_id'],role=self.info['role'],image=request['image'],
                              exposure=request['exposure'],mounts=bundle['mounts'],kind=kind,
                              origin=self.origin,deadline=self.deadline,
                              resources=self.development_resources if kind=='development' else self.inference_resources)
        need(bundle==rebuilt,'exact fixed phase request, mounts and resource operands')
        need(request['phase_id'] not in self.phase_ids,'one fresh attempt per phase; no replay')
        self.phase_ids.add(request['phase_id'])

    def _development_membership(self,mounts):
        expected={'/input','/paper/paper.pdf','/common','/candidate/develop.py'}
        if self.info['role']=='B':expected.add('/official/code.tar.gz')
        need(set(mounts)==expected,'only development data and literal condition assets')
        views_module().validate_mount(self.development,mounts['/input'])
        need(mounts['/paper/paper.pdf']['purpose']=='paper' and only_pin(mounts['/paper/paper.pdf'])==
             {k:self.info['paper'][k] for k in ('bytes','sha256')},'exact source paper')
        need(mounts['/common']==r.primary_common(mounts['/common']['path'],mounts['/common']['files']),
             'weights/config/architecture/license only; no author implementation in A')
        need(mounts['/candidate/develop.py']['purpose']=='program','candidate development source')
        only_pin(mounts['/candidate/develop.py'])
        if self.info['role']=='B':
            need(mounts['/official/code.tar.gz']['purpose']=='historical_author_source' and
                 only_pin(mounts['/official/code.tar.gz'])=={k:self.info['official_code'][k] for k in ('bytes','sha256')},
                 'exact official source for B only')

    def _closed(self,capture):
        names={x['name'] for x in capture['retired_resources']}
        need(not names & self.closed_names,'native resource reuse across phases')
        self.closed_names.update(names)

    def develop_and_freeze(self,provider,*,bundle,journal,frozen_output):
        r.require_installation()
        need(self.state=='development' and self.barrier is not None,'development only in registered campaign')
        self.barrier.ready_for_development(self)
        try:
            self._clock_and_role(bundle,'development')
            p,_,_=a.transport_package();need(type(provider)is p.Provider,'exact pinned Provider before dispatch')
            self._development_membership(bundle['mounts'])
            returned=provider.execute_phase(bundle['request'],bundle['mounts'],self.deadline,journal)
            capture=observe_capture(provider,bundle,returned,self.deadline,output_names=ARTIFACT_FILES|{'RESULT.json'})
            expected={'schema':'reve-development-selection-v2','episode_id':self.id,
                      'development_identity':self.development['view_identity'],
                      'selected_files':{name:capture['files'][name] for name in ARTIFACT_FILES}}
            need(capture['result']==expected,'selected code/model captured from this exact development episode')
            self._closed(capture)
            frozen={'episode_id':self.id,'role':self.info['role'],'profile':self.profile,
                    'declaration':self.declaration,'design_identity':self.design_identity,
                    'development_identity':self.development['view_identity'],'test_identity':self.test['view_identity'],
                    'inference_resources':self.inference_resources}
            self.artifact=promote_selected(provider,capture,frozen_output,frozen,self.deadline)
            self.freeze_time=time.monotonic()
            need(capture['receipt_finished']<=self.freeze_time<self.deadline,'development closes before immutable freeze')
            self.provider=provider;self.provider_binding=self._provider_identity(provider)
            self.exposures=deepcopy(provider.exposures)
            self.last_read_used=provider.read_used;self.last_write_used=provider.write_used
            self.freeze_receipt_pin=capture['receipt_pin'];self.image=bundle['request']['image'];self.state='frozen'
            return {'artifact_identity':self.artifact['artifact_identity'],'development_receipt_pin':self.freeze_receipt_pin,
                    'frozen_at':self.freeze_time,'runtime_qualified':False,'scientific_qualification':False}
        except BaseException:self.state='failed';raise

    def run_inference(self,provider,*,bundle,journal):
        r.require_installation()
        need(self.state=='frozen' and self.barrier is not None,'one complete test phase after genuine freeze')
        self.barrier.ready_for_inference(self)
        try:
            self._clock_and_role(bundle,'inference')
            p,_,_=a.transport_package();need(type(provider)is p.Provider,'exact pinned Provider before dispatch')
            need(provider is self.provider and self._provider_identity(provider)==self.provider_binding and
                 provider.read_used>=self.last_read_used and provider.write_used>=self.last_write_used,
                 'same Provider and cumulative original read/write budgets')
            # The held exposure can only be approved after artifact hashes exist.
            # This append is an operator-pinned path, not an approval authority;
            # Provider still authenticates the exact body's independent approval.
            key=bundle['request']['exposure']['sha256']
            need(all(provider.exposures.get(k)==v for k,v in self.exposures.items()) and
                 set(provider.exposures)-set(self.exposures)<= {key} and key in provider.exposures,
                 'preserve approvals; only this exact held exposure may be appended')
            need(bundle['request']['image']==self.image,'unchanged selected runtime image')
            mounts=bundle['mounts'];views_module().validate_mount(self.test,mounts['/input'])
            need(mounts==inference_mounts(mounts['/input'],self.artifact),
                 'complete unlabeled test data and exact frozen code/model/contract only')
            returned=provider.execute_phase(bundle['request'],mounts,self.deadline,journal)
            capture=observe_capture(provider,bundle,returned,self.deadline,output_names={'RESULT.json'})
            need(capture['receipt_started']>=self.freeze_time,'test process starts after freeze')
            self._closed(capture);result=capture['result']
            need(type(result)is dict and set(result)=={'schema','artifact_identity','predictions'} and
                 result['schema']=='reve-frozen-dataset-result-v1' and
                 result['artifact_identity']==self.artifact['artifact_identity'],'current complete frozen-program result')
            admitted=a.admit_result({'schema':'reve-candidate-predictions-v1',
                                     'materials_identity':self.info['materials_identity'],
                                     'predictions':deepcopy(result['predictions'])},self.info)
            self.results=admitted;self.state='complete'
            self.last_read_used=provider.read_used;self.last_write_used=provider.write_used
            return {'predictions_collected':1803,'complete':True,'scientific_qualification':False}
        except BaseException:self.state='failed';raise

    def complete_predictions(self):
        need(self.barrier is not None,'private evaluator requires complete campaign barrier')
        campaign=self.barrier.release()
        predictions=a.admit_result(deepcopy(self.results),self.info)
        release={'schema':'reve-protected-prediction-release-v1','episode_id':self.id,
                 'role':self.info['role'],'profile':self.profile,'declaration':deepcopy(self.declaration),
                 'artifact_identity':self.artifact['artifact_identity'],'design_identity':self.design_identity,
                 'roster_identity':campaign['roster_identity'],'materials_identity':self.info['materials_identity'],
                 'predictions_pin':pin_json(predictions),'complete_test_epochs':1803,
                 'scientific_qualification':False,'current_paper_win_qualified':False,
                 'requires_separate_outcome_binding':self.profile==PROFILES[1]}
        release['release_identity']=r.identity(release)
        return {'release':release,'predictions':predictions}


class CampaignBarrier:
    """No score release before all independently planned episodes freeze/finish.

    Protects this exact operator-admitted roster, not all possible future runs.
    No resume tokens, autonomous reruns, selection by test outcome, or new budget
    authority. This in-memory trusted owner is never mounted into a participant.
    """
    def __init__(self,roster):
        need(type(roster)is dict and len(roster)>=2 and set(roster.values())=={'A','B'} and
             all(type(k)is str and a.HEX.fullmatch(k) for k in roster),'fixed roster includes both access conditions')
        self.roster=deepcopy(roster);self.roster_identity=r.identity(roster)
        self.episodes={};self.sealed=None

    def register(self,episode):
        need(type(episode)is Episode and self.sealed is None and episode.state=='development' and episode.barrier is None,
             'fresh exact episode before development')
        need(self.roster.get(episode.id)==episode.info['role'] and episode.id not in self.episodes,
             'no extra, duplicate or replacement episode')
        self.episodes[episode.id]=episode;episode.barrier=self
        self._check(require_all=False)

    def _check(self,require_all=True):
        need(r.identity(self.roster)==self.roster_identity,'planned campaign roster cannot change')
        if require_all:need(set(self.episodes)==set(self.roster),'all planned episodes required')
        anchor=None
        for eid,episode in self.episodes.items():
            need(type(episode)is Episode and episode.id==eid and self.roster.get(eid)==episode.info['role'] and
                 episode.barrier is self,'same live registered episode, role and barrier')
            episode._unchanged()
            comparable=(episode.info['data_identity'],episode.development['view_identity'],episode.test['view_identity'],
                        episode.profile,a.canonical(episode.development_resources),a.canonical(episode.inference_resources))
            if anchor is None:anchor=comparable
            need(comparable==anchor,'equal complete paired data, scientific profile and phase resource caps')
            if self.sealed is not None:
                identity=self.sealed[eid]
                need(episode is identity['episode'] and episode.artifact==identity['artifact'] and
                     episode.freeze_time==identity['frozen_at'] and episode.provider is identity['provider'] and
                     episode.image==identity['image'],'all original frozen artifacts/owners must remain exact')

    def ready_for_development(self,episode):
        self._check();need(self.sealed is None and self.episodes.get(episode.id)is episode,'no development after campaign freeze')

    def seal(self):
        self._check();need(self.sealed is None and all(e.state=='frozen' for e in self.episodes.values()),
                           'every declared method must freeze before any test exposure')
        providers=[e.provider for e in self.episodes.values()]
        need(len({id(p) for p in providers})==len(providers),'one original Provider per episode')
        roots=[Path(root) for p in providers for root in (p.control_root,p.quarantine_root)]
        need(all(root.is_absolute() and '..' not in root.parts for root in roots) and
             all(not left.is_relative_to(right) and not right.is_relative_to(left)
                 for index,left in enumerate(roots) for right in roots[index+1:]),
             'non-nested disjoint private capture/control roots across campaign')
        need(len({e.image for e in self.episodes.values()})==1,'same actual immutable image across paired conditions')
        self.sealed={eid:{'episode':e,'artifact':deepcopy(e.artifact),'frozen_at':e.freeze_time,
                          'provider':e.provider,'image':e.image} for eid,e in self.episodes.items()}
        return {'episodes_frozen':len(self.sealed),'roster_identity':self.roster_identity,'scores_released':False}

    def ready_for_inference(self,episode):
        need(self.sealed is not None,'entire declared roster freezes before test')
        self._check();need(self.episodes.get(episode.id)is episode,'exact registered inference episode')
        need(all(e.state in ('frozen','complete') for e in self.episodes.values()),'no failed or reopened episode')

    def release(self):
        need(self.sealed is not None,'no feedback before all declared methods freeze')
        self._check();need(all(e.state=='complete' for e in self.episodes.values()),'no partial campaign scoring feedback')
        return {'complete_episodes':len(self.episodes),'roster_identity':self.roster_identity}


def feasibility(frozen_artifact_bytes,predictor_panels=1):
    need(type(frozen_artifact_bytes)is int and frozen_artifact_bytes>0 and
         type(predictor_panels)is int and predictor_panels>0,'explicit complete artifact and panel count')
    signal_bytes=1803*64*800*8
    return {'test_phases':predictor_panels,'complete_epochs_per_phase':1803,
            'containers_created_and_retired':2*predictor_panels,'volumes_created_and_retired':predictor_panels,
            'minimum_Docker_CLI_calls':40*predictor_panels,'minimum_archive_GETs':2*predictor_panels,
            'artifact_hash_read_bytes':2*predictor_panels*frozen_artifact_bytes,
            'reference_raw_classifier_load_bytes':predictor_panels*279390224,
            'test_signal_payload_bytes':predictor_panels*signal_bytes,
            'signal_and_artifact_hash_read_bytes':2*predictor_panels*(signal_bytes+frozen_artifact_bytes),
            'reference_batches_per_phase':57,'reference_batch_size':32,
            'original_global_deadline_required':True,'measured_runtime_seconds':None,
            'extra_costs':'development/promotion, NPY headers, metadata, retries, geometry, source hashes, kernel/library I/O and closure excluded',
            'GPU_provider_qualified':False,'scientific_budget_adopted':False}
