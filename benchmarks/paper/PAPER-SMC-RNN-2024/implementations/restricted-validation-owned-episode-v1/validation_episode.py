"""One restricted VALID reference phase on the retained protected owner.

Only the overlay custody command may admit the captured prediction after the
unchanged parent/aggregate closure gate. No target or numerical grading occurs.
"""
from pathlib import Path
import importlib
import os
import sys

sys.path.insert(0,str(Path(__file__).absolute().parent))
from validation_core import (need,path,body,read,pin,encode,decode,descriptor,checked,
    ref,write_new,load_module,source_identity,load_inputs,owner_mounts)

ROUTE='smc_validation_owned_reference_v1'
PHASE='validation_reference'
OUTCOME='restricted_validation_reference'
ACCESS='paper_data_author_code_and_weights'
TRANSPORT_PIN={'bytes':997,'sha256':'bdeaf4d661115f8f605c572c6da4faaa088370cb1ab714c41f563767bff5fc9c'}
TRANSPORT_FILES={'__init__.py','engine.py','bounds.py','contract.py','archive.py','holder.py','provider.py'}
TRANSPORT_MODULE='_smc_validation_owned_transport'
EPISODE_REL=Path('benchmarks/paper/PAPER-SMC-RNN-2024/implementations/aggregate-episode-v1')


