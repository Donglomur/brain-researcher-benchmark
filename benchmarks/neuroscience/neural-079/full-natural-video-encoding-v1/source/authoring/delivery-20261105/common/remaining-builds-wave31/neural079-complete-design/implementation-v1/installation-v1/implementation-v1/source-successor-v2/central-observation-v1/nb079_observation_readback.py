"""Complete actual selected output readback; no targets, fits or report recompute."""
import os
from pathlib import PurePosixPath
from nb079_observation_common import require,fields,integer,check_pin,body_pin,bounded_encode,bounded_decode,close_all
from nb079_observation_io import descriptor,artifact,open_directory,verify_root,read_terminal
from nb079_observation_capture import parse_terminal
from nb079_observation_physical import validate_snapshot

ROLES=('observer','issuer','supervisor','provider','features','assembler','grams','references','controller','grader')
PRODUCERS=ROLES[4:]
BINARY_SHAPES=((('point_array',),(2160,228600)),(('bootstrap','estimator_array'),(74,10000)),(('bootstrap','contrast_array'),(48,10000)))
BINARY_BYTES=3959968000


def selected_index(value,keys):
    require(type(keys) is list and 1<=len(keys)<=8 and all(type(k) is str and k for k in keys),'exact nonempty key chain')
    for key in keys:
        require(type(value) is dict and key in value,'actual selected result key exists');value=value[key]
    return artifact(value)


def complete_stream(row):
    for name in ('bytes','retained_bytes'):integer(row[name])
    require(row['eof'] is True and row['durable'] is True and row['bytes']==row['retained_bytes'] and
        row['sha256']==row['retained_sha256'] and row['pending_block_base64'] is None and row['pending_block_retained_bytes']==0,
        'full durably retained stream and exact empty/pending disposition')


def completed_role(row,role,source,clock):
    fields(row,('schema','role','source_pin','process_identity','release_pin','configuration_pin','wait','streams','terminal','products','index','population_before','population_after','fresh_grade_input_observation'),'complete original role observation schema')
    from nb079_observation_observer import full_identity
    full_identity(row['process_identity'])
    require(row['schema']=='n079_outer_actual_role_observation_v1' and row['role']==role and row['source_pin']==source,
            'exact source-owned original role observation')
    wait=row['wait'];integer(wait['pid'],1);integer(wait['observed_ns']);require(type(wait['code']) is int and type(wait['status']) is int and type(wait['popen_returncode']) is int and
        wait['code']==os.CLD_EXITED and wait['status']==wait['popen_returncode']==0 and wait['natural_zero'] is True,
        'original natural integer waitid/Popen zero; bool and forced status refuse')
    require(wait['pid']==row['process_identity']['pid'] and clock['origin']<=wait['observed_ns']<clock['outer'],
        'historical original identity/wait/original cutoff, no fresh dead-PID lookup')
    for key in ('population_before','population_after'):
        value=row[key];require(type(value) is dict and clock['origin']<=value['observed_ns']<clock['outer'],'original quiescence observation clock')
        integer(value['observed_ns']);text=value['raw_ascii'];require(type(text) is str and body_pin(text.encode('ascii'))==value['pin'],'actual raw quiescence bytes')
        require(dict(line.split() for line in text.splitlines()).get('populated')=='0','actual empty owned role scope before and after products')
    require(set(row['streams'])=={role+'/stdout',role+'/stderr'},'exact both role streams')
    for stream in row['streams'].values():complete_stream(stream)
    return row


