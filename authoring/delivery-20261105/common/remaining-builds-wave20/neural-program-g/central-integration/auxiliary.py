"""Full source-defined auxiliary exposure and investigation transcript joins."""
from collections import OrderedDict
from pathlib import Path
import re
from .core import need, encode, decode, pin, capture, read_json
from _sleep_parent.common import VIEWS
from _sleep_parent.investigator import ACTION_SCHEMA
from _sleep_parent.scorer import admit_presentation_view


def file_identity(name,descriptor,purpose='input'):
    return {'kind':'file','purpose':purpose,'files':{name:descriptor}}


def stage_pair(view_raw,binding_raw,meter):
    """Schema-derived complete-view size bound; no arbitrary epoch truncation."""
    view=decode(view_raw,meter.depth,meter.nodes); binding=decode(binding_raw,meter.depth,meter.nodes)
    need(set(view)=={'schema','view','role','current_person','class_order','nights'}
         and view['schema']=='neural007_public_view_v1' and view['view'] in VIEWS
         and view['role'] in ('probe','fit52','fit65','infer','validation')
         and view['class_order']==['W','N1','N2','N3','R'], 'Exact finite public view schema')
    need(view['current_person'] is None or type(view['current_person']) is str
         and re.fullmatch('[0-9a-f]{32}',view['current_person']), 'Opaque current handle domain')
    need(type(view['nights']) is list and 1<=len(view['nights'])<=153, 'Complete view lies within original153 nights')
    for n in view['nights']:
        need(set(n)=={'person','night','epochs','channels','directory','target_role','split_role'}
             and re.fullmatch('[0-9a-f]{32}',n['person']) and n['night'] in ('night-1','night-2')
             and n['directory']=='nights/'+n['person']+'/'+n['night']
             and type(n['epochs']) is int and 2<=n['epochs']<=2**63-1
             and n['channels']==list(VIEWS[view['view']])
             and n['target_role'] in ('training','unlabeled')
             and n['split_role'] in ('fit52','validation13','current_query'), 'Bounded exact night metadata fields')
    need(set(binding)=={'schema','public_view','sources','presentation'}
         and binding['schema']=='neural007_private_view_binding_v1'
         and binding['public_view']==pin(view_raw) and type(binding['sources']) is list
         and len(binding['sources'])==len(view['nights']), 'Exact complete private stage binding')
    for b in binding['sources']:
        need(set(b)=={'directory','subject','night','epochs'}
             and type(b['subject']) is int and 0<=b['subject']<=2**63-1
             and type(b['night']) is int and b['night'] in (1,2)
             and type(b['epochs']) is int and 2<=b['epochs']<=2**63-1
             and re.fullmatch('nights/[0-9a-f]{32}/night-[12]',b['directory']), 'Typed bounded biological binding metadata')
    presentation=binding['presentation']
    need(presentation is None or type(presentation) is dict and set(presentation)=={'bytes','sha256'}
         and type(presentation['bytes']) is int and 0<presentation['bytes']<=2**63-1
         and re.fullmatch('[0-9a-f]{64}',presentation['sha256']), 'Exact presentation descriptor')
    need(encode(view)==view_raw and encode(binding)==binding_raw, 'Parent source publishes canonical stage JSON')
    need(len(view_raw)<=2048+153*1024 and len(binding_raw)<=2048+153*512,
         'Source-schema complete stage extents used by prospective cache bound')
    return view,binding