def create_episode(repository_root,component_root):
    root=path(component_root);initial=load_inputs(root)
    base=load_module('_smc_validation_fixed_full_panel_facade',initial['binding']['facade']['path'],
                     {k:initial['binding']['facade'][k] for k in ('bytes','sha256')})

    class ValidationEpisode(base.FullPanelEpisode):
        ROUTE=ROUTE
        CONDITIONS=(PHASE,)
        KEYS={OUTCOME:['offline']}
        CLOSED_SCHEMA='smc_validation_unadmitted_closed_phase_v1'
        ENGINE_MODULE=TRANSPORT_MODULE+'.engine'
        # This exactly matches the retained Provider's release executable.
        COMMAND=['/usr/local/bin/python','-I','-S','-B','/runner/worker.py']

        def __init__(self):
            self.repository_root,self.HERE=path(repository_root),root
            self.data=load_inputs(root)
            self.profile=dict(self.data['binding']['profile'])
            self.PROFILES={OUTCOME:self.profile}
            retained_root=self.repository_root/EPISODE_REL
            base._read_source(retained_root/'SOURCE.json',base.EPISODE_SOURCE_PIN)
            self.retained=base._module('_smc_validation_retained_episode',retained_root/'episode.py',base.EPISODE_PIN)
            self.retained.source_identity()
            for name in ('need','path','body','read','publish','relative','descriptor','checked','encoded',
                         'request_bytes','pin','decode','file_mount','mount_identity','validate_closed','observe_closed'):
                setattr(self,name,getattr(self.retained,name))
            self.TRANSPORT=path(self.data['binding']['transport_source']['path']).parent
            self.TRANSPORT_SHA=TRANSPORT_PIN['sha256']
            self._provider=None
            self.TASK_SHA=pin(body(root/'VALIDATION_TASK.json'))['sha256']
            self.PAIR_CAP=sum(row['bytes'] for row in self.data['materials']['files'].values())+1024**2
            self._protocol=self._protocol_path=None
            self._captured_actual={}
            self._compatibility=ValidationBenchmark(self)
            self.source_identity()

        def source_identity(self):
            return source_identity(self.HERE)

        def implementation_identity(self):
            manifest=read(self.HERE/'SOURCE.json')
            return pin(encode({'schema':'smc_validation_owned_implementation_v1','route':ROUTE,
                'files':{k:v for k,v in manifest['files'].items() if k!='DEPLOYMENT_BINDING.json'},
                'transport':TRANSPORT_PIN}))

        @property
        def PAIR_SHA(self):
            return self.data['binding']['prepared_reference']['sha256']

        def benchmark(self):
            return self._compatibility

        def material_binding(self):
            return self.data['binding']['prepared_reference']

        def public_context(self,pair_path,task_path):
            current=load_inputs(self.HERE)
            need(path(pair_path)==path(current['binding']['prepared_reference']['path'])
                 and pin(body(pair_path))=={k:current['binding']['prepared_reference'][k] for k in ('bytes','sha256')}
                 and path(task_path)==self.HERE/'VALIDATION_TASK.json'
                 and pin(body(task_path))['sha256']==self.TASK_SHA,'Exact VALID preparation and task')
            task=read(task_path)
            need(task=={'schema':'smc_validation_owned_task_v1','route':ROUTE,'outcome':OUTCOME,
                'phase_id':PHASE,'role':'B','profile':self.profile,
                'packet_sha256':current['job']['packet_sha256'],
                'declaration_sha256':current['prepared']['declaration']['sha256'],
                'checkpoint_training_cohort':'unknown','resource_adequacy':False},
                'Exact VALID task/profile without a readiness claim')
            self.data=current
            return current['prepared'],{'capsule':current['materials']}

        def instantiate(self,runtime_path,runtime_sha,output):
            self.public_context(self.data['binding']['prepared_reference']['path'],self.HERE/'VALIDATION_TASK.json')
            runtime_raw=body(runtime_path);need(pin(runtime_raw)['sha256']==runtime_sha,'Exact selected runtime')
            runtime=self.runtime_config(decode(runtime_raw))
            output=path(output)
            protected=(self.HERE,self.data['component'],self.data['material_root'],path(self.data['binding']['prepared_reference']['path']).parent)
            need(not os.path.lexists(output) and output.parent.is_dir()
                 and not any(output.is_relative_to(p) or p.is_relative_to(output) for p in protected),'Fresh disjoint protocol')
            output.mkdir(mode=0o700);folder=output/PHASE;folder.mkdir(mode=0o700)
            programme=body(self.data['component']/'validation_adapter.py',self.data['manifest']['files']['validation_adapter.py'])
            declaration=checked(self.data['prepared']['declaration'])
            pp=write_new(folder/'program.py',programme,0o444);dp=write_new(folder/'declaration.json',declaration,0o444)
            protocol={'schema':'smc_validation_owned_protocol_v1','route':ROUTE,'outcome':OUTCOME,
                'pair_path':self.data['binding']['prepared_reference']['path'],'pair_sha256':self.PAIR_SHA,
                'task_path':str(self.HERE/'VALIDATION_TASK.json'),'task_sha256':self.TASK_SHA,
                'source':self.source_identity(),'resource_profile':self.profile,
                'programs':{PHASE:{'program':pp,'declaration':dp,'method':{'path':str(folder/'declaration.json'),**dp}}},
                'runtime':write_new(output/'runtime.json',runtime_raw),
                'deployment_binding_pin':runtime['deployment']['binding_pin'],
                'all_programmes_and_declarations_frozen_before_first_phase':True,
                'AI_attempt':False,'scientific_improvement':False,'execution_authorized_by_construction':False}
            write_new(output/'PROTOCOL.json',encode(protocol));return ref(output/'PROTOCOL.json')

        def admit_protocol(self,protocol_path,expected):
            protocol_path=path(protocol_path)
            if self._protocol_path!=protocol_path:self._captured_actual.clear()
            self._protocol=self._protocol_path=None
            raw=body(protocol_path);need(pin(raw)['sha256']==expected,'Exact selected VALID protocol')
            value=decode(raw)
            fields={'schema','route','outcome','pair_path','pair_sha256','task_path','task_sha256','source',
                'resource_profile','programs','runtime','deployment_binding_pin',
                'all_programmes_and_declarations_frozen_before_first_phase','AI_attempt',
                'scientific_improvement','execution_authorized_by_construction'}
            need(set(value)==fields and value['schema']=='smc_validation_owned_protocol_v1'
                 and value['route']==ROUTE and value['outcome']==OUTCOME and value['source']==self.source_identity()
                 and encode(value['resource_profile'])==encode(self.profile) and value['pair_sha256']==self.PAIR_SHA
                 and value['task_sha256']==self.TASK_SHA and set(value['programs'])=={PHASE}
                 and value['all_programmes_and_declarations_frozen_before_first_phase'] is True
                 and value['AI_attempt'] is False and value['scientific_improvement'] is False
                 and value['execution_authorized_by_construction'] is False,'Exact single-phase VALID protocol')
            self.public_context(value['pair_path'],value['task_path'])
            row=value['programs'][PHASE];folder=protocol_path.parent/PHASE
            need(set(row)=={'program','declaration','method'}
                 and body(folder/'program.py',row['program'])==body(self.data['component']/'validation_adapter.py',self.data['manifest']['files']['validation_adapter.py'])
                 and body(folder/'declaration.json',row['declaration'])==checked(self.data['prepared']['declaration'])
                 and row['method']=={'path':str(folder/'declaration.json'),**row['declaration']},
                 'Original VALID programme and method bytes remain frozen')
            runtime=self.runtime_config(decode(body(protocol_path.parent/'runtime.json',value['runtime'])))
            need(value['deployment_binding_pin']==runtime['deployment']['binding_pin'],'Original selected deployment join')
            self._protocol,self._protocol_path=value,protocol_path
            return value,runtime

        def resources(self,outcome,runtime):
            need(outcome==OUTCOME,'VALID reference only')
            result=super().resources(outcome,runtime)
            # The retained parent supports a phase tuple; this route has one phase.
            result['source_read_bytes']=runtime['source_read_bytes']
            result['host_write_bytes']=runtime['host_write_bytes']
            return result

        def provider_class(self):
            selected=self.data['binding']['transport_source']
            need({k:selected[k] for k in ('bytes','sha256')}==TRANSPORT_PIN,'Exact VALID-only transport derivative')
            manifest=decode(checked(selected))
            need(set(manifest)=={'schema','files'} and manifest['schema']=='smc_aggregate_transport_source_manifest_v1'
                 and set(manifest['files'])==TRANSPORT_FILES,'Exact derived transport closure')
            for name,expected in manifest['files'].items():body(self.TRANSPORT/name,expected)
            if self._provider is None:
                self.retained.load_file(TRANSPORT_MODULE,self.TRANSPORT/'__init__.py',manifest['files']['__init__.py']['sha256'],True)
                self._provider=importlib.import_module(TRANSPORT_MODULE+'.provider').Provider
            return self._provider

        def job_for(self,protocol,phase):
            need(protocol==self._protocol and phase==PHASE,'Admitted sole VALID phase')
            job=dict(self.data['job']);job['source']=protocol['source']
            return job

        def mounts_for(self,protocol_path,protocol,phase,job_path,job_pin,manifests):
            need(protocol==self._protocol and phase==PHASE,'Admitted VALID phase before material exposure')
            worker={'path':str(self.repository_root/EPISODE_REL/'worker.py'),
                'bytes':11424,'sha256':'2fc10bb2b608e7f1e4a803588cff1123add5aa7c6fbb92eb6b22cea028a9b473'}
            rows=owner_mounts(self.data,path(protocol_path).parent/PHASE/'program.py',
                path(protocol_path).parent/PHASE/'declaration.json',job_path,job_pin,
                retained_worker_descriptor=worker,component_source=self.source_identity())
            need(not any(row['destination'] in ('/request.json','/output','/work') for row in rows),
                 'Provider exclusively creates actual request/output/scratch mounts')
            return {row['destination']:self.file_mount(row['source'],{k:row[k] for k in ('bytes','sha256')},row['purpose']) for row in rows}

        def captured_predictions(self,receipt,phase,outcome,programme):
            need(phase==PHASE and outcome==OUTCOME and self._protocol is not None,'Selected VALID capture')
            files=receipt['output_inventory']['files']
            need(receipt['output_inventory']['complete'] is True
                 and set(files)=={'offline.h5','actual_declaration.json','RESULT.json','OUTPUTS.json'},'Complete bounded worker output')
            root=path(receipt['quarantine_root']);result=decode(body(root/'RESULT.json',files['RESULT.json']))
            expected={'schema':'smc_restricted_validation_program_result_v1','route':'smc_restricted_validation_v1',
                'phase_id':PHASE,'access_condition':ACCESS,'outcome':OUTCOME,
                'program_sha256':programme['program']['sha256'],'declaration_sha256':programme['declaration']['sha256'],
                'method_freeze_sha256':programme['method']['sha256'],
                'author_reference_resource_profile':self.profile,'submission_keys':['offline']}
            need(encode(result)==encode(expected),'Captured worker result joins exact source method/profile')
            actual=decode(body(root/'actual_declaration.json',files['actual_declaration.json']))
            need(actual['schema']=='smc_restricted_validation_actual_v1' and actual['phase_id']==PHASE
                 and actual['phase']=='val' and actual['packet_sha256']==self.data['job']['packet_sha256']
                 and actual['method_freeze_sha256']==programme['method']['sha256']
                 and encode(actual['recipe'])==encode(self.data['core'].recipe())
                 and encode(actual['author_reference_resource_profile'])==encode(self.profile)
                 and actual['AI_attempt'] is False and actual['scientific_improvement'] is False,
                 'Actual VALID use has no fabricated scientific success')
            self._captured_actual[PHASE]={'prediction':{'path':str(root/'offline.h5'),**files['offline.h5']},
                'actual':{'path':str(root/'actual_declaration.json'),**files['actual_declaration.json']}}
            return {'offline':root/'offline.h5'}

        def _grade_from_owned_pair(self,*args,**kwargs):
            need(False,'This owner admits inference custody only; use the separately bounded VALID grade owner')

        def admit_closed_prediction(self,folder,result,invocation,output):
            """Subordinate to derived runner.custody's complete saved-parent gate."""
            folder=path(folder)
            need(read(folder/'RESULT.json')==result and read(folder/'INVOCATION.json',result['invocation_pin'])==invocation
                 and result['status']=='closed_pair' and invocation['legacy_source']==self.source_identity(),
                 'Exact saved owner operands after retained custody gate')
            protocol,_=self.admit_protocol(invocation['protocol_path'],invocation['protocol_pin']['sha256'])
            pair=read(Path(invocation['output'])/'PAIR_CLOSED.json',result['pair_closed_pin'])
            need(pair['schema']==self.CLOSED_SCHEMA and pair['route']==ROUTE
                 and set(pair['conditions'])=={PHASE} and pair['owner_source']==result['source']
                 and pair['owner_invocation_pin']==result['invocation_pin'] and pair['private_target_accessed'] is False,
                 'Unadmitted captured phase joined to complete owner')
            row=pair['conditions'][PHASE];capture=read(row['freeze_path'],row['freeze'])
            need(capture['schema']=='smc_validation_unadmitted_capture_v1'
                 and capture['custody_admitted'] is False and capture['phase_id']==PHASE
                 and capture['component_source']==self.source_identity()
                 and capture['packet_sha256']==self.data['job']['packet_sha256']
                 and capture['method']==protocol['programs'][PHASE]['method'],
                 'Only original unadmitted capture becomes a freeze after aggregate closure')
            receipt=read(row['receipt_path'],row['receipt'])
            expected_prediction={'path':str(path(receipt['quarantine_root'])/'offline.h5'),**receipt['output_inventory']['files']['offline.h5']}
            need(capture['prediction']==expected_prediction,'Prediction remains the exact owned quarantine output')
            output=path(output)
            roots=(folder,path(invocation['output']),self.HERE,self.data['material_root'],self._protocol_path.parent)
            need(not os.path.lexists(output) and output.parent.is_dir()
                 and not any(output.is_relative_to(p) or p.is_relative_to(output) for p in roots),'Fresh disjoint custody output')
            write_new(folder/'VALIDATION_CUSTODY_STARTED.json',encode({'result':pin(body(folder/'RESULT.json')),
                'invocation':result['invocation_pin'],'output':str(output)}))
            output.mkdir(mode=0o700)
            gm=decode(checked(self.data['binding']['grade_source']));gr=path(self.data['binding']['grade_source']['path']).parent
            for name,expected in gm['files'].items():body(gr/name,expected)
            grader=load_module('_smc_validation_custody_freezer',gr/'validation_grade.py',gm['files']['validation_grade.py'])
            packet={'path':str(self.data['material_root']/'inputs/PACKET.json'),**self.data['materials']['packet']}
            panel={'path':str(gr/'VALID_PANEL.json'),**gm['files']['VALID_PANEL.json']}
            freeze=grader.freeze_prediction(capture['prediction']['path'],panel,packet,capture['method'],output/'prediction',role='reference')
            frozen=decode(checked(freeze))
            need({k:frozen['snapshot'][k] for k in ('bytes','sha256')}=={k:capture['prediction'][k] for k in ('bytes','sha256')},
                 'Final immutable snapshot must equal the exact captured owner prediction')
            custody={'schema':'smc_validation_owned_prediction_custody_v1','route':ROUTE,'phase_id':PHASE,
                'component_source':self.source_identity(),'owner_result':{'path':str(folder/'RESULT.json'),**pin(body(folder/'RESULT.json'))},
                'owner_invocation':result['invocation_pin'],'aggregate':result['aggregate'],
                'controller_closure_pin':result['controller_closure_pin'],'freeze':freeze,
                'operational_custody_admitted':True,'private_target_accessed':False,
                'checkpoint_training_cohort':'unknown','resource_adequacy':False,'scientific_success':None,
                'AI_attempt':False,'scientific_improvement':False}
            write_new(output/'CUSTODY.json',encode(custody));return ref(output/'CUSTODY.json')

    class ValidationBenchmark:
        def __init__(self,episode):self.episode=episode

        def inspect_pair(self,pair_path,pair_sha,task_path,task_sha,*,max_bytes):
            e=self.episode
            need(pair_sha==e.PAIR_SHA and task_sha==e.TASK_SHA,'Exact prepared reference binding')
            e.public_context(pair_path,task_path)
            e.data=load_inputs(e.HERE,verify_materials=True)
            need(sum(x['bytes'] for x in e.data['materials']['files'].values())<=max_bytes,'Prospective whole material extent')
            return e.data['prepared']

        def freeze(self,pair_path,pair_sha,task_path,task_sha,phase,outcome,predictions,declaration_path,destination,*,max_bytes):
            e=self.episode
            need(phase==PHASE and outcome==OUTCOME and set(predictions)=={'offline'}
                 and PHASE in e._captured_actual and pair_sha==e.PAIR_SHA and task_sha==e.TASK_SHA,
                 'Closed Provider capture only; parent closure still pending')
            row=e._captured_actual[PHASE]
            need(path(predictions['offline'])==path(row['prediction']['path'])
                 and pin(body(declaration_path))==e._protocol['programs'][PHASE]['declaration'],
                 'Original method and captured prediction before unadmitted record')
            record={'schema':'smc_validation_unadmitted_capture_v1','phase_id':PHASE,
                'component_source':e.source_identity(),'prediction':row['prediction'],'actual':row['actual'],
                'method':e._protocol['programs'][PHASE]['method'],'packet_sha256':e.data['job']['packet_sha256'],
                'custody_admitted':False,'parent_aggregate_closure_still_required':True,'private_target_accessed':False}
            write_new(destination,encode(record));return ref(destination)

    return ValidationEpisode()
