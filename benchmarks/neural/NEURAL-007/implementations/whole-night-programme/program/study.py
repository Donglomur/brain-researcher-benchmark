"""Complete source-defined campaign orchestration. Explicit future grant only.

This coordinator owns scope, histories, role mounts, choices and original clocks.
It has no numerical default/smaller-cohort fallback, retry or ambient provider.
"""
from pathlib import Path
import time
import uuid
from .common import capture, decode, encoded, need, pin, publish, Meter, MODES, VIEWS
from .packet import roster, admit_index, view_plan
from .schedule import graph
from .transport import Native, source_mounts, stage_view, file_mount
from .model_transport import Session
from .investigator import investigate, captured
from .execution import handles, captured_tree, shift_plan, admit_generated_state, predictions
from .scorer import array_rows
from .science import confusion, combine_confusions, person_macro
from .references import choose, GRID
from . import presentation


def admit_fixed_submission(fixed, profile, origin, meter):
    """Actual executing files must be members of the pre-data source seal."""
    commit=decode(capture(fixed['commit_path'],fixed['commit_pin'],meter=meter))
    manifest_raw=capture(fixed['bundle_path'],fixed['bundle'],meter=meter); manifest=decode(manifest_raw)
    need(manifest['schema']=='neural007_frozen_submission_v1' and manifest['profile']==profile, 'Exact fixed submission format/profile')
    need(commit['source']==pin(manifest_raw) and commit['profile']==profile and type(commit['sealed_at']) in (int,float)
         and commit['sealed_at']<origin and commit['numeric_exposure_before_seal'] is False,'Independent pre-data commitment')
    if profile=='generic_current_person':
        operands={'policy.py':{'path':fixed['policy']['path'],**fixed['policy']['source']}}
    else:
        operands={name:fixed['bundle_members'][key] for name,key in [('fit.py','fit_source'),('infer.py','inference_source'),('RECIPE.json','recipe')]}
    need(manifest['files']=={n:{k:a[k] for k in ('bytes','sha256')} for n,a in operands.items()},'Exact committed executing membership; no substituted policy/code/recipe')
    need(sum(a['bytes'] for a in operands.values())<=1048576,'Whole committed source bundle ceiling')
    for name,a in operands.items():
        body=capture(a['path'],{k:a[k] for k in ('bytes','sha256')},1048576,meter)
        if name.endswith('.py'):compile(body.decode('utf-8'),'<committed-'+name+'>','exec')
        else:decode(body)
    return {'bundle':pin(manifest_raw),'commit':fixed['commit_pin'],'authoring_cost':commit.get('authoring_cost')}