class Views:
    """Complete bounded encoded-byte index; at most two parsed view pairs retained."""
    def __init__(self,root,tree,meter,cache_bytes):
        self.root,self.meter=root,meter; self.index={}; self.cache=OrderedDict(); self.used=set(); self.cached_bytes=0; self.cache_bytes=cache_bytes
        names={n.split('/')[1] for n in tree if n.startswith('stages/')}
        for name in sorted(names):
            need(re.fullmatch('[0-9a-f]{32}',name),'Only opaque stage directories')
            prefix='stages/'+name+'/'
            need({n[len(prefix):] for n in tree if n.startswith(prefix)}=={'VIEW.json','BINDING.json'},'Complete exact stage metadata pair')
            vp=root/prefix/'VIEW.json'; bp=root/prefix/'BINDING.json'
            vr=capture(vp,meter=meter); br=capture(bp,meter=meter)
            vpin,bpin=pin(vr),pin(br); _,binding=stage_pair(vr,br,meter)
            need(binding['public_view']==vpin,'Every stage binds exact public view')
            key=(vpin['bytes'],vpin['sha256'])
            if key in self.index:
                need(self.index[key]['binding']==bpin,'No ambiguous private identity for equal public view')
            else:
                self.cached_bytes+=len(vr)+len(br)
                need(self.cached_bytes<=self.cache_bytes,'Complete preselected encoded view-cache allocation')
                self.index[key]={'view':vpin,'binding':bpin,'view_path':str(vp),'binding_path':str(bp),
                    'view_body':vr,'binding_body':br}
        self.stage_count=len(names)

    def get(self,descriptor):
        key=(descriptor['bytes'],descriptor['sha256']); need(key in self.index,'Every mounted view belongs to complete stage census')
        self.used.add(key)
        record=self.index[key]
        cache_key=(record['view_path'],*key,record['binding_path'],record['binding']['bytes'],record['binding']['sha256'])
        if cache_key not in self.cache:
            need(pin(record['view_body'])==record['view'] and pin(record['binding_body'])==record['binding'], 'Exact immutable cached-byte identity')
            view=decode(record['view_body'],self.meter.depth,self.meter.nodes)
            binding=decode(record['binding_body'],self.meter.depth,self.meter.nodes)
            self.cache[cache_key]=(view,binding)
            if len(self.cache)>2:self.cache.popitem(last=False)
        self.cache.move_to_end(cache_key)
        return self.cache[cache_key]


def expected_members(spec,folds,prepared):
    source=spec['spec']; action=spec['action']
    if action=='reference_cache':
        person=source['subject']; fold=next(f for f in folds if person in f['query_people'])
        return fold,'EOC','infer',person,{(person,source['night'])},set()
    fold=folds[source['fold']-1]; view=source['view']
    person=source.get('subject',fold['query_people'][0])
    if action in ('policy','probe'):role='probe'
    elif action=='fit':role='fit65'
    elif action=='infer':role='infer'
    elif source['kind']=='reference_fit':role=source['role']
    elif source['kind']=='reference_validation':role='validation'
    else:role='infer'
    if role=='fit65':people=set(fold['final_training_people']); labelled=people
    elif role=='fit52':people=set(fold['fit_people']);labelled=people
    elif role=='validation':people=set(fold['validation_people']);labelled=set()
    elif role=='probe':people=set(fold['final_training_people'])|{person};labelled=set(fold['final_training_people'])
    else:people={person};labelled=set()
    return fold,view,role,person,{k for k in prepared if k[0] in people},labelled