class Readback:
    def __init__(self,observer):
        self.observer=observer;self.io=observer.io;self.policy=observer.policy;self.limits=self.policy['bootstrap']['limits']
        self.encoding=self.io.encoding;self.inventory={};self.files=[];self.total=0;self.metadata=0;self.metadata_records=[]
    def _reserve(self,size,kind):
        integer(size);self.total+=size
        if kind=='metadata':self.metadata+=size
        require(self.total<=self.limits['readback_bytes'],'whole selected central readback byte ceiling before read')
        require(self.metadata<=self.limits['metadata_total_bytes'] and 4*self.metadata<=self.limits['live_buffer_bytes'],
                'cumulative complete retained metadata/live payload bound before parse')
    def _root(self,name):
        root=self.policy['roots'][name];fd=open_directory(root['path']);first=None
        try:verify_root(fd,root)
        except BaseException as error:first=error;raise
        finally:close_all([('readback exact root descriptor',lambda:os.close(fd))],first)
        return root
    def _absolute(self,root_name,item):
        artifact(item);root=self._root(root_name);path=PurePosixPath(item['path'])
        if path.is_absolute():
            require(str(path.parent)==root['path'],'exact declared root-owned absolute artifact leaf');absolute=str(path)
        else:
            require(str(path)==item['path'] and '..' not in path.parts,'canonical relative artifact below selected root')
            absolute=root['path'].rstrip('/')+'/'+item['path']
        return {'path':absolute,'pin':{k:item[k] for k in ('bytes','sha256')}},root['owner_uid']
    def _observed(self,role,item):
        artifact(item);require(item['path'] in self.inventory[role] and
            {k:self.inventory[role][item['path']][k] for k in ('path','bytes','sha256')}==item,'exact actual observed complete output inventory member')
    def json(self,root,item,observed=False):
        if observed:self._observed(root,item)
        selected,owner=self._absolute(root,item);self._reserve(item['bytes'],'metadata')
        value=self.io.json(selected,'outer',owner_uid=owner);self.files.append({'kind':'metadata','descriptor':selected})
        self.metadata_records.append({'descriptor':selected,'body':value});return value
    def opaque(self,root,item):
        self._observed(root,item);selected,owner=self._absolute(root,item);self._reserve(item['bytes'],'opaque')
        self.io.capture(selected,'outer',kind='result',keep=False,maximum=self.limits['readback_bytes'],owner_uid=owner)
        self.files.append({'kind':'full_original_grader_array','descriptor':selected})
    def stream(self,item,role,terminal):
        complete_stream(item);artifact_={k:item[k] for k in ('path','bytes','sha256')}
        selected,owner=self._absolute('parent_stream',artifact_);self._reserve(item['bytes'],'stream')
        if terminal:
            value=read_terminal(self.io,selected,'n079_actual_role_return_v1',owner)
            fields(value,('schema','status','role','result','source_pin','budget_prefix','endpoint_record','configuration_custody'),'actual complete role terminal')
            require(value['configuration_custody']=='requires_actual_outer_release_gate_bootstrap_and_return_join','exact unchanged original role custody ABI')
            require(value['status']=='complete' and value['role']==role and value['source_pin']==self.policy['parent_source_pin'],'actual role terminal source join')
        else:
            self.io.capture(selected,'outer',kind='stream',keep=False,maximum=self.limits['stream_bytes'],owner_uid=owner);value=None
        self.files.append({'kind':'full_original_role_stream','descriptor':selected});return value
    def run(self):
        observed=self.observer.returned;require(observed['forced_cleanup'] is False and observed['wait']['natural_zero'] is True,'original natural finalizer boundary')
        for value in observed['streams'].values():complete_stream(value)
        output=self.observer.admission['central_output_root'];stdout=observed['streams']['stdout']
        selected={'path':stdout['path'],'pin':{k:stdout[k] for k in ('bytes','sha256')}}
        require(str(PurePosixPath(selected['path']).parent)==output['path'],'own actual full finalizer stdout path')
        self._reserve(stdout['bytes'],'stream');terminal=read_terminal(self.io,selected,'n079_complete_source_terminal_v1',output['owner_uid'])
        parse_terminal(bounded_encode(terminal,self.encoding)+b'\n',self.encoding)
        stderr=observed['streams']['stderr'];self._reserve(stderr['bytes'],'stream')
        self.io.capture({'path':stderr['path'],'pin':{k:stderr[k] for k in ('bytes','sha256')}},'outer',kind='stream',keep=False,
                        maximum=self.limits['stream_bytes'],owner_uid=output['owner_uid'])
        original=terminal['original_outer'];fields(original,('path','bytes','sha256','audit_after_cleanup','terminal_boundary'),'original outer return ABI')
        outer_item={k:original[k] for k in ('path','bytes','sha256')};outer=self.json('parent_report',outer_item)
        require(outer['schema']=='n079_source_owned_outer_grade_v1' and outer['complete'] is True,'actual original complete outer grade')
        snapshot=validate_snapshot(outer['closed_snapshot'],self.observer.profile,require_closed=True)
        require(snapshot['source_pin']==self.policy['parent_source_pin'] and snapshot['origin_ns']==self.policy['original_clock']['origin'] and
            snapshot['observed_ns']<self.policy['original_clock']['outer'],'same original source/physical interval')
        closed=self.json('parent_report',outer['closed_scope_evidence'])
        require(snapshot['raw_evidence_pin']=={k:outer['closed_scope_evidence'][k] for k in ('bytes','sha256')},'exact original closed scope evidence')
        fields(closed,('actual','cpu','roles','inventory','transfers'),'complete original closed-scope evidence')
        require(set(closed['roles'])==set(ROLES),'all ten actual original role observations')
        identities=[];indices={}
        for role in ROLES:
            row=completed_role(closed['roles'][role],role,self.policy['parent_source_pin'],self.policy['original_clock'])
            identities.append((row['process_identity']['pid'],row['process_identity']['start_ticks']))
            self.io.ledger.charge({'validation_calls':1},'complete original role observation validation','outer')
            expected_bytes=bounded_encode(row,self.observer.profile['encoding_limits'])
            independently=self.json('parent_report',{'path':role+'-OBSERVATION.json',**body_pin(expected_bytes)})
            require(independently==row,'actual separately published complete observation equals closed-scope body')
            for name in ('stdout','stderr'):
                parsed=self.stream(row['streams'][role+'/'+name],role,name=='stdout')
                if name=='stdout':require(parsed==row['terminal'],'actual full role stream terminal equals stored observation')
            if role not in PRODUCERS:
                require(row['products'] is None and row['index'] is None,'daemon has no fabricated producer result');continue
            products=row['products'];require(type(products) is list,'actual full observed producer inventory')
            root=self.policy['output_roots'][role]
            require(len(products)<=root['maximum_files'] and sum(integer(p['bytes']) for p in products)<=root['maximum_bytes'],
                    'unchanged selected full product caps')
            self.inventory[role]={p['path']:p for p in products};require(len(self.inventory[role])==len(products),'unique full producer paths')
            item=selected_index(row['terminal']['result'],root['index_result_key']);require(item==row['index']['descriptor'],'original terminal/index descriptor chain')
            value=self.json(role,item,True);require(value==row['index']['body'],'actual full source-owned index body')
            indices[role]=value
        require(len(set(identities))==10 and (observed['blocked']['identity']['pid'],observed['blocked']['identity']['start_ticks']) not in identities,
                'ten historical children and actual finalizer remain distinct')
        grader=closed['roles']['grader'];numeric=indices['grader'];require(numeric['schema']=='n079_protected_numeric_grade_v1','unchanged original numeric grade')
        require(outer['grade']==grader['index'] and outer['grader_return']==grader and outer['grader_output_inventory']==grader['products'],
                'all actual original grader graph joins')
        fresh=grader['fresh_grade_input_observation'];require(fresh['declared']['index']==numeric['input_index'] and
            fresh['declared_pin']==numeric['input_index_observation_pin'] and fresh['declared']['source_pin']==self.policy['parent_source_pin'] and
            fresh['actual_read_pin']=={k:numeric['input_index'][k] for k in ('bytes','sha256')},'actual full input-index observation, no target opening')
        require(body_pin(bounded_encode(fresh['declared'],self.observer.profile['encoding_limits']))==fresh['declared_pin'] and
            self.policy['original_clock']['origin']<=fresh['started_ns']<=fresh['finished_ns']<self.policy['original_clock']['scientific'],
            'actual original scientific-clock input-index observation identity')
        mandatory=[grader['index']['descriptor']];total=0
        for chain,shape in BINARY_SHAPES:
            matrix=numeric
            for key in chain:matrix=matrix[key]
            require(matrix['shape']==list(shape) and matrix['dtype']=='<f8','all original complete metric coordinates/draws/status rows')
            item=matrix['object'];require(item['bytes']==shape[0]*shape[1]*8,'full original binary algebra-derived extent')
            self.opaque('grader',item);mandatory.append(item);total+=item['bytes']
        require(total==BINARY_BYTES and len(self.inventory['grader'])==4 and
            set(self.inventory['grader'])=={item['path'] for item in mandatory},'exact four original grader artifacts')
        controller=indices['controller'];require(controller['schema']=='n079_complete_controller_index_v1' and
            controller['source_pin']==self.policy['parent_source_pin'] and controller['study_pin']==self.policy['study_pin'],'complete controller source/study')
        candidates=self.json('controller',controller['candidate_index'],True);native=self.json('controller',controller['native_index'],True)
        require(candidates['schema']=='n079_complete_candidate_programme_v1' and
            candidates['counts']=={'bundles':36,'queries':3672,'reports':36,'person_video_predictions':22032},'all original candidate work units')
        require(native['schema']=='n079_complete_native_programme_v1' and len(native['jobs'])==22,'all22 actual native captures; outcome preserved')
        reference=indices['references'];require(reference['schema']=='n079_full_reference_index_v1' and
            reference['source_pin']==self.policy['parent_source_pin'] and reference['study_pin']==self.policy['study_pin'],'full reference source/study')
        result=reference['result'];require(result['counts']['spectra']==36 and result['counts']['setting_factors']==546 and
            result['counts']['completed_target_fits']==5496 and len(result['records'])==5496 and len(result['final'])==36,
            'complete full reference metadata roster; one producer not5496 processes')
        panels=candidates['consolidated'];require(len(panels)==36 and len({p['id'] for p in panels})==36,'all36 original report bundles')
        reports=[]
        for panel in panels:
            require(len(panel['queries'])==102 and [p['video_id'] for p in panel['queries']]==list(range(1001,1103)) and
                len(panel['predictions'])==6,'all own102 queries and6 person panels')
            report=self.json('controller',panel['report_object'],True)
            require(report==panel['report_record']['report'] and panel['report_record']==candidates['reports'][panel['id']],
                'actual ordinary report and original capture join')
            reports.append(panel['report_object'])
        composed=terminal['result'];fields(composed,('index','audit_after_publication','terminal_boundary'),'actual report composer terminal return ABI')
        report_result=self.json('parent_report',composed['index'])
        require(report_result['schema']=='n079_additive_report_result_v1' and report_result['source_pin']==self.policy['parent_source_pin'] and
            report_result['study_pin']==self.policy['study_pin'] and report_result['original_outer']['object']==outer_item and
            report_result['original_outer']['actual_return']==original and report_result['original_numerical_grade']['object']==grader['index']['descriptor'] and
            report_result['original_controller']['object']==closed['roles']['controller']['index']['descriptor'],
            'same actual immutable outer/numeric/controller report-result joins, no second composer')
        quality=report_result['report_quality'];require(quality['denominator']==432 and len(quality['reports'])==36 and
            all(r['denominator']==12 and len(r['item_outcomes'])==12 for r in quality['reports'].values()) and
            quality['measurement']=='fixed_denominator_verified_credit_lower_bound' and quality['unassessable_is_incorrect'] is False and
            quality['scientific_reasoning_accuracy_claim'] is False,'all432 lower-bound report items without promoted semantic claims')
        require(len(report_result['actual_report_joins'])==36 and {r['report_object']['path'] for r in report_result['actual_report_joins']}=={r['path'] for r in reports},
                'complete actual report object graph')
        for selected in self.policy['readback_catalog']:
            role=selected['role'];row=self.inventory[role].get(selected['path']);require(row is not None,'selected metadata is an actual produced file')
            value=self.json(role,{k:row[k] for k in ('path','bytes','sha256')},True)
            require(type(value) is dict and value.get('schema')==selected['schema'],'exact source-selected output metadata type')
        # Recheck source/environment and original selected typed profile after all
        # output observations; no library or numerical model is rerun.
        for item in self.policy['sources']+self.observer.parent_sources:
            self.io.capture(item,'outer',keep=False,maximum=self.limits['source_bytes'],owner_uid=self.observer.owner(item['path']))
        self.io.capture(self.policy['python'],'outer',keep=False,maximum=self.limits['source_bytes'],owner_uid=self.observer.owner(self.policy['python']['path']))
        require(dict(os.environ)==self.policy['environment'],'same selected central environment after complete readback')
        require(self.observer.identity.observe(os.getpid(),'outer')==self.observer.central_identity,'same actual central identity, no late replacement')
        self.observer.close()
        central={'schema':'nb079_complete_central_observation_v1','request':self.observer.configuration['request'],
            'policy':self.observer.configuration['policy'],'admission':self.observer.configuration['admission'],
            'source_pin':self.policy['source_pin'],'parent_source_pin':self.policy['parent_source_pin'],'study_pin':self.policy['study_pin'],
            'original_clock':self.policy['original_clock'],'original_finalizer':observed,'terminal':terminal,
            'original_outer':outer,'closed_scope':closed,'report_result':report_result,'selected_metadata':self.metadata_records,
            'actual_rehashed_files':self.files,'full_original_grader_binary_bytes':BINARY_BYTES,'central_readback_bytes':self.total,
            'parent_full_inventories':'retained original source-owned evidence; central independently rehashes only the exact named subset above',
            'ledger_before_publication':self.io.ledger.snapshot(),'observer_cleanup_complete':True,
            'scientific_qualification_added':False,'physical_boundary':'central/finalizer/issuer/feeder are outside original scientific common scope; no new whole physical total',
            'external_terminal_boundary':'actual central wrapper original status/EOF remains independently observed externally; this artifact cannot self-certify it'}
        raw=bounded_encode(central,self.encoding);root=self.observer.admission['central_output_root'];fd=open_directory(root['path']);first=None
        try:
            verify_root(fd,root);written=self.io.write(fd,'CENTRAL_READBACK.json',raw,'outer')
        except BaseException as error:first=error;raise
        finally:close_all([('central final publication directory',lambda:os.close(fd))],first)
        absolute_item={'path':root['path'].rstrip('/')+'/'+written['path'],'pin':{k:written[k] for k in ('bytes','sha256')}}
        self.io.capture(absolute_item,'outer',owner_uid=root['owner_uid'])
        self.observer.clock.tick('outer')
        return {'path':absolute_item['path'],**absolute_item['pin']}
