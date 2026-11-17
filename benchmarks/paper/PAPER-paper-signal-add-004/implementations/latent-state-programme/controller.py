"""Concrete whole-program composition; run only inside the outer supervisor.

All candidate programs commit before original data. A real transport.Provider
owns each isolated phase; no executor/admission/scoring implementation is
supplied by candidate code. The supervisor owns terminal process/cleanup proof.
"""
import argparse
import copy
import hashlib
import os
import time
from pathlib import Path
import access
from budget import Budget
from core import TASK, REVISION, BRANCHES, HMM, ROLES, CONTROLS, encoded, identity, need, runs
from safe_io import capture, strict, child, pin
import staging
import workflow
from operation import validate_operation, inner_limits

COMMON = ['core.py','safe_io.py','arm_worker.py','native/__init__.py','native/contract.py']
B_EXTRA = ['native_run.py','native_entry.py','native/sink.py']


def mount(view, purpose):
    return {'path':view['root'],'kind':'directory','purpose':purpose,
            'files':{**view['files'],'VIEW.json':view['manifest']}}


class Operations:
    def __init__(self, operation, root, origin, source_root):
        validate_operation(operation)
        self.op=copy.deepcopy(operation);self.root=Path(root);self.source=Path(source_root)
        self.root.mkdir(mode=0o700,parents=False,exist_ok=False)
        (self.root/'journal').mkdir(mode=0o700)
        self.budget=Budget(inner_limits(self.op),origin,self.root/'journal')
        self.ordinal=0;self.phases=[];self.sources={};self.programs={};self.boundaries={}
        self.original=None;self.folds={};self.artifacts={};self.closures={}
        self.transport_reads=self.transport_writes=0
        self.working_deadline=self.budget.end-self.op['outer_cleanup_seconds']
        need(origin<self.working_deadline<self.budget.end,'Reserved independent terminal cleanup window')

    def save(self,path,value):
        return self.budget.save(path,encoded(value))

    def view(self,label,members):
        """Explicit mixed-root inventory, never a host-directory wildcard mount."""
        root=self.root/'views'/label;need(not root.exists(),'Fresh phase view')
        root.mkdir(mode=0o700,parents=True)
        files={}
        for name,item in sorted(members.items()):
            staging.validate_files({name:item['pin']})
            body=self.budget.read_file(item['path'],item['pin'],max(1,item['pin']['bytes']))
            target=root/name;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            files[name]=self.budget.save(target,body);os.chmod(target,0o444)
        descriptor=self.save(root/'VIEW.json',{'schema':'osl_closed_role_view_v1','files':files})
        os.chmod(root/'VIEW.json',0o444)
        for directory in [root,*[p for p in root.rglob('*') if p.is_dir()]]:os.chmod(directory,0o555)
        return {'root':str(root.absolute()),'manifest':descriptor,'files':files,
                'bytes':sum(x['bytes'] for x in files.values())+descriptor['bytes']}

    def json_view(self,label,name,value,members=None):
        directory=self.root/'metadata';directory.mkdir(mode=0o700,exist_ok=True)
        path=directory/(label+'.json');d=self.save(path,value)
        return self.view(label,{**(members or {}),name:{'path':str(path),'pin':d}})

    def precommit(self):
        op=self.op
        need(op['schema']=='osl_complete_program_operation_v1' and op['task_id']==TASK
             and op['scientific_execution_authorized'] is True and op['scientific_qualification'] is False,
             'Separately selected explicit scientific operation, not BUILD authorization')
        need(set(op['images'])=={'A','B','reference','operator'} and
             set(op['programs'])=={'A','B'} and set(op['boundaries'])==set(op['images']), 'All isolated roles')
        source_manifest=strict(self.budget.read_file(op['source_manifest']['path'],
            {k:op['source_manifest'][k] for k in ('bytes','sha256')},1048576))
        source_files={r['path']: {k:r[k] for k in ('bytes','sha256')} for r in source_manifest['files']}
        # The manifest is rooted at this exact source directory, not arbitrary
        # sibling workspaces or an unfrozen central integration folder.
        staging.validate_files(source_files)
        for role in ('A','B','reference','operator'):
            names=COMMON+(B_EXTRA if role=='B' else []) if role in ('A','B') else [n for n in source_files if n.endswith('.py') and not n.startswith(('peer-review/','review-revisions/','transport/')) and not n.startswith('engineering_')]
            need(all(n in source_files for n in names),'Complete concrete role implementation source')
            self.sources[role]=staging.materialize(self.root/'sources'/role,self.source,
                {n:source_files[n] for n in names},self.budget)
            b=op['boundaries'][role]
            body=self.budget.read_file(b['path'],b['pin'],2000000)
            proof=strict(body)
            source_rows=strict(self.budget.read_file(b['source_rows']['path'],b['source_rows']['pin'],op['boundary_metadata_bytes']))
            access.validate(proof,'reference' if role=='operator' else role,op['images'][role],
                            b['inventory_sha256'],source_rows,op['author_source_hashes'])
            self.boundaries[role]={'proof':proof,'pin':b['pin'],'inventory_sha256':b['inventory_sha256'],'source_rows':source_rows}
        for role in ('A','B'):
            need(set(op['programs'][role])=={'native','held_hmm'},'Both committed candidate programs')
            self.programs[role]={}
            for family, item in op['programs'][role].items():
                body=self.budget.read_file(item['path'],item['pin'],1048576)
                target=self.root/'programs'/role/(family+'.py');target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                d=self.budget.save(target,body);os.chmod(target,0o444)
                self.programs[role][family]={'path':str(target.absolute()),'pin':d}
        need(op['engine_source_pin']==source_files['transport/SOURCE_MANIFEST.json'] and
             op['canonical_native_entry_sha256']==source_files['native_entry.py']['sha256'],
             'Concrete actual transport and canonical native entry, not caller-chosen substitutes')
        self.selection_source=identity({'worker':source_files['worker.py'],'selection':source_files['selection.py'],
                                       'image':op['images']['operator']})
        for role in ROLES:
            expected={'entrypoint':['/source/worker.py' if role=='reference' else '/source/arm_worker.py'],
                      'source_sha256':identity(self.sources[role]['files']) if role=='reference' else
                          identity({k:v['pin'] for k,v in self.programs[role].items()}),
                      'selection_producer_source_pin':self.selection_source}
            need(op['attempt_policy']['programs'][role]==expected,'Attempt policy binds actual source/program/selection identities')
        need(op['attempt_policy']['provider_source_pin']==op['engine_source_pin']['sha256'],'Exact provider policy source')
        self.budget.event({'event':'all_programs_images_source_committed_before_data',
                          'programs':self.programs,'images':op['images'],
                          'source_manifest':op['source_manifest'],'native_attempts':453,'held_attempts':5400,
                          'maximum_additional_selection_phases':5850})

    def phase(self,action,role,payload,mounts=None,output_kind='generic',candidate=None,cutoff=None):
        from transport import Provider
        self.budget.tick();self.ordinal+=1
        phase_id=identity({'operation':self.op['operation_id'],'ordinal':self.ordinal,'action':action,'role':role})
        resources=self.op['phase_resources'][action]
        if self.budget.attempt is not None:
            need(resources['memory_bytes']<=self.attempt_memory_cap,
                 'Every compound producer/selection memory ceiling fits the original attempt before dispatch')
            self.attempt_max_memory=max(self.attempt_max_memory,resources['memory_bytes'])
        seconds=sum(resources[k] for k in ('setup_seconds','producer_seconds','capture_seconds','cleanup_seconds'))
        end=min(self.working_deadline,cutoff) if cutoff is not None else self.working_deadline
        need(self.budget.tick()+seconds<=end,'Complete phase fits original work cutoff plus reserved terminal cleanup')
        root=self.root/'phases'/phase_id;root.mkdir(mode=0o700,parents=True)
        name='CASE.json' if candidate is not None else 'PAYLOAD.json'
        view=self.json_view(phase_id,name,payload)
        all_mounts={'/source':mount(self.sources[role],'program'),'/input':mount(view,'input'),**(mounts or {})}
        if candidate is None:
            command=['/usr/local/bin/python','/source/worker.py','--payload','/input/PAYLOAD.json']
        else:
            item=self.programs[role][candidate]
            target='/program/'+Path(item['path']).name
            all_mounts[target]={'path':item['path'],'kind':'file','purpose':'program',
                                               'files':{Path(item['path']).name:item['pin']}}
            command=['/usr/local/bin/python','/source/arm_worker.py','--program',target,
                     '--program-sha256',item['pin']['sha256']]
        source=self.sources[role]['manifest'];audit=self.boundaries[role]
        reviewed={r['path']:{k:r[k] for k in ('bytes','sha256')} for r in audit['source_rows']}
        mounted={}
        for target,desc in all_mounts.items():
            if desc['purpose'] not in ('program','historical_author_source','operator_reference'):continue
            for name,d in desc['files'].items():
                if name=='VIEW.json':continue # transport metadata; contains no source body
                address=target+'/'+name if desc['kind']=='directory' else target
                mounted[address]=d
        need(mounted and all(reviewed.get(path)==d for path,d in mounted.items()),
             'Actual role source/program bytes join the independently reviewed full image/source inventory')
        exposure={'schema':'osl_transport_exposure_v1','role':role,'image':self.op['images'][role],
                  'source':source,'command':command,
                  'mounts':{k:{x:v[x] for x in ('kind','purpose','files')} for k,v in all_mounts.items()},
                  'approved_image_inventory_sha256':audit['inventory_sha256'],
                  'boundary_audit':audit['pin'],'role_boundary_verified':True}
        exposure_path=root/'EXPOSURE.json';exposure_pin=self.save(exposure_path,exposure)
        request={'schema':'osl_owned_phase_request_v1','phase_id':phase_id,'action':action,'role':role,
                 'image':self.op['images'][role],'command':command,'workdir':'/work','source':source,
                 'exposure':exposure_pin,'clock':{'origin':self.budget.origin,'phase_deadline':end},
                 'resources':resources,'output':{'kind':output_kind,'manifest':'CAPTURE.json' if output_kind=='native_capture' else'OUTPUTS.json'}}
        request_pin=self.save(root/'REQUEST.json',request)
        observer_cap=self.op['observer_read_bytes']
        self.budget.reserve_producer(phase_id,resources['source_read_bytes']+observer_cap,resources['host_write_bytes'],resources['host_write_bytes'])
        (root/'control').mkdir(mode=0o700);(root/'quarantine').mkdir(mode=0o700)
        provider=Provider(root/'control',root/'quarantine',self.op['docker']['binary'],self.op['docker']['socket'],
                          self.op['engine_source_pin'],{exposure_pin['sha256']:str(exposure_path)},
                          resources['source_read_bytes']+observer_cap,resources['host_write_bytes'])
        self.budget.event({'event':'phase_declared','phase_id':phase_id,'request':request_pin,'control_root':str(root/'control')})
        journal=lambda name,value:self.budget.event({'event':'transport','phase_id':phase_id,'name':name,'value':value})
        result=provider.execute_phase(request,all_mounts,self.budget.end,journal)
        need(result['receipt_pin']['bytes']+1<=observer_cap,'Prospectively reserved complete observer receipt')
        observed=provider.observe(phase_id,request_pin['sha256'],result['receipt_pin'],self.budget.end)
        self.transport_reads+=result['final_transport_counters']['read_bytes']+observed['read_bytes']
        self.transport_writes+=result['final_transport_counters']['write_bytes']
        self.budget.tick()
        record={'request':request,'request_pin':request_pin,**result};self.phases.append(record)
        receipt=result['receipt']
        if receipt.get('status')!='captured':
            if self.budget.attempt is not None:self.compound_memory_observed=False
            self.budget.event({'event':'phase_failed','phase_id':phase_id,'receipt':result['receipt_pin']})
            need(receipt.get('all_native_resources_closed') is True and receipt.get('cli_reaped') is True,
                 'Unresolved native custody stops further dispatch for independent outer recovery')
            staging.retire(view,True,self.budget)
            return record
        files=receipt['output_inventory']['files'];staging.validate_files(files)
        retained=sum(p.stat().st_size for folder in (root/'control',root/'quarantine') for p in folder.rglob('*') if p.is_file())
        self.budget.settle(phase_id,retained,True)
        staging.retire(view,True,self.budget)
        record['root']=receipt['quarantine_root'];record['files']=files
        if output_kind=='generic':
            record['result']=strict(self.budget.read_file(child(record['root'],'RESULT.json'),files['RESULT.json'],resources['max_file_bytes']))
        return record

    def originals(self):
        # Explicit original files are readonly; no credentials or unrelated user
        # trees are mounted. The independently bound full Elekta metadata is a
        # mandatory input, not synthesized by this program.
        op=self.op;spec=copy.deepcopy(op['originals']['spec']);mounts={};members={}
        for key in ('ctf_archive','ctf_directory','elekta_binding'):
            item=spec[key];members[key]={'path':item['path'],'pin':{k:item[k] for k in ('bytes','sha256')}}
            item['path']='/original/'+key
        originals_view=self.view('original_archive_metadata',members)
        for key in members:
            mounts['/original/'+key]={'path':str(Path(originals_view['root'])/key),'kind':'file','purpose':'input',
                                      'files':{key:originals_view['files'][key]}}
        e=op['originals']['elekta_inventory']
        elekta_view=staging.materialize(self.root/'views'/'original_elekta',spec['elekta_root'],e,self.budget)
        mounts['/original/elekta']=mount(elekta_view,'input')
        spec['elekta_root']='/original/elekta'
        self.original=self.phase('prepare_originals','operator',{'source_spec':spec,'io_limits':op['originals']['io_limits']},mounts)
        need('result' in self.original,'Complete original-source preparation required')
        self.original['data_root']=str(Path(self.original['root'])/'originals')
        staging.retire(originals_view,True,self.budget);staging.retire(elekta_view,True,self.budget)

    def original_view(self,branch,label):
        result=self.original['result'];prefix='elekta/' if branch.startswith('elekta') else'ctf/'
        files={n[len(prefix):]:d for n,d in result['native_files'].items() if n.startswith(prefix)}
        return staging.materialize(self.root/'views'/label,Path(self.original['data_root'])/prefix[:-1],files,self.budget)

    def folds_prepare(self):
        original_files={n[len('originals/'):]:d for n,d in self.original['files'].items() if n.startswith('originals/')}
        view=staging.materialize(self.root/'views'/'originals_for_folds',self.original['data_root'],original_files,self.budget)
        for branch in HMM:
            for fold in range(5):
                p=self.original['result']['packets'][branch]
                payload={'packet_path':'/originals/'+p['path'],'packet_pin':{k:p[k] for k in ('bytes','sha256')},
                         'packet_identity':p['identity'],'original_root':'/originals','branch':branch,'fold':fold,
                         'budget':self.op['fold_budget']}
                record=self.phase('prepare_fold','operator',payload,{'/originals':mount(view,'input')})
                need('result' in record,'Every full original person fold must prepare')
                self.folds[f'{branch}:{fold}']=record
        staging.retire(view,True,self.budget)

    def training_view(self,job,label):
        f=self.folds[f"{job['branch']}:{job['fold']}"];p=f['result']['preparation'];rows=p['training_controls'][job['control']]
        members={};mapped=[]
        for i,r in enumerate(rows):
            d=r['observations'];name=f'arrays/{i:04d}.npy';members[name]={'path':str(Path(f['root'])/'fold'/d['path']),
                'pin':{k:d[k] for k in ('bytes','sha256')}}
            mapped.append({'person':r['person'],'run':r['run'],'observations':{**d,'path':name}})
        data={'schema':'osl_training_view_v1','task_id':TASK,'branch':job['branch'],'fold':job['fold'],
              'control':job['control'],'representation_id':p['representation_id'],'runs':mapped,
              'query_observations_included':False}
        view=self.json_view(label,'TRAINING.json',data,members)
        return view,data

    def native_context(self,job):
        branch=job['branch'];files=self.original['result']['native_files'];rows=[]
        for person,run in runs(branch):
            if branch.startswith('elekta'):
                path=f'src/{person}_run{run:02d}/sflip_parc-raw.fif';key='elekta/'+path;source='data/'+path
            else:
                path=('bursts/' if branch=='ctf_bursts' else'networks/')+person+'.npy';key='ctf/'+path;source='training_data/'+path
            rows.append({'person_id':person,'run_id':str(run),
                         'input_id':identity({'lineage':self.original['result']['lineage'],'source_member':key,'person':person,'run':run}),
                         'source_input':source})
        return {'branch':branch,'revision':REVISION,'attempt_id':job['id'],'role':job['role'],'seed':job['seed'],
                'preparation_binding':self.original['result']['lineage'],'runs':rows}

    def environment(self,role='operator'):
        need(role in ('operator','reference'),'Private source environment only')
        return {'role':'reference','source_revision':REVISION,'image_digest':self.op['images'][role],
                'inventory_sha256':self.boundaries[role]['inventory_sha256']}

    def execute(self,request):
        self.budget.begin_attempt(request['limits']['phase_read_bytes'],request['limits']['phase_write_bytes'],request['clock']['phase_deadline'])
        self.attempt_memory_cap=request['limits']['phase_memory_bytes'];self.attempt_max_memory=0;self.compound_memory_observed=True
        job=request['job'];role=job['role'];start=self.budget.tick()
        before=(self.budget.file_reads+self.transport_reads,self.budget.file_writes+self.transport_writes)
        native_view=None;training=None;data=None;context=None
        if job['phase']=='native':
            context=self.native_context(job);native_view=self.original_view(job['branch'],job['id']+'_native')
            target='/work/data' if job['branch'].startswith('elekta') else'/work/training_data'
            payload={'job':job,'context':context,'capture_cap':self.op['phase_resources']['native_attempt']['max_output_bytes']}
            if role!='A':
                payload.update(self.op['native_scripts'][job['branch']])
                payload['exposure']={'role':role,'image_digest':self.op['images'][role],
                    'inventory_sha256':self.boundaries[role]['inventory_sha256']}
            phase=self.phase('native_attempt',role,payload,{target:mount(native_view,'input')},'native_capture',None if role=='reference' else'native',request['clock']['phase_deadline'])
        else:
            training,data=self.training_view(job,job['id']+'_training')
            t=training['files']['TRAINING.json']
            payload={'job':job,'view_path':'/training/TRAINING.json','view_pin':t,'input_root':'/training',
                     'array_cap':self.op['fold_budget']['array_bytes'],'training_view':data}
            if role=='reference':
                payload.update(environment=self.environment('reference'),diagnostic_cap=self.op['reference_diagnostic_cap'])
            phase=self.phase('held_attempt',role,payload,{'/training':mount(training,'input')},
                             candidate=None if role=='reference' else'held_hmm',cutoff=request['clock']['phase_deadline'])
        natural='files' in phase;measurement=None;output_files={}
        if natural:
            output_files=phase['files'] if job['phase']=='native' else {'MODEL.json':phase['files']['MODEL.json']}
            temporary={'job':job,'status':'completed','outputs':output_files,'capture_pin':phase['receipt_pin']['sha256']}
            artifact={'root':phase['root'],'context':context,'files':output_files,'producer':phase['receipt_pin']}
            self.artifacts[job['id']]=artifact
            if job['branch']!='ctf_static':
                model_view=staging.materialize(self.root/'views'/(job['id']+'_model'),phase['root'],output_files,self.budget)
                payload={'disposition':temporary,'model_root':'/model','output_cap':self.op['phase_resources'][phase['request']['action']]['max_output_bytes'],
                         'environment':self.environment()}
                mounts={'/model':mount(model_view,'input')}
                if job['phase']=='native':
                    payload.update(context=context,trusted_original_pipeline=(role=='reference' or
                        role=='B' and self.programs['B']['native']['pin']['sha256']==self.op['canonical_native_entry_sha256']))
                    mounts[target]=mount(native_view,'input')
                else:
                    payload.update(representation_id=data['representation_id'],view_path='/training/TRAINING.json',
                                   view_pin=training['files']['TRAINING.json'],input_root='/training',array_cap=self.op['fold_budget']['array_bytes'])
                    mounts['/training']=mount(training,'input')
                selected=self.phase('selection_evaluate','operator',payload,mounts,cutoff=request['clock']['phase_deadline'])
                if 'result' in selected and selected['result'].get('available'):
                    r=selected['result'];measurement={'value':r['value'],'criterion':r['criterion'],
                        'producer_source_pin':request['program']['selection_producer_source_pin'],
                        'input_binding':identity(request['input_view']),'candidate_supplied':False,'query_used':False,
                        'evidence_mode':r['evidence_mode'],'evidence_pin':selected['receipt_pin']['sha256']}
                staging.retire(model_view,True,self.budget)
        if native_view is not None:staging.retire(native_view,True,self.budget)
        if training is not None:staging.retire(training,True,self.budget)
        finished=self.budget.tick();state=phase['receipt'].get('natural_exit') or {}
        closure={'schema':'osl_attempt_closure_v1','request_id':identity(request),'job_id':job['id'],
                 'natural_exit':natural,'exit_code':0 if natural else state.get('ExitCode',-1),
                 'reason':('' if self.compound_memory_observed else'compound_phase_enforcement_unobserved') if natural else'producer_or_capture_failed','oom':bool(state.get('OOMKilled',False)),
                 'deadline_exceeded':finished>request['clock']['phase_deadline'],'provider_error':not natural,
                 'outputs':output_files,'training_measurement':measurement,
                 'cost':{'elapsed_s':finished-start,'read_bytes':self.budget.file_reads+self.transport_reads-before[0],
                         'write_bytes':self.budget.file_writes+self.transport_writes-before[1],'peak_memory_bytes':None},
                 'resource_observation':{'scope':'observed_transport_and_staging_only','producer_read_bytes':None,
                    'producer_write_bytes':None,'exact_peak_memory_bytes':None,
                    'enforced_memory_bytes':self.attempt_max_memory if natural and self.compound_memory_observed else None,
                    'enforced_memory_observed':natural and self.compound_memory_observed,
                    'transport_receipt_pin':phase['receipt_pin']['sha256']},
                 'timing':{'origin':request['clock']['origin'],'deadline':request['clock']['phase_deadline'],
                           'started':start,'finished':finished}}
        path=self.root/'closures'/f"{job['id']}.json";path.parent.mkdir(mode=0o700,exist_ok=True)
        descriptor=self.save(path,closure);self.closures[(job['id'],identity(request))]={'path':str(path),'pin':descriptor}
        self.budget.read(descriptor['bytes']) # reserve the following independent compound-closure observation
        self.budget.end_attempt()
        return closure

    def observe(self,job_id,request_id):
        row=self.closures[(job_id,request_id)]
        body=self.budget.read_file(row['path'],row['pin'],row['pin']['bytes'])
        return hashlib.sha256(body).hexdigest()

    def assessment(self,execution):
        members={};artifacts={};folds={}
        for job_id,a in self.artifacts.items():
            for name,d in a['files'].items():
                members['artifacts/'+job_id+'/'+name]={'path':str(child(a['root'],name)),'pin':d}
            artifacts[job_id]={'root':'/assessment/artifacts/'+job_id,'context':a['context']}
        for key,f in self.folds.items():
            branch,fold=key.split(':');physical=f'folds/{branch}/fold{fold}'
            for name,d in f['files'].items():
                members[physical+'/'+name]={'path':str(child(f['root'],name)),'pin':d}
            prefix='/assessment/'+physical
            folds[key]={'root':prefix+'/fold','preparation_path':prefix+'/fold/PREPARATION.json',
                        'preparation_pin':f['files']['fold/PREPARATION.json'],'static_path':prefix+'/STATIC.json',
                        'static_pin':f['files']['STATIC.json'],'representation_id':f['result']['representation_id']}
        age=self.original['result']['ages'];members['AGES.json']={'path':str(Path(self.original['data_root'])/'AGES.json'),
                                                                 'pin':{k:age[k] for k in ('bytes','sha256')}}
        view=self.json_view('assessment','EXECUTION.json',execution,members)
        payload={'execution_path':'/assessment/EXECUTION.json','execution_pin':view['files']['EXECUTION.json'],
                 'artifacts':artifacts,'folds':folds,'age_path':'/assessment/AGES.json','age_pin':view['files']['AGES.json'],
                 'age_identity':age['identity'],'scales':self.op['native_scales'],
                 'scale_pins':{b:identity(s) for b,s in self.op['native_scales'].items()},**self.op['assessment_limits']}
        result=self.phase('final_evaluate','operator',payload,{'/assessment':mount(view,'input')})
        if 'result' in result:staging.retire(view,True,self.budget)
        return result

    def run(self):
        self.precommit();self.originals();self.folds_prepare()
        policy=copy.deepcopy(self.op['attempt_policy'])
        policy.update(source_freeze=self.op['source_manifest'],images={r:self.op['images'][r] for r in ROLES},
                      exposure_audits={r:self.boundaries[r]['pin'] for r in ROLES},
                      native_inputs={b:{'original_lineage':self.original['result']['lineage'],'branch':b} for b in BRANCHES},
                      held_preparations={k:{'representation_id':f['result']['representation_id'],
                          'training_controls':{c:identity(f['result']['preparation']['training_controls'][c]) for c in CONTROLS},
                          'operator_query_pin':identity(f['result']['preparation']['operator_private_query']),
                          'static_reference_pin':f['result']['static']} for k,f in self.folds.items()})
        execution=workflow.execute(policy,identity(policy),self.execute,self.observe,self.budget.event,self.budget.tick,
                                   {'origin':self.budget.origin,'deadline':self.working_deadline})
        execution_pin=self.save(self.root/'EXECUTION.json',execution)
        assessed=self.assessment(execution)
        report={'schema':'osl_complete_program_inner_return_v1','task_id':TASK,'source':self.op['source_manifest'],
                'execution':execution_pin,'assessment':assessed.get('receipt_pin'),
                'numerical_complete':bool(assessed.get('result',{}).get('complete',False)),
                'phase_receipts':[p['receipt_pin'] for p in self.phases],'budget':self.budget.snapshot(),
                'actual_whole_producer_resources_measured':False,'outer_natural_exit_and_terminal_absence_required':True,
                'runtime_qualified':False,'scientific_qualification':False,'whole_paper_reproduced':False}
        result=self.save(self.root/'INNER_RETURN.json',report);self.budget.tick();return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--operation',required=True);p.add_argument('--operation-sha256',required=True)
    p.add_argument('--output',required=True);p.add_argument('--origin',type=float,required=True);a=p.parse_args()
    raw=capture(a.operation,1048576);need(hashlib.sha256(raw).hexdigest()==a.operation_sha256,'Externally selected operation')
    op=strict(raw);Operations(op,a.output,a.origin,Path(__file__).resolve().parent).run()


if __name__=='__main__':main()