def view_inputs(spec,view,binding,vp,prepared,folds,presentations,cache_files,graded_records,shifted_mounts=None):
    fold,view_name,role,person,members,labelled=expected_members(spec,folds,prepared)
    need(view['schema']=='neural007_public_view_v1' and set(view)=={'schema','view','role','current_person','class_order','nights'}
         and view['view']==view_name and view['role']==role and view['class_order']==['W','N1','N2','N3','R'], 'Frozen phase view/type/class semantics')
    need(len(binding['sources'])==len(view['nights'])==len(members)
         and {(x['subject'],x['night']) for x in binding['sources']}==members, 'All and only source-defined auxiliary biological support')
    by_dir={x['directory']:x for x in binding['sources']}; need(len(by_dir)==len(members),'Unique private view directory membership')
    reference=spec['role']=='reference'
    admit_presentation_view(view,binding,presentations[str(fold['fold'])],reference)
    expected={'/view/VIEW.json':file_identity('VIEW.json',vp,'contract')}
    identities={}; held_handles=set()
    for night in view['nights']:
        b=by_dir[night['directory']]; key=(b['subject'],b['night']); original=prepared[key]
        need(type(b['subject']) is int and type(b['night']) is int and type(b['epochs']) is int
             and b['epochs']==night['epochs']==original['epochs'] and night['channels']==list(VIEWS[view_name]), 'Whole source clock/channel geometry')
        need(type(night['person']) is str and re.fullmatch('[0-9a-f]{32}',night['person'])
             and night['night']=='night-'+str(b['night'])
             and night['directory']=='nights/'+night['person']+'/'+night['night'], 'Exact opaque person and within-person night path')
        if b['subject'] in identities:need(identities[b['subject']]==night['person'],'Both nights grouped under same handle')
        identities[b['subject']]=night['person']
        split='fit52' if b['subject'] in fold['fit_people'] else ('validation13' if b['subject'] in fold['validation_people'] else 'current_query')
        need(night['split_role']==split and night['target_role']==('training' if b['subject'] in labelled else 'unlabeled'), 'No target-role or split substitution')
        if b['subject']==person:held_handles.add(night['person'])
        arrays={'clock.npy':original['clock'],**{f'channel-{c}.npy':original['channels'][str(c)] for c in VIEWS[view_name]}}
        if b['subject'] in labelled:arrays.update({'stages.npy':original['stages'],'mask.npy':original['mask']})
        for name,a in arrays.items():
            target='/view/'+night['directory']+'/'+name
            if spec['action']=='infer' and spec['spec'].get('control')=='shifted' and name.startswith(('channel-0','channel-1')):
                # The unchanged metadata panel already admitted the exact
                # transformed source/offset/current-person lineage for this row.
                need(spec['logical'] in graded_records,'Shift must have full protected-metadata provenance')
                expected[target]=shifted_mounts[target]
            else:expected[target]=file_identity(Path(a['path']).name,{k:a[k] for k in ('bytes','sha256')})
        if reference and spec['action']!='reference_cache':
            cached=cache_files[key]
            for name in [f'context-{c}.npy' for c in VIEWS[view_name]]+['context-clock.npy']:
                expected['/cache/'+night['directory']+'/'+name]=file_identity(name,cached[name],'operator_reference')
    need(len(set(identities.values()))==len(identities),'No aliased source people')
    if role in ('probe','infer'):need(len(held_handles)==1 and view['current_person']==next(iter(held_handles)),'Only exact current held person')
    else:need(view['current_person'] is None,'No query handle in training/validation view')
    return expected,fold,view_name