class Campaign:
    def __init__(self, configuration, grant, source_root, source_manifest, roster_body, folds_body, index_body):
        self.c=configuration;self.grant=grant;self.source_root=Path(source_root);self.source_manifest=source_manifest
        need(grant['schema']=='neural007_full153_campaign_grant_v1' and grant['authorized'] is True,'Separate explicit authentic campaign authority')
        need(grant['source']==pin(encoded(source_manifest)) and grant['roster']==pin(roster_body)
             and grant['folds']==pin(folds_body) and grant['index']==pin(index_body),'Immutable complete source/input/clock grant')
        need(grant['roster']==source_manifest['design']['ROSTER.json'] and grant['folds']==source_manifest['design']['FOLDS.json'], 'Only frozen original153-night cohort')
        need(grant['configuration']==pin(encoded(configuration)),'Exact pre-query campaign configuration')
        pools=grant['tracked_io_envelopes']
        expected_pools={'controller_read_bytes':grant['read_bytes'],'controller_write_bytes':grant['write_bytes'],
            'native_read_bytes':configuration['native']['source_read_bytes'],'native_write_bytes':configuration['native']['host_write_bytes'],
            'model_contexts':312,'model_context_read_bytes':configuration['model']['read_bytes'],'model_context_write_bytes':configuration['model']['write_bytes']}
        need(pools==expected_pools and all(type(v) is int and v>0 for v in pools.values()), 'Complete disjoint precommitted controller/native/312-provider I/O pools')
        need(grant['tracked_read_ceiling']==pools['controller_read_bytes']+pools['native_read_bytes']+312*pools['model_context_read_bytes']
             and grant['tracked_write_ceiling']==pools['controller_write_bytes']+pools['native_write_bytes']+312*pools['model_context_write_bytes'], 'Explicit whole-workload tracked I/O envelope sum')
        need(configuration['native']['source']==grant['source'] and configuration['model']['source']==grant['source'],'Same exact campaign source across transports')
        self.provider_costs=[]
        self.clock=grant['clock'];self.meter=Meter(grant['read_bytes'],grant['write_bytes'],self.clock['origin'],self.clock['deadline'])
        self.root=Path(configuration['root']);need(self.root.is_absolute() and not self.root.exists(),'Fresh isolated campaign, no automatic retry')
        self.fixed=configuration['fixed_submission']
        self.fixed_admission=admit_fixed_submission(self.fixed,configuration['frozen_profile'],self.clock['origin'],self.meter)
        self.rows,self.folds=roster(roster_body,folds_body)
        self.presentations={f['fold']:presentation.create(f,self.rows) for f in self.folds}
        self.graph=graph(self.folds,self.rows,configuration['frozen_profile'])
        self.root.mkdir(mode=0o700)
        for name in ('stages','records','shifts','investigations','models','provider','cache','fixed'):(self.root/name).mkdir(mode=0o700)
        self.presentation_pin=publish(self.root/'PRIVATE_PRESENTATIONS.json',encoded(self.presentations),self.meter)
        self.stage_fixed_submission()
        self.prepared=admit_index(decode(index_body),self.rows,pin(roster_body),True,self.meter)
        self.native=Native(configuration['native'],self.meter)
        self.references={};self.caches={};self.validation={};self.outputs=[];self.receipts={};self.shared={};self.sequence=[];self.receipt_logical={};self.context_wire={}
        self.source=grant['source']
        publish(self.root/'GRAPH.json',encoded(self.graph),self.meter)

    def stage_fixed_submission(self):
        # Source locations supplied by the author never become bind-source names.
        # Authenticate/copy the <=1MiB committed bundle into a neutral namespace.
        root=self.root/'fixed'/uuid.uuid4().hex;root.mkdir(mode=0o700)
        fixed=dict(self.fixed)
        if self.c['frozen_profile']=='generic_current_person':
            a=fixed['policy'];body=capture(a['path'],a['source'],1048576,self.meter)
            target=root/'policy.py';publish(target,body,self.meter);fixed['policy']={'path':str(target),'source':a['source']}
        else:
            members={}
            for key,name in [('fit_source','fit.py'),('inference_source','infer.py'),('recipe','RECIPE.json')]:
                a=fixed['bundle_members'][key];expected={k:a[k] for k in ('bytes','sha256')}
                body=capture(a['path'],expected,1048576,self.meter);target=root/name;publish(target,body,self.meter)
                members[key]={'path':str(target),**expected}
            fixed['bundle_members']=members
        self.fixed=fixed

    def candidate_handles(self,fold,person):
        return presentation.handles(self.presentations[fold['fold']],fold,person)

    def candidate_plan(self,fold,person,view,role,binding):
        plan=view_plan(self.prepared,fold,person,view,role,binding)
        return presentation.apply(plan,self.presentations[fold['fold']])

    def phase_clock(self,seconds):
        now=self.meter.tick();need(now+seconds<=self.clock['deadline'],'Whole next phase reserved inside original campaign clock')
        return {'origin':now,'deadline':now+seconds,'campaign_origin':self.clock['origin'],'campaign_deadline':self.clock['deadline']}

    def limits(self,action):
        value=dict(self.c['phase_limits'][action]);need(value['producer_seconds']=={'probe':300,'policy':180,'fit':7200,'infer':1800,'reference_fit':7200,'reference_infer':1800,'reference_cache':300}[action],'Accepted operation ceiling')
        need(value['memory_bytes']==16*1024**3 and value['cpu_nanos']==4_000_000_000,'Matched numerical process envelope')
        return value

    def run(self,identity,action,role,job,mounts,clock):
        result=self.native.run(identity,action,role,job,mounts,clock,self.limits(action))
        rp=result['receipt_pin']; self.receipts[rp['sha256']]=result['receipt_path'];self.receipt_logical[rp['sha256']]=identity
        publish(self.root/'records'/(identity+'.json'),encoded(result),self.meter)
        self.sequence.append({'id':identity,'action':action,'receipt':rp,'finished':time.monotonic()})
        return result

    def staged(self,identity,plan,reference=False,cache=False):
        mounts,public,view_pin=stage_view(plan,self.root/'stages'/uuid.uuid4().hex,self.meter)
        mounts.update(source_mounts(self.source_root,self.source_manifest,reference))
        if cache:
            # Join by this operator-only view plan, never caller-selected cache.
            reverse={n['directory']:n for n in public['nights']}
            for item in plan['members']:
                if not item['target'].endswith('/clock.npy'):continue
                directory=str(Path(item['target']).parent)
                matches=[key for key,row in self.prepared.items() if row['clock']==item['artifact']]
                need(len(matches)==1,'Exact original-night cache identity')
                cached=self.caches[matches[0]]
                for channel in VIEWS[public['view']]:
                    name=f'context-{channel}.npy';a=cached[name]
                    mounts['/cache/'+directory+'/'+name]=file_mount(a['path'],{k:a[k] for k in ('bytes','sha256')},'operator_reference')
                a=cached['context-clock.npy'];mounts['/cache/'+directory+'/context-clock.npy']=file_mount(a['path'],{k:a[k] for k in ('bytes','sha256')},'operator_reference')
        return mounts,public,view_pin

    def construct_caches(self):
        for spec in self.graph['reference_caches']:
            f=next(x for x in self.folds if spec['subject'] in x['query_people']);binding=handles(f,spec['subject'])
            plan=view_plan(self.prepared,f,spec['subject'],'EOC','infer',binding)
            directories={n['directory'] for n in plan['nights'] if n['night']=='night-'+str(spec['night'])}
            plan={**plan,'nights':[n for n in plan['nights'] if n['directory'] in directories],
                  'members':[m for m in plan['members'] if str(Path(m['target']).parent) in directories]}
            mounts,_,_=self.staged(spec['id'],plan,True)
            result=self.run(spec['id'],'reference_cache','reference',{},mounts,self.phase_clock(660))
            receipt=result['receipt'];files=receipt['output_inventory']['files'];root=Path(receipt['quarantine_root'])
            expected={'context-0.npy','context-1.npy','context-2.npy','context-clock.npy'}
            need({n.removeprefix('cache/') for n in files if n.startswith('cache/')}==expected,'Complete deterministic per-channel cache')
            self.caches[(spec['subject'],spec['night'])]={n:{'path':str(root/'cache'/n),**files['cache/'+n]} for n in expected}
            for a in self.caches[(spec['subject'],spec['night'])].values():Path(a['path']).chmod(0o444)

    def selection(self,key,family):
        values=self.validation[key];count=3 if family=='R0' else 6
        need(set(values)==set(range(count)),'Complete selection grid, no outer outcomes')
        return choose([values[i] for i in range(count)],family)

    def validation_score(self,result,public,fold,binding):
        output=decode(captured(result,'PREDICTIONS.json',self.meter));wanted={(n['person'],n['night']):n for n in public['nights']}
        need(output['schema']=='neural007_predictions_v1' and len(output['nights'])==len(wanted),'Complete validation prediction panel')
        reverse={v:int(k) for k,v in binding.items()};person={s:[] for s in fold['validation_people']};seen=set()
        files=result['receipt']['output_inventory']['files'];root=Path(result['receipt']['quarantine_root'])
        for item in output['nights']:
            key=(item['person'],item['night']);need(key in wanted and key not in seen,'Complete unique validation night');seen.add(key)
            subject=reverse[item['person']];need(subject in person,'Validation only, never outer query')
            night=int(item['night'].removeprefix('night-'));target=self.prepared[(subject,night)];e=target['epochs']
            need(item['epochs']==e and item['path'] in files,'Exact all-clock captured validation output')
            a={'path':str(root/item['path']),**files[item['path']]};p=list(array_rows(a,e,5,'<f8',self.meter))
            y=list(array_rows(target['stages'],e,0,'|i1',self.meter));m=list(array_rows(target['mask'],e,0,'|b1',self.meter))
            need(m==[v>=0 for v in y],'Training validation mask equality');person[subject].append(confusion(p,y))
        need(seen==set(wanted),'All validation nights')
        return person_macro({s:combine_confusions(v) for s,v in person.items()},13)['primary']

    def construct_references(self):
        for spec in self.graph['references']:
            fold=self.folds[spec['fold']-1];person=spec.get('subject',fold['query_people'][0]);binding=handles(fold,person)
            role=spec.get('role','validation' if spec['kind']=='reference_validation' else 'infer')
            plan=view_plan(self.prepared,fold,person,spec['view'],role,binding)
            mounts,public,_=self.staged(spec['id'],plan,True,True)
            job={'family':spec['family'],'cache':True};recipe=None
            if spec['kind']=='reference_fit':
                parameter=spec.get('parameter');power=None
                if 'selection' in spec:
                    choice=self.selection(spec['selection'],spec['family'])
                    if spec['family']=='R0':parameter=choice
                    else:parameter,power=choice
                job.update(parameter=parameter,association_control=spec.get('association_control',False))
                result=self.run(spec['id'],'reference_fit','reference',job,mounts,self.phase_clock(7560))
                files=result['receipt']['output_inventory']['files'];root=Path(result['receipt']['quarantine_root'])
                need('MODEL.pkl' in files,'Captured independent reference state');(root/'MODEL.pkl').chmod(0o444)
                model={'path':str(root/'MODEL.pkl'),'pin':files['MODEL.pkl']}
                recipe={'family':spec['family'],'view':spec['view'],'parameter':parameter,'power':power,'association_control':job['association_control']}
                self.references[spec['id']]={'model':model,'recipe':recipe,'fit':result['receipt_pin']}
                continue
            state=self.references[spec['model']]
            mounts['/model/MODEL.pkl']=file_mount(state['model']['path'],state['model']['pin'],'operator_reference')
            job.update(shifted=spec.get('control')=='shifted',power=spec.get('power',state['recipe']['power']),alpha=spec.get('alpha'))
            result=self.run(spec['id'],'reference_infer','reference',job,mounts,self.phase_clock(2160))
            if spec['kind']=='reference_validation':
                key=f"f{spec['fold']}-R0" if spec['family']=='R0' else f"f{spec['fold']}-R2-{spec['view']}"
                index=(1,10,100).index(spec['alpha']) if spec['family']=='R0' else int(spec['id'].rsplit('-',1)[1])
                self.validation.setdefault(key,{})[index]=self.validation_score(result,public,fold,binding)
            else:
                nights=predictions(result,public,binding,person,self.meter,prefix='')
                self.outputs.append({'context':spec['id'],'mode':spec['family'],'profile':'independent_reference','fold':spec['fold'],
                    'subject':person,'view':spec['view'],'control':spec['control'],'source':self.source,'recipe':pin(encoded(state['recipe'])),
                    'model':state['model']['pin'],'fit':state['fit'],'inference':result['receipt_pin'],'nights':nights})

    def fit_bundle(self,identity,fold,person,view,binding,bundle,clock,mode=MODES[0]):
        plan=self.candidate_plan(fold,person,view,'fit65',binding);mounts,_,_=self.staged(identity,plan)
        for key,target in (('fit_source','/candidate/main.py'),('recipe','/recipe')):
            a=bundle[key];mounts[target]=file_mount(a['path'],{k:a[k] for k in ('bytes','sha256')},'program' if key=='fit_source' else 'contract')
        result=self.run(identity,'fit','A' if mode==MODES[0] else 'B',{'recipe':True},mounts,clock)
        model,model_pin=captured_tree(result,'artifacts/')
        return {'model_mount':model,'model':model_pin,'fit':result['receipt_pin'],'bundle':bundle}

    def construct_shared_fits(self):
        if self.graph['profile']!='training_only_reuse':return
        for spec in self.graph['shared_candidate_fits']:
            f=self.folds[spec['fold']-1];person=f['query_people'][0]
            # Globally fixed fit source may select with the supplied opaque52/13
            # roles internally, but never receives a held-person view.
            state=self.fit_bundle(spec['id'],f,person,spec['view'],self.candidate_handles(f,person),self.fixed['bundle_members'],self.phase_clock(7800))
            state['sealed_at']=time.monotonic();self.shared[(spec['fold'],spec['view'])]=state

    def provider_session(self,context,clock,root):
        c=self.c['model'];life=root/'LIFECYCLE.json';life_pin=publish(life,encoded({'context':context['id'],'deadline':clock['deadline']}),self.meter)
        names=('__init__.py','entry.py','common.py','provider_worker.py')
        mounts={'/library/program/'+n:file_mount(self.source_root/n,self.source_manifest['files'][n],'program') for n in names}
        profile=c['profile'];models=c['models']
        # Exact dynamic lifecycle identity is joined to a pre-query policy by a
        # host-authored admission record. Candidate/model cannot edit this root.
        from .vendor_transport.bounds import mount_identity
        all_mounts={**mounts,'/profile.json':file_mount(profile['path'],{k:profile[k] for k in ('bytes','sha256')},'contract'),
                    '/models':models,'/lifecycle.json':file_mount(life,life_pin,'contract')}
        policy=decode(capture(c['boundary_policy_path'],c['boundary_policy'],meter=self.meter))
        need(policy['image']==c['image'] and policy['source']==self.source and policy['profile']=={k:profile[k] for k in ('bytes','sha256')}
             and policy['models']=={k:v for k,v in models.items() if k!='path'},'Pre-query exact model/image/source admission')
        approval={'context':context['id'],'image':c['image'],'source':self.source,'immutable_mounts':mount_identity(all_mounts),
                  'mailbox_policy':'fresh_readonly_append_only_current_context','boundary_policy':c['boundary_policy']}
        ap=root/'PROVIDER_ADMISSION.json';ap_pin=publish(ap,encoded(approval),self.meter)
        return Session({**c,'admission_path':str(ap),'admission_pin':ap_pin},self.root/'provider'/context['id'],context['id'],clock,mounts,
                       all_mounts['/profile.json'],models,all_mounts['/lifecycle.json'])

    def construct_candidates(self):
        for context in self.graph['candidate_contexts']:
            f=self.folds[context['fold']-1];person=context['subject'];binding=self.candidate_handles(f,person);clock=self.phase_clock(context['enclosure_seconds'])
            wire_context={'id':uuid.uuid4().hex,'mode':context['mode']}
            self.context_wire[context['id']]=wire_context['id']
            publish(self.root/'records'/(context['id']+'-wire.json'),encoded({'logical_context':context['id'],'wire_context':wire_context['id'],'presentation':pin(encoded(self.presentations[context['fold']]))}),self.meter)
            croot=self.root/'models'/wire_context['id'];croot.mkdir(mode=0o700)
            if context['final_fit']!='fresh_current_context':
                state=self.shared[(context['fold'],context['view'])]
                need(state['sealed_at']<time.monotonic(),'Shared model sealed before any corresponding query staging')
            else:
                probe_plan=self.candidate_plan(f,person,context['view'],'probe',binding)
                probe_mounts,public,_=stage_view(probe_plan,self.root/'stages'/uuid.uuid4().hex,self.meter)
                policy={'source':self.source,'system_prompt':self.c['investigator_system_prompt'], 'phases':{}}
                for k,n in (('policy',8),('probe',6)):
                    for i in range(1,n+1):policy['phases'][f'{k}-{i}']={'limits':self.limits(k)}
                session=self.provider_session(wire_context,clock,croot) if context['mode']==MODES[1] else None
                seal,seal_pin=investigate(wire_context,self.native,session,policy,self.root/'investigations'/wire_context['id'],public,probe_mounts,
                    source_mounts(self.source_root,self.source_manifest),clock,self.meter,
                    frozen=self.fixed['policy'] if context['mode']==MODES[0] else None)
                if context['mode']==MODES[1]:self.provider_costs.append(seal['provider_closure'])
                admit_generated_state(seal,seal_pin,self.c['semantic_intake'],clock,7200+1800*len(context['inferences'])+420,self.meter)
                state=self.fit_bundle(context['id']+'-fit',f,person,context['view'],binding,seal['bundle'],clock,context['mode'])
            bundle=state['bundle']
            for control in context['inferences']:
                plan=self.candidate_plan(f,person,context['view'],'infer',binding)
                transform=None
                if control=='shifted':
                    plan,trace=shift_plan(plan,self.root/'shifts'/wire_context['id'],self.meter,self.c['shift_retained_bytes'])
                    path=self.root/'shifts'/wire_context['id']/'TRANSFORM.json'
                    transform={'path':str(path),**publish(path,encoded({'source':self.source,'context':context['id'],'trace':trace}),self.meter)}
                identity=context['id']+'-'+control;mounts,public,_=self.staged(identity,plan)
                a=bundle['inference_source'];mounts['/candidate/main.py']=file_mount(a['path'],{k:a[k] for k in ('bytes','sha256')},'program')
                a=bundle['recipe'];mounts['/recipe']=file_mount(a['path'],{k:a[k] for k in ('bytes','sha256')},'contract');mounts['/model']=state['model_mount']
                result=self.run(identity,'infer','A' if context['mode']==MODES[0] else 'B',{'recipe':True,'model':True},mounts,clock)
                if transform is not None:self.native.operands[identity]['transform']=transform
                nights=predictions(result,public,binding,person,self.meter)
                self.outputs.append({'context':identity,'mode':context['mode'],'profile':context['fitting_profile'],'fold':context['fold'],'subject':person,
                    'view':context['view'],'control':control,'source':{k:bundle['inference_source'][k] for k in ('bytes','sha256')},
                    'recipe':{k:bundle['recipe'][k] for k in ('bytes','sha256')},'model':state['model'],'fit':state['fit'],'inference':result['receipt_pin'],'nights':nights})
            self.meter.tick()

    def execute(self):
        # Reference outputs are operator-only; candidate realms never mount them.
        # Shared fixed fits seal before any candidate query context starts.
        try:
            self.construct_caches();self.construct_references();self.construct_shared_fits();self.construct_candidates()
            need(len(self.outputs)==2106,'No incomplete full study accepted')
            prediction_pin=publish(self.root/'PREDICTIONS.json',encoded(self.outputs),self.meter)
            receipt_pin=publish(self.root/'RECEIPTS.json',encoded(self.receipts),self.meter)
            needed={self.receipt_logical[r[k]['sha256']] for r in self.outputs for k in ('fit','inference')}
            context_pin=publish(self.root/'PRIVATE_CONTEXTS.json',encoded(self.context_wire),self.meter)
            operands_pin=publish(self.root/'OPERANDS.json',encoded({i:self.native.operands[i] for i in sorted(needed)}),self.meter)
            report={'schema':'neural007_campaign_source_completion_v1','source':self.source,'graph':pin(encoded(self.graph)),
                    'predictions':prediction_pin,'receipts':receipt_pin,'operands':operands_pin,
                    'private_presentations':self.presentation_pin,'private_contexts':context_pin,'counts':self.graph['counts'],'accounting':self.meter.report(),
                    'fixed_source_authoring_cost':self.fixed_admission['authoring_cost'],
                    'native_tracked_io':{'read_bytes':self.native.provider.read_used,'write_reserved_bytes':self.native.provider.write_used},
                    'provider_context_costs':self.provider_costs,'tracked_io_envelopes':self.grant['tracked_io_envelopes'],
                    'cost_exclusions':'Producer numerical I/O, peak RSS, filesystem overhead, Python/import/bootstrap and unmetered host metadata work remain unknown; disjoint tracked pools are not whole-host cost.',
                    'scientific_content_admitted':False,'outer_scores_loaded':False,'runtime_qualification_inherited':False}
            publish(self.root/'COMPLETION.json',encoded(report),self.meter);return report
        except BaseException as exc:
            try:publish(self.root/'FAILED.json',encoded({'type':type(exc).__name__,'completed_phase_count':len(self.sequence),
                'completed_inferences':len(self.outputs),'accounting':self.meter.report(),'automatic_retry':False}),self.meter)
            except BaseException:pass
            raise
