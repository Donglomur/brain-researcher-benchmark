"""Concrete full I operation, exclusively launched by the independent supervisor.

Every fit/query is a real immutable-image Provider phase. No executor, grader or
scientific callback is supplied by a candidate. Importing this module does not
start Docker, load arrays, fit a model or select an actual operation.
"""
import argparse
import copy
import hashlib
import os
import random
import secrets
import time
from pathlib import Path
import access
import planner
import staging
from budget import Budget
from core import TASK, ROLES, PROFILES, BRANCHES, INPUTS, need, encoded, identity, high_level_jobs
from operation import validate_operation
from safe_io import capture, strict, child
from transport import Provider
from transport.contract import validate_request, validate_exposure
from transport.bounds import mount_identity


def pin(row):return {k:row[k] for k in ('bytes','sha256')}

def mount(view,purpose):
    return {'path':view['root'],'kind':'directory','purpose':purpose,'files':view['files']}


class Operations:
    def __init__(self,operation,root,origin,global_deadline,work_deadline,source_root):
        self.op=validate_operation(copy.deepcopy(operation));self.root=Path(root);self.source=Path(source_root)
        need(global_deadline==origin+self.op['global_limits']['wall_seconds'] and work_deadline==global_deadline-self.op['host']['cleanup_seconds'],'Supervisor original clocks and reserved independent cleanup')
        self.root.mkdir(mode=0o700,parents=False,exist_ok=False)
        for n in ('journal','views','control','quarantine','exposures','metadata'): (self.root/n).mkdir(mode=0o700)
        limits={**self.op['host']['controller_limits'],'wall_seconds':global_deadline-origin}
        self.budget=Budget(limits,origin,self.root/'journal');self.work_deadline=work_deadline
        self.phases=[];self.seen=[];self.selections=[];self.job_results={};self.encoding_outputs={};self.native_outputs={};self.grades=[]
        self.plan=None;self.current_job=None;self.encoding_sealed=False;self.custody_known=True
        self.boundaries={};self.programs={};self.ordinal=0;self.shuffle_cache={}
        self.attempt_memory=None

    def save(self,path,value):return self.budget.save(path,encoded(value))

    def read_json(self,path,p):return strict(self.budget.read_file(path,p,self.op['host']['max_metadata_bytes']))

    def event(self,row):
        need(len(self.budget.events)<self.op['host']['max_events'],'Complete journal limit; never discard events')
        return self.budget.event(row)

    def view(self,members):
        root=self.root/'views'/secrets.token_hex(16);root.mkdir(mode=0o700)
        files={}
        for name,item in sorted(members.items()):
            staging.validate_files({name:item['pin']})
            target=child(root,name);target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            from streaming import copy_file
            files[name]=copy_file(item['path'],target,item['pin'],self.budget)
        # The metadata is private; views mount exactly their declared members.
        for d in [root,*[p for p in root.rglob('*') if p.is_dir()]]:os.chmod(d,0o555)
        return {'root':str(root.absolute()),'files':files,'bytes':sum(p['bytes'] for p in files.values())}

    def json_view(self,name,value,members=None):
        p=self.root/'metadata'/(secrets.token_hex(16)+'.json');d=self.save(p,value)
        return self.view({**(members or {}),name:{'path':str(p),'pin':d}})

    def record_members(self,record,prefix='',names=None):
        return {n[len(prefix):]:{'path':str(child(record['root'],n)),'pin':d} for n,d in record['files'].items() if n.startswith(prefix) and (names is None or n in names)}

    def source_view(self,spec):return self.view({n:{'path':str(child(spec['root'],n)),'pin':d} for n,d in spec['files'].items()})

    def precommit(self):
        op=self.op;m=self.read_json(op['source_manifest']['path'],pin(op['source_manifest']))
        need(m['schema']=='paper_i_executable_source_manifest_v1','Exact executable implementation manifest')
        files={r['path']:pin(r) for r in m['files']};staging.validate_files(files)
        need(len(files)==len(m['files']) and all(n in files for n in ('worker.py','controller.py','supervisor.py','transport/SOURCE_MANIFEST.json','native/BINDINGS.json')),'Complete implementation closure')
        self.contract=self.source_view({'root':str(self.source),'files':{'PUBLIC_CONTRACT.md':files['PUBLIC_CONTRACT.md']}})
        self.engine_pin=files['transport/SOURCE_MANIFEST.json']
        self.source_view_all=self.source_view({'root':str(self.source),'files':files})
        self.source_pin={'bytes':len(encoded(files)),'sha256':identity(files)}
        need(pin(op['paper'])=={'bytes':204482,'sha256':'68fadc1d857652feeea80db41e5564ff66e32006ce96496481d54b5ef4cf355b'},'Exact common article exposure')
        self.paper=self.view({'article.xml':{'path':op['paper']['path'],'pin':pin(op['paper'])}})
        from native.bridge import assembly_plan, PREPARATION_FILES, validate_bindings
        bindings=self.read_json(child(self.source,'native/BINDINGS.json'),files['native/BINDINGS.json']);validate_bindings(bindings)
        author_files={r['target']:pin(r) for r in bindings['original_files']}
        need(op['author_source']['files']==author_files,'Exact42 original source members for B')
        native_files={r['path']:pin(r) for r in bindings['original_files']+bindings['wrappers']+bindings['helpers']}
        need(op['native_source']['files']==native_files,'Exact54 held original and derivative source members')
        self.author=self.source_view(op['author_source'])
        assembly=assembly_plan(op['native_source']['root'],str(self.source/'native'),bindings,{n:files['native/'+n] for n in PREPARATION_FILES},'operator')
        self.native=self.view({r['target']:{'path':str(child(r['root'],r['record']['path'])),'pin':pin(r['record'])} for r in assembly})
        for role in ('A','B'):self.programs[role]=self.source_view(op['programs'][role]['source'])
        source_roles={r:({'bytes':len(encoded(self.programs[r]['files'])),'sha256':identity(self.programs[r]['files'])} if r in self.programs else self.source_pin) for r in (*ROLES,'operator')}
        for role,image in op['images'].items():
            inv=self.read_json(image['inventory']['path'],pin(image['inventory']));audit=self.read_json(image['boundary_audit']['path'],pin(image['boundary_audit']))
            forbidden=[d['sha256'] for d in files.values()]+[pin(r)['sha256'] for r in bindings['wrappers']+bindings['helpers']]
            if role=='A':forbidden += [d['sha256'] for d in author_files.values()]
            access.approve_image(role,image,inv,audit,source_roles[role],forbidden)
            self.boundaries[role]=audit
        q=self.read_json(op['qualification']['path'],pin(op['qualification']))
        need(type(q) is dict and q.get('schema')=='paper_i_runtime_qualification_v1' and q.get('source')==pin(op['source_manifest']) and q.get('images')=={r:v['digest'] for r,v in op['images'].items()} and q.get('docker_binary')==op['host']['docker_binary_pin'],'External exact runtime/source/image qualification')
        need(all(q.get(k) is True for k in ('linux_pidfd_cgroup_verified','shared_monotonic_clock_verified','isolated_query_no_persistence_verified','primitive_writer_parity_verified','matlab_toolboxes_verified','full_image_and_mount_boundary_verified')),'Actual native/provider qualification remains a separate gate')
        self.event({'event':'all_source_images_programs_committed_before_data','source':op['source_manifest'],'programs':{r:source_roles[r] for r in ('A','B')},'qualification':pin(op['qualification'])})

    def phase(self,action,role,payload,slot,mounts=None,input_members=None):
        need(self.custody_known,'Unknown native custody stops all dispatch')
        self.budget.tick();self.ordinal+=1;need(self.ordinal<=self.op['host']['max_phases'],'Complete phase roster bound')
        if self.plan is not None:need(planner.valid_slot(self.plan,slot),'Exact declared logical phase')
        else:need(slot['stage'] in ('prepare_originals','prepare_support'),'Only full preparation before PLAN')
        phase_id=secrets.token_hex(16);resources=self.op['phase_resources'][action]
        need(resources['source_read_bytes']>=1048576,'Worker request bootstrap reserved')
        if self.attempt_memory is not None:need(resources['memory_bytes']<=self.attempt_memory,'Every compound phase memory cap inside producer allocation')
        end=min(self.work_deadline,self.budget.attempt['deadline']) if self.budget.attempt else self.work_deadline
        seconds=sum(resources[k] for k in ('setup_seconds','producer_seconds','capture_seconds','cleanup_seconds'))
        need(self.budget.tick()+seconds<=end,'Complete owned phase plus cleanup inside original cutoff')
        need(not self.encoding_sealed or action not in ('fit','query'),'Encoding seal is irreversible')
        public=role in ('A','B')
        if public:access.public_payload(action,role,payload)
        name='REQUEST.json' if public else 'PAYLOAD.json';view=self.json_view(name,payload,input_members)
        allmounts={'/input':mount(view,'input'),**(mounts or {})}
        if public:
            allmounts['/program']=mount(self.programs[role],'program')
            allmounts['/contract']=mount(self.contract,'contract')
            allmounts['/paper/article.xml']={'path':str(Path(self.paper['root'])/'article.xml'),'kind':'file','purpose':'paper','files':{'article.xml':self.paper['files']['article.xml']}}
            if role=='B':allmounts['/author']=mount(self.author,'historical_author_source')
            access.candidate_mounts(action,role,allmounts,self.encoding_sealed)
            command=self.op['programs'][role]['commands'][action]
            source={'bytes':len(encoded(self.programs[role]['files'])),'sha256':identity(self.programs[role]['files'])}
        else:
            allmounts['/source']=mount(self.source_view_all,'operator_reference')
            command=['/usr/local/bin/python','-I','-B','/source/worker.py','--payload','/input/PAYLOAD.json','--payload-bytes',str(view['files'][name]['bytes']),'--payload-sha256',view['files'][name]['sha256']]
            source=self.source_pin
        audit=self.boundaries[role]
        for target,row in allmounts.items():
            if row['purpose'] not in ('program','operator_reference','historical_author_source'):continue
            for n,d in row['files'].items():
                address=target+'/'+n if row['kind']=='directory' else target
                need(audit['mounted_source_files'].get(address)==d,'Every actual source byte joins independent complete source audit')
        exposure={'schema':'osl_transport_exposure_v1','role':role,'image':self.op['images'][role]['digest'],'source':source,'command':command,'mounts':mount_identity(allmounts),'approved_image_inventory_sha256':self.op['images'][role]['inventory']['sha256'],'boundary_audit':pin(self.op['images'][role]['boundary_audit']),'role_boundary_verified':True}
        ep=self.root/'exposures'/(phase_id+'.json');exposure_pin=self.save(ep,exposure)
        request={'schema':'paper_i_owned_phase_request_v1','phase_id':phase_id,'action':action,'role':role,'image':self.op['images'][role]['digest'],'command':command,'workdir':'/work','source':source,'exposure':exposure_pin,'clock':{'origin':self.budget.origin,'phase_deadline':end},'resources':resources,'output':{'kind':'generic','manifest':'OUTPUTS.json'}}
        validate_request(request,allmounts,self.budget.end);validate_exposure(exposure,request,allmounts)
        request_pin={'bytes':len(encoded(request)),'sha256':identity(request)}
        self.event({'event':'nested_start','phase_id':phase_id,'job_id':slot['job_id'],'request_pin':request_pin,'action':action,'role':role,'control_directory':'control/'+phase_id,'original_deadline':self.budget.end,'exposure_path':'exposures/'+phase_id+'.json','exposure_pin':exposure_pin,'slot':slot})
        # Provider counters, output, worker reads/writes and independent observation
        # are prospectively charged; arbitrary candidate internal I/O is unknown.
        reserve_read=2*resources['source_read_bytes']+resources['inventory_bytes']
        reserve_write=resources['host_write_bytes']+resources['max_output_bytes']+resources['scratch_bytes']
        self.budget.reserve_producer(phase_id,reserve_read,reserve_write,reserve_write)
        provider=Provider(self.root/'control',self.root/'quarantine',self.op['host']['docker_binary'],self.op['host']['docker_socket'],self.engine_pin,{exposure_pin['sha256']:str(ep)},resources['source_read_bytes']+resources['inventory_bytes'],resources['host_write_bytes'])
        def journal(name,value):self.event({'event':'transport_event','phase_id':phase_id,'job_id':slot['job_id'],'name':name,**value})
        try:
            r=provider.execute_phase(request,allmounts,self.budget.end,journal)
            provider.observe(phase_id,request_pin['sha256'],r['receipt_pin'],self.budget.end)
            receipt=r['receipt'];closed=receipt.get('all_native_resources_closed') is True and receipt.get('cli_reaped') is True
            self.custody_known=self.custody_known and closed
            state='captured' if receipt.get('status')=='captured' and closed else 'failed' if closed else 'unknown'
            record={'phase_id':phase_id,'slot':slot,'request_pin':request_pin,**r}
            self.phases.append(record);self.seen.append({'slot':slot,'phase_id':phase_id,'status':state,'resources_closed':closed,'receipt_pin':r['receipt_pin']})
            self.event({'event':'nested_disposition','phase_id':phase_id,'job_id':slot['job_id'],'status':state,'receipt_pin':r['receipt_pin'],'resources_closed':closed})
            need(state=='captured','Complete natural phase capture required')
            # Retire the temporary-volume allowance only after observed closure.
            # Successfully written host bytes remain a conservative retained upper,
            # including any written-then-deleted partial files; cumulative I/O is not refunded.
            self.budget.settle(phase_id,r['final_transport_counters']['write_bytes'],True)
            record['root']=receipt['quarantine_root'];record['files']=receipt['output_inventory']['files']
            record['result']=self.read_json(child(record['root'],'RESULT.json'),record['files']['RESULT.json'])
            return record
        except BaseException:
            if not any(s['phase_id']==phase_id for s in self.seen):
                self.custody_known=False
                self.seen.append({'slot':slot,'phase_id':phase_id,'status':'unknown','resources_closed':False,'receipt_pin':None})
            raise

    def native_payload(self,branch=None):
        return {'schema':'paper_i_worker_native_v1','matlab':self.op['native_matlab'],'originals':self.op['originals']['files'],'limits':self.op['native_limits'] if branch is None else None,'branch':branch,'initial_seed':None if branch is None else self.op['native_seeds'][branch]}

    def original_mount(self):
        return {'path':self.op['originals']['root'],'kind':'directory','purpose':'input','files':{n:pin(d) for n,d in self.op['originals']['files'].items()}}

    def prepare(self):
        r=self.phase('prepare_originals','operator',self.native_payload(),planner.slot('prepare_originals'),{'/native':mount(self.native,'operator_reference'),'/originals':self.original_mount()})
        names={n:d for n,d in r['files'].items() if n.startswith('native/')}
        need('native/PREPARED.json' in names,'Complete released-source preparation')
        self.prepared=self.view(self.record_members(r,'native/'))
        cert=self.read_json(self.op['lineage']['path'],pin(self.op['lineage']));review=self.read_json(self.op['lineage_review']['path'],pin(self.op['lineage_review']))
        for e in self.op['lineage_evidence']:self.budget.read_file(e['path'],pin(e),self.op['host']['max_metadata_bytes'])
        payload={'schema':'paper_i_worker_support_v1','prepared_path':'PREPARED.json','prepared_pin':self.prepared['files']['PREPARED.json'],'certificate':cert,'certificate_pin':pin(self.op['lineage']),'review':review,'review_pin':pin(self.op['lineage_review']),'evidence_pins':[pin(e) for e in self.op['lineage_evidence']],'max_queries':self.op['host']['max_queries'],'max_units':self.op['host']['max_phases']}
        s=self.phase('prepare_views','operator',payload,planner.slot('prepare_support'),{'/prepared':mount(self.prepared,'input')})
        self.support=self.read_json(child(s['root'],'SUPPORT.json'),s['files']['SUPPORT.json'])
        configurations={r:({p:planner.reference_configurations(p) for p in PROFILES} if r=='reference' else self.op['programs'][r]['configurations']) for r in ROLES}
        self.plan=planner.build_plan(self.support['units'],configurations)
        pp=self.save(self.root/'PLAN.json',self.plan);self.event({'event':'plan_admitted','plan':{'path':'PLAN.json',**pp}})
        self.acquisitions={a['key']:a for a in self.support['acquisitions']}

    def job_slot(self,stage,unit=None,**kwargs):
        j=self.current_job
        return planner.slot(stage,job_id=j['job_id'],producer_role=j['role'],profile=j.get('profile'),branch=j.get('branch'),unit_id=None if unit is None else unit['unit_id'],**kwargs)

    def prepare_view(self,unit,part,inner=None):
        job=self.current_job;acq=copy.deepcopy(self.acquisitions[unit['source_key']]);meta=acq.pop('private_unit_metadata')[unit['modality']]
        rows=part['train'];mapping=None;provenance=None
        if job['profile']=='CM-shuffled':
            # One private seed across arms/modalities. Worker derives independent
            # source-context/observed-modality stratum seeds, preserving paired
            # maps even when an acquisition has structural unpaired support.
            key=(meta['acquisition'],job['fold'],inner)
            physical=[meta['trials'][i] for i in rows]
            if key not in self.shuffle_cache:
                self.shuffle_cache[key]={'seed':secrets.randbits(63)}
            item=self.shuffle_cache[key]
            # Delivered outcome is the only row-varying discrete context. It is
            # read privately by a separate view operation, never inferred from Y.
            mapping={'physical_trials':physical,'seed':item['seed']}
            provenance={'kind':'whole_training_trajectory_reassignment','receipt_sha256':identity({'acquisition':meta['acquisition'],'fold':job['fold'],'inner':inner,'physical':sorted(physical),'seed':item['seed']})}
        payload={'schema':'paper_i_worker_views_v1','acquisition':acq,'modality':unit['modality'],'profile':job['profile'],'train_rows':rows,'held_rows':part['validation'] if inner is not None else part['query'],'cell_tokens':unit['cell_tokens'],'cell_indices':None,'categorical_vocabulary':None if job['profile']=='M' else meta['categorical_vocabulary'],'permutation':mapping,'label_provenance':provenance,'transport_seed':secrets.randbits(63),'namespace':secrets.token_hex(16)}
        result=self.phase('prepare_views','operator',payload,self.job_slot('prepare_inner' if inner is not None else 'prepare_final',unit,inner_fold=inner),{'/prepared':mount(self.prepared,'input')})
        result['index']=self.read_json(child(result['root'],'private/INDEX.json'),result['files']['private/INDEX.json'])
        result['train']=self.read_json(child(result['root'],'public/TRAIN.json'),result['files']['public/TRAIN.json']);access.public_training(result['train'])
        result['provenance']=provenance;return result

    def fit(self,unit,view,configuration,indices,inner=None):
        job=self.current_job;cells=[unit['cell_tokens'][i] for i in indices]
        members=self.record_members(view,'public/',names={'public/TRAIN.json','public/Y.npy','public/weights.npy'})
        need(set(members)=={'TRAIN.json','Y.npy','weights.npy'},'Training-only full population payload')
        if job['role']=='reference':payload={'schema':'paper_i_worker_fit_v1','train_path':'/input/TRAIN.json','train_pin':view['files']['public/TRAIN.json'],'configuration':configuration,'selected_cell_indices':indices,'label_provenance':view['provenance']}
        else:payload={'schema':'paper_i_candidate_fit_v1','train_path':'TRAIN.json','train_pin':view['files']['public/TRAIN.json'],'configuration':configuration,'selected_cell_indices':indices,'selected_cell_tokens':cells,'namespace':view['train']['namespace']}
        r=self.phase('fit',job['role'],payload,self.job_slot('inner_fit' if inner is not None else 'final_fit',unit,inner_fold=inner,configuration_id=configuration['id']),input_members=members)
        need('MODEL.json' in r['files'],'Complete sealed typed model')
        model=self.read_json(child(r['root'],'MODEL.json'),r['files']['MODEL.json'])
        need(model['schema']=='paper_i_primitive_model_v1' and model['profile']==job['profile'] and model['cell_tokens']==cells,'Exact selected model output-cell axis')
        names={'MODEL.json'}|{d['path'] for d in model['arrays'].values()}
        need(all(n in r['files'] for n in names) and all(pin(d)==r['files'][d['path']] for d in model['arrays'].values()),'Complete pinned primitive state')
        return {'record':r,'model':model,'members':self.record_members(r,names=names),'indices':indices,'cells':cells}

    def bundle(self,unit,models):
        role=self.current_job['role'];groups=[];members={}
        for i,m in enumerate(models):
            prefix='group'+str(i)+'/'
            for n,item in m['members'].items():members[prefix+n]=item
            groups.append({'model_path':prefix+'MODEL.json','model_pin':m['record']['files']['MODEL.json'],'cell_tokens':m['cells'],'output_indices':m['indices']})
        value={'schema':'paper_i_reference_bundle_v1' if role=='reference' else 'paper_i_candidate_bundle_v1','profile':self.current_job['profile'],'cell_tokens':unit['cell_tokens'],'groups':groups}
        view=self.json_view('BUNDLE.json',value,members);return view

    def query(self,unit,view,bundle,inner=None,configuration=None):
        result=[];queries=list(view['index']['queries']);random.SystemRandom().shuffle(queries)
        for q in queries:
            query=self.read_json(child(view['root'],q['path']),q['pin'])
            if self.current_job['role']=='reference':
                payload={'schema':'paper_i_worker_query_v1','bundle_path':'/models/BUNDLE.json','bundle_pin':bundle['files']['BUNDLE.json'],'query_path':'/input/QUERY.json','query_pin':q['pin']}
                members={'QUERY.json':{'path':str(child(view['root'],q['path'])),'pin':q['pin']}}
            else:
                payload={'schema':'paper_i_candidate_query_v1','profile':query['profile'],'record':query['record'],'cell_tokens':query['cell_tokens'],'bundle_path':'BUNDLE.json','bundle_pin':bundle['files']['BUNDLE.json'],'namespace':query['namespace']};members=None
            slot=self.job_slot('inner_query' if inner is not None else 'outer_query',unit,inner_fold=inner,configuration_id=None if configuration is None else configuration['id'],row=q['source_row'],time_index=q['time_index'])
            r=self.phase('query',self.current_job['role'],payload,slot,{'/models':mount(bundle,'input')},members)
            d=r['result']['prediction'];need(r['result']['profile']==query['profile'] and r['result']['cell_tokens']==unit['cell_tokens'] and r['files'].get(d['path'])==pin(d) and d['shape']==[len(unit['cell_tokens'])],'Complete one-record full-cell vector')
            result.append({'query':q,'record':r,'prediction':d})
        return result

    def admit_model(self,unit,model,configuration,inner=None):
        view=self.view(model['members'])
        payload={'schema':'paper_i_worker_admit_v1','model_kind':'reference' if self.current_job['role']=='reference' else 'candidate','model_path':'/models/MODEL.json','model_pin':view['files']['MODEL.json'],'profile':self.current_job['profile'],'cell_tokens':model['cells']}
        return self.phase('selection_evaluate','operator',payload,self.job_slot('inner_admit' if inner is not None else 'final_admit',unit,inner_fold=inner,configuration_id=configuration['id']),{'/models':mount(view,'input')})

    def errors(self,unit,view,predictions,configuration,inner):
        truth=view['index']['truth'];members={'TRUTH.npy':{'path':str(child(view['root'],'private/'+truth['path'])),'pin':pin(truth)}}
        descriptors=[];truth_rows=[]
        for i,row in enumerate(predictions):
            name='prediction'+str(i)+'.npy';d=row['prediction'];members[name]={'path':str(child(row['record']['root'],d['path'])),'pin':pin(d)}
            descriptors.append({**d,'path':name});truth_rows.append(row['query']['truth_index'])
        payload={'schema':'paper_i_worker_errors_v1','cell_tokens':unit['cell_tokens'],'truths':{**truth,'path':'TRUTH.npy'},'truth_rows':truth_rows,'predictions':descriptors}
        return self.phase('selection_evaluate','operator',payload,self.job_slot('inner_error',unit,inner_fold=inner,configuration_id=configuration['id']),input_members=members)

    def encode_unit(self,unit):
        job=self.current_job;outer=next(x for x in unit['outer'] if x['fold']==job['fold']);configs=self.plan['configurations'][job['role']][job['profile']]
        errors=[];members={};fit_calls=0;cell_fits=0;svd_calls=0
        fold_tokens={g['fold']:secrets.token_hex(16) for g in outer['inner']}
        for inner in outer['inner']:
            f=inner['fold'];view=self.prepare_view(unit,inner,f)
            for cfg in configs:
                model=self.fit(unit,view,cfg,list(range(len(unit['cell_tokens']))),f);fit_calls+=1;cell_fits+=len(unit['cell_tokens'])
                if job['role']=='reference':svd_calls+=model['record']['result']['svd_factorizations']
                self.admit_model(unit,model,cfg,f)
                bundle=self.bundle(unit,[model]);predictions=self.query(unit,view,bundle,f,cfg)
                err=self.errors(unit,view,predictions,cfg,f);d=err['result']['squared_error_sum'];name='sse'+str(len(errors))+'.npy'
                members[name]={'path':str(child(err['root'],d['path'])),'pin':pin(d)}
                errors.append({'configuration_id':cfg['id'],'fold_token':fold_tokens[f],'squared_error_sum':{**d,'path':name},'count':err['result']['count']})
        payload={'schema':'paper_i_worker_selection_v1','profile':job['profile'],'cell_tokens':unit['cell_tokens'],'configurations':configs,'fold_tokens':list(fold_tokens.values()),'errors':errors,'fit_accounting':{'logical_cell_fits':cell_fits if job['role']=='reference' else None,'fit_calls':fit_calls,'svd_factorizations':svd_calls if job['role']=='reference' else None}}
        selected=self.phase('selection_evaluate','operator',payload,self.job_slot('selection',unit),input_members=members)
        groups=selected['result']['groups'];selection={'job_id':job['job_id'],'unit_id':unit['unit_id'],'groups':groups,'selection_pin':selected['files']['RESULT.json']}
        planner.validate_selection(self.plan,selection);self.selections.append(selection)
        self.event({'event':'selection_admitted','job_id':job['job_id'],'unit_id':unit['unit_id'],'selection':{'path':str(Path(selected['root']).relative_to(self.root)/'RESULT.json'),**selected['files']['RESULT.json']},'groups':groups})
        final=self.prepare_view(unit,outer);models=[]
        for group in groups:
            model=self.fit(unit,final,group['configuration'],group['cell_indices']);self.admit_model(unit,model,group['configuration']);models.append(model)
        bundle=self.bundle(unit,models);predictions=self.query(unit,final,bundle)
        return {'unit':unit,'view':final,'predictions':predictions,'selection':selection,'models':models,'scheduled_inner_fit_processes':fit_calls,'scheduled_output_cell_fits':cell_fits+len(unit['cell_tokens']),'arbitrary_candidate_internal_operations_observed':False}

    def execute_job(self,job):
        self.current_job=job;self.event({'event':'high_level_start','job_id':job['job_id'],'job':job})
        limit=self.op['attempt_limits'][job['kind']];deadline=min(self.work_deadline,self.budget.tick()+limit['wall_seconds'])
        self.budget.begin_attempt(limit['read_bytes'],limit['write_bytes'],deadline);self.attempt_memory=limit['memory_bytes']
        failure=None;outputs=[]
        try:
            if job['kind']=='encoding':
                outputs=[self.encode_unit(u) for u in self.plan['units']]
                self.encoding_outputs[job['job_id']]=outputs
            else:
                need(self.encoding_sealed,'Full encoding closure before every raw native exposure')
                branch=job['branch']
                if job['role']=='reference':
                    payload=self.native_payload(branch);extra={'/originals':self.original_mount(),'/native':mount(self.native,'operator_reference')}
                else:
                    payload={'schema':'paper_i_candidate_reconstruction_v1','branch':branch,'native_seed':self.op['native_seeds'][branch],'required_roots':BRANCHES[branch]['targets'],'input_manifest':self.op['originals']['files'],'output_format':'filio_native_numeric_v1','namespace':secrets.token_hex(16)}
                    extra={'/originals':self.original_mount()}
                r=self.phase('reconstruct',job['role'],payload,self.job_slot('reconstruct'),extra)
                name='native/NATIVE.json' if job['role']=='reference' else 'NATIVE.json'
                need(name in r['files'],'Complete native numeric JSON export')
                self.native_outputs[job['job_id']]={'record':r,'name':name};outputs=[{'native_pin':r['files'][name]}]
        except Exception as exc:failure={'type':type(exc).__name__,'message':str(exc)[:1000]}
        finally:
            # An expired attempt never refreshes the global clock. The failure
            # disposition may be written only after clearing the sub-cap, inside
            # the same original controller/global allocation.
            self.budget.attempt=None;self.attempt_memory=None
        status='complete' if failure is None else 'failed' if self.custody_known else 'unknown'
        self.job_results[job['job_id']]={'job':job,'status':status,'reason':failure,'artifact_pins':[p['receipt_pin'] for p in self.phases if p['slot']['job_id']==job['job_id']]}
        self.event({'event':'high_level_disposition','job_id':job['job_id'],'status':status,'reason':failure,'artifact_pins':self.job_results[job['job_id']]['artifact_pins']})
        self.current_job=None
        need(self.custody_known,'Unknown custody delegates independent parent recovery')

    def grade_encoding(self,role,profile):
        selected=[j for j in high_level_jobs() if j['kind']=='encoding' and j['role']==role and j['profile']==profile]
        need(all(self.job_results.get(j['job_id'],{}).get('status')=='complete' for j in selected),'Whole fivefold profile required for grading')
        support=[];truths={};predictions={};means={};members={};view_groups={k:[] for k in ('Water','1-s DA','DA-first','2-s DA')}
        for job in selected:
            for item in self.encoding_outputs[job['job_id']]:
                unit=item['unit'];view=item['view'];a=self.acquisitions[unit['source_key']];meta=a['private_unit_metadata'][unit['modality']]
                prefix=secrets.token_hex(16);td=view['index']['truth'];md=view['index']['training_mean']
                tn=prefix+'_truth.npy';mn=prefix+'_mean.npy'
                members[tn]={'path':str(child(view['root'],'private/'+td['path'])),'pin':pin(td)};members[mn]={'path':str(child(view['root'],'private/'+md['path'])),'pin':pin(md)}
                for result in item['predictions']:
                    q=result['query'];token=q['token'];d=result['prediction'];pn=token+'.npy'
                    need(token not in truths,'Unique query token across complete fivefold output')
                    members[pn]={'path':str(child(result['record']['root'],d['path'])),'pin':pin(d)}
                    truths[token]={'array':{**td,'path':tn},'row':q['truth_index']};predictions[token]={**d,'path':pn};means[token]={**md,'path':mn}
                    for label in meta['trial_views'][str(q['source_row'])]:view_groups[label].append(token)
                    support.append({'stratum':{k:q['categories'][k] for k in ('reinforcer','planned_delay','delivered_outcome')},'token':token,'modality':unit['modality'],'acquisition':meta['acquisition'],'session':meta['session'],'animal':meta['animal'],'physical_trial':meta['trials'][q['source_row']],'time_index':q['time_index'],'time_count':unit['time_count'],'cell_tokens':unit['cell_tokens'],'fold':job['fold']})
        payload={'schema':'paper_i_worker_final_v1','support':support,'truths':truths,'predictions':predictions,'training_means':means,'view_groups':view_groups}
        r=self.phase('final_evaluate','operator',payload,planner.slot('grade_encoding',producer_role=role,profile=profile),input_members=members)
        self.grades.append({'kind':'encoding','role':role,'profile':profile,'record':r});return r

    def grade_native(self,branch):
        payload={'schema':'paper_i_worker_native_grade_v1','branch':branch};members={}
        for role in ROLES:
            job=next(j for j in high_level_jobs() if j['kind']=='reconstruction' and j['role']==role and j['branch']==branch)
            need(self.job_results.get(job['job_id'],{}).get('status')=='complete','All three native branch producers required')
            item=self.native_outputs[job['job_id']];r=item['record'];name=role+'.json';d=r['files'][item['name']]
            members[name]={'path':str(child(r['root'],item['name'])),'pin':d};payload[role]={'path':name,'pin':d}
        r=self.phase('final_evaluate','operator',payload,planner.slot('grade_native',branch=branch),input_members=members)
        self.grades.append({'kind':'native','branch':branch,'record':r});return r

    def run(self):
        failure=None
        try:
            self.precommit();self.prepare()
            need(self.plan['counts']['maximum_phase_slots']<=self.op['host']['max_phases'] and self.plan['counts']['total_vector_query_process_phases']<=self.op['host']['max_queries'],'Full expanded parametric workload fits prospective operation ceiling')
            for job in high_level_jobs():
                if job['kind']=='encoding':self.execute_job(job)
            encoding_jobs=[j for j in high_level_jobs() if j['kind']=='encoding']
            need(all(j['job_id'] in self.job_results for j in encoding_jobs) and self.custody_known,'All sixty encoding attempts terminal before raw native exposure')
            seal={'schema':'paper_i_encoding_irreversible_seal_v1','jobs':{j['job_id']:self.job_results[j['job_id']] for j in encoding_jobs},'closed_phases':[p['receipt_pin'] for p in self.phases],'no_more_encoding_dispatch':True}
            self.save(self.root/'ENCODING_SEAL.json',seal);self.encoding_sealed=True
            for job in high_level_jobs():
                if job['kind']=='reconstruction':self.execute_job(job)
            for role in ROLES:
                for profile in PROFILES:
                    try:self.grade_encoding(role,profile)
                    except Exception as exc:
                        self.event({'event':'grade_unavailable','role':role,'profile':profile,'reason':str(exc)[:1000]})
                        need(self.custody_known,'Unresolved grader custody')
            for branch in BRANCHES:
                try:self.grade_native(branch)
                except Exception as exc:
                    self.event({'event':'grade_unavailable','branch':branch,'reason':str(exc)[:1000]})
                    need(self.custody_known,'Unresolved grader custody')
            members={};results=[]
            for i,g in enumerate(self.grades):
                r=g['record'];name=str(i)+'.json';d=r['files']['RESULT.json'];members[name]={'path':str(child(r['root'],'RESULT.json')),'pin':d};results.append({'path':'/input/'+name,'pin':d})
            from comparisons import comparisons
            paired=comparisons([{'role':g['role'],'profile':g['profile'],'metrics':g['record']['result']['metrics']} for g in self.grades if g['kind']=='encoding'])
            status={'paired_comparisons':paired,'jobs':self.job_results,'source':pin(self.op['source_manifest']),'complete_required_grades':len(self.grades)==21,'native_equal_branch_fraction':{role:(sum(g['record']['result']['arms'][role]['fraction'] for g in self.grades if g['kind']=='native')/9 if sum(g['kind']=='native' for g in self.grades)==9 else None) for role in ('A','B')},'reference_scheduled_logical_fits':self.plan['counts']['reference_total_cell_fits'],'candidate_internal_fit_counts_observed':False,'actual_queries_completed':sum(p['slot']['stage'] in ('inner_query','outer_query') for p in self.phases),'actual_native_memory_IO_unknown':True,'released_processed_target_estimand':True,'upstream_processing':self.support['processing']}
            report=self.phase('report','operator',{'schema':'paper_i_worker_report_v1','closed_results':results,'status':status},planner.slot('report'),input_members=members)
            self.save(self.root/'report.json',report['result'])
        except Exception as exc:failure={'type':type(exc).__name__,'message':str(exc)[:2000]}
        for j in high_level_jobs():
            if j['job_id'] not in self.job_results:
                self.job_results[j['job_id']]={'job':j,'status':'not_started','reason':failure,'artifact_pins':[]}
        coverage=None if self.plan is None else planner.summarize_missing(self.plan,self.seen,self.selections)
        result={'schema':'paper_i_controller_result_v1','complete':failure is None and all(x['status']=='complete' for x in self.job_results.values()) and coverage is not None and coverage['complete'],'failure':failure,'jobs':self.job_results,'nested_coverage':coverage,'custody_known':self.custody_known,'budget':self.budget.snapshot(),'runtime_qualified_by_external_gate_only':True,'scientific_qualification':False,'outer_natural_exit_and_terminal_absence_required':True}
        return self.save(self.root/'CONTROLLER_RESULT.json',result)


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--operation',required=True);p.add_argument('--operation-pin',required=True);p.add_argument('--output',required=True)
    p.add_argument('--origin',type=float,required=True);p.add_argument('--global-deadline',type=float,required=True);p.add_argument('--work-deadline',type=float,required=True);a=p.parse_args(argv)
    descriptor=strict(a.operation_pin.encode());body=capture(a.operation,1048576,descriptor);op=strict(body)
    operation=Operations(op,a.output,a.origin,a.global_deadline,a.work_deadline,Path(__file__).resolve().parent)
    operation.budget.read(len(body));operation.budget.file_reads+=len(body)
    operation.run()


if __name__=='__main__':main()