def exposure(spec,result,views,prepared,folds,presentations,source_bodies,cache_files,reference_models,
             seals,contexts,configuration,graded_records):
    receipt=result['receipt']; job=result['job']; actual=receipt['input_before']
    view_mount=actual['/view/VIEW.json']; need(view_mount['kind']=='file' and view_mount['purpose']=='contract'
        and set(view_mount['files'])=={'VIEW.json'},'Exact public view mount')
    vp=view_mount['files']['VIEW.json']; view,binding=views.get(vp)
    expected,fold,view_name=view_inputs(spec,view,binding,vp,prepared,folds,presentations,cache_files,graded_records,actual)
    expected['/job.json']=file_identity('JOB.json',result['join']['job'],'contract')
    reference=spec['role']=='reference'
    names=['__init__.py','common.py','worker.py','entry.py']+(['science.py','references.py'] if reference else [])
    for name in names:
        expected['/library/program/'+name]=file_identity(name,pin(source_bodies['program/'+name]),'operator_reference' if reference else 'program')
    action=spec['action']; source=spec['spec']; base={'schema':'neural007_worker_job_v1','action':action}
    if action=='reference_cache':need(job==base,'Exact deterministic cache JOB')
    elif reference:
        family=source['family']; need(job['family']==family and job['cache'] is True,'Frozen reference family and cache route')
        if action=='reference_fit':
            need(set(job)==set(base)|{'family','cache','parameter','association_control'},'Exact reference fit JOB fields')
            need(job['association_control']==source.get('association_control',False),'Source-selected reference association control')
            if 'selection' in source:
                need(job['parameter'] in ((1,10,100) if family=='R0' else (1,5)),'Frozen validation grid parameter domain')
            else:need(job['parameter']==source.get('parameter'),'Fixed reference fit parameter')
        else:
            need(set(job)==set(base)|{'family','cache','shifted','power','alpha'} and job['shifted']==(source.get('control')=='shifted')
                 and job['alpha']==source.get('alpha'),'Exact validation/inference control JOB')
            if family!='R2':need(job['power'] is None,'No undeclared sequence power')
            elif 'power' in source:need(job['power']==source['power'],'Exact frozen validation grid power')
            else:need(job['power'] in (0,.5,1),'Selected frozen-grid sequence power')
            expected['/model/MODEL.pkl']=file_identity('MODEL.pkl',reference_models[source['model']]['model'],'operator_reference')
            need(reference_models[source['model']]['timing']['finished']<receipt['timing']['started'],
                 'Actual reference state captured before every validation/inference use')
    elif action in ('policy','probe'):
        wire=spec['wire_context']; seal=seals[wire]
        need(result['join']['clock']==seal['clock'],'Exact original investigation enclosure, not refreshed tool clock')
        if action=='policy':
            need(job=={**base,'history':True},'Exact frozen-policy history JOB')
            expected['/candidate/main.py']=file_identity('policy.py',configuration['fixed_submission']['policy']['source'],'program')
            expected['/history']=file_identity(f"prompt-{spec['turn']}.json",spec['prompt_pin'],'contract')
        else:
            need(job==base,'Exact probe JOB')
            expected['/candidate/main.py']=file_identity(f"probe-{spec['probe']}.py",spec['probe_source'],'program')
    elif action=='fit':
        need(job=={**base,'recipe':True},'Exact candidate fit JOB')
        logical=source['id']; wire=contexts.get(logical)
        bundle=seals[wire]['bundle'] if wire in seals else configuration['fixed_submission']['bundle_members']
        expected['/candidate/main.py']=file_identity('fit.py',{k:bundle['fit_source'][k] for k in ('bytes','sha256')},'program')
        expected['/recipe']=file_identity('RECIPE.json',{k:bundle['recipe'][k] for k in ('bytes','sha256')},'contract')
    else:
        need(action=='infer' and job=={**base,'recipe':True,'model':True} and spec['logical'] in graded_records, 'Exact candidate inference JOB and complete panel lineage')
        wire=contexts[source['id']]
        bundle=seals[wire]['bundle'] if wire in seals else configuration['fixed_submission']['bundle_members']
        expected['/candidate/main.py']=file_identity('infer.py',{k:bundle['inference_source'][k] for k in ('bytes','sha256')},'program')
        expected['/recipe']=file_identity('RECIPE.json',{k:bundle['recipe'][k] for k in ('bytes','sha256')},'contract')
        # Actual model content was independently joined to the sealed fit by
        # metadata-panel primitives; code/recipe additionally join finalization.
        expected['/model']=actual['/model']
    need(actual==expected,'Exact complete source-defined mount set; no extra target, other-context or arbitrary file')
    return {'view':vp,'source_members':len(binding['sources']),'reference_numeric_selection_verified':False}


def transcripts(root,seals,context_map,schedule,phase_evidence,views,prepared,folds,presentations,configuration,meter):
    """Reconstruct each permitted conversation from its exact captured producers."""
    logical_by_wire={v:k for k,v in context_map.items()}
    context_specs={c['id']:c for c in schedule['candidate_contexts']}
    for wire,seal in sorted(seals.items()):
        current=root/'investigations'/wire; context=context_specs[logical_by_wire[wire]]
        first=read_json(current/'prompt-1.json',meter)
        need(type(first) is list and len(first)==2,'Initial prompt has exactly one system and current-task message')
        public=first[1]['content']['view']; vp=pin(encode(public)); stored,binding=views.get(vp)
        need(public==stored,'Provider/policy prompt view equals captured staged view')
        spec={'logical':context['id'],'action':'probe','role':'A' if seal['mode']=='frozen_program' else 'B','spec':context}
        view_inputs(spec,stored,binding,vp,prepared,folds,presentations,{}, {})
        conversation=[{'role':'system','content':configuration['investigator_system_prompt']},
            {'role':'user','content':{'task':'Predict every full-clock30s epoch in every current-person night. Five classes W,N1,N2,N3,R.',
                'view':public,'tool':'python_probe','max_probes':6,'max_decisions':8,
                'final_output':'training-only fit source, immutable-model inference source, recipe, executable supported claims'}}]
        need(first==conversation,'Exact current-context prompt without hidden labels, other context or reference output')
        probes=0
        for decision in seal['decisions']:
            turn=decision['turn']; prompt=encode(conversation)
            need(len(prompt)<=8388608,'Complete unchanged transcript extent')
            if turn==1:
                actual_prompt=first
            else:
                actual_prompt=read_json(current/f'prompt-{turn}.json',meter)
            need(actual_prompt==conversation,'Every conversation step joins only admitted previous actions/tools')
            action=read_json(current/f'action-{turn}.json',meter,decision['action'])
            if seal['mode']=='frozen_program':
                evidence=phase_evidence[wire+f'-policy-{turn}']
                raw=capture(Path(evidence['output_root'])/'artifacts/ACTION.json',
                    evidence['files']['artifacts/ACTION.json'],meter,1048576)
                need(decode(raw,meter.depth,meter.nodes)==action and evidence['receipt_pin']==decision['receipt']['native'],
                     'Canonical policy action equals actual captured ACTION producer')
                need(evidence['clock']==seal['clock'] and evidence['history_pin']==pin(prompt),
                     'Exact policy history and original context clock')
            else:
                request=read_json(root/'provider'/wire/'requests'/f'turn-{turn}.json',meter,decision['receipt']['request'])
                response=read_json(root/'provider'/wire/f'response-{turn}.json',meter,decision['receipt']['response'])
                need(request['prompt']==prompt.decode('utf-8') and request['format']==ACTION_SCHEMA and response['action']==action
                     and request['context']==response['context']==wire and request['turn']==response['turn']==turn,
                     'Actual provider prompt/action/current-context lineage')
            conversation.append({'role':'assistant','content':action})
            if action['action']=='python_probe':
                probes+=1; evidence=phase_evidence[wire+f'-probe-{probes}']
                source_pin=pin(action['source'].encode('utf-8'))
                capture(current/f'probe-{probes}.py',source_pin,meter,1048576)
                need(evidence['probe_source']==source_pin and evidence['clock']==seal['clock'], 'Only exact current action source in original probe enclosure')
                need(evidence['files']['artifacts/OBSERVATION.json']['bytes']<=65536,'Original typed observation ceiling')
                observation=read_json(Path(evidence['output_root'])/'artifacts/OBSERVATION.json',meter,
                    evidence['files']['artifacts/OBSERVATION.json'])
                conversation.append({'role':'tool','content':{'probe':probes,'observation':observation,
                    'source':source_pin,'receipt':evidence['receipt_pin']}})
            else:
                need(action['action']=='finalize' and turn==len(seal['decisions']),'Final action terminates exact context')
                for key,name in [('fit_source','fit.py'),('inference_source','infer.py')]:
                    source_pin=pin(action[key].encode('utf-8')); bound=seal['bundle'][key]
                    need(bound=={'path':str(current/name),**source_pin},'Exact final generated source seal')
                    capture(current/name,source_pin,meter,1048576)
                recipe_pin=pin(encode(action['recipe']))
                need(seal['bundle']['recipe']=={'path':str(current/'RECIPE.json'),**recipe_pin},'Exact generated recipe seal')
                capture(current/'RECIPE.json',recipe_pin,meter,1048576)
        need(probes==seal['probes'],'Complete actual transcript probe sequence')
    need(views.used==set(views.index),'No unaccounted extra staged view or hidden data role')
    return {'contexts':len(seals),'transcripts_and_actions_joined':True,'numerical_claim_content_recomputed':False}
