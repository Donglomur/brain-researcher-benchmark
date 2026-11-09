"""Own-bundle report evidence and immutable post-outer report composition.

No candidate scores, prose judges, semantic instrumentation or scientific I/O.
All admission exchanges are independently implemented issuer obligations.
"""
import hashlib
import json
import os
import stat

QUERY = tuple(range(1001, 1103))
ITEMS = ('target','generalization','support','normalization','selection','features',
         'method_lineage','evidence_integrity','confounds','metric_claims',
         'failure_status','prediction_lineage')
SEMANTIC_ITEMS = ('normalization','selection','features','method_lineage','failure_status')


def require(value, reason):
    if not value: raise ValueError(reason)


def fields(value, keys):
    require(type(value) is dict and set(value) == set(keys), 'closed schema: '+','.join(keys))


def integer(value, minimum=0):
    require(type(value) is int and value >= minimum, 'bounded nonnegative integer')
    return value


def descriptor(value):
    fields(value, ('path','bytes','sha256'))
    require(type(value['path']) is str and value['path'] and '\x00' not in value['path'], 'ordinary object path')
    integer(value['bytes'])
    digest(value['sha256'])
    return value


def digest(value):
    require(type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value), 'SHA256 digest')


def pin(value):
    fields(value, ('bytes','sha256')); integer(value['bytes']); digest(value['sha256'])


def limits(value):
    fields(value, ('max_json_bytes','max_nodes','max_depth','max_string_bytes','max_items','max_live_payload_bytes'))
    for x in value.values(): integer(x,1)
    require(value['max_live_payload_bytes'] >= 4*value['max_json_bytes'], 'four bounded JSON payloads before allocation')


def bounded(value, cap):
    nodes=0
    def walk(v, depth):
        nonlocal nodes
        nodes+=1; require(nodes<=cap['max_nodes'] and depth<=cap['max_depth'], 'JSON nodes/depth ceiling')
        if type(v) is dict:
            require(len(v)<=cap['max_items'], 'JSON object item ceiling')
            for k,x in v.items():
                require(type(k) is str, 'JSON keys are strings'); walk(k,depth+1); walk(x,depth+1)
        elif type(v) is list:
            require(len(v)<=cap['max_items'], 'JSON list item ceiling')
            for x in v:walk(x,depth+1)
        elif type(v) is str:
            require(len(v)<=cap['max_string_bytes'] and len(v.encode())<=cap['max_string_bytes'], 'JSON string byte ceiling')
        else:require(v is None or type(v) in (bool,int,float), 'JSON-only value')
    walk(value,0)
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
    require(len(raw)<=cap['max_json_bytes'], 'bounded complete JSON bytes')
    return raw


def ident(value, cap):
    raw=bounded(value,cap)
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def clone(value, cap):return json.loads(bounded(value,cap))


def _unique(values):
    require(type(values) is list and all(type(v) is str and v for v in values) and len(set(values))==len(values), 'unique nonempty IDs')
    return values


def _pairs(pairs):
    result={}
    for key,value in pairs:
        require(key not in result,'duplicate JSON key');result[key]=value
    return result


def read_json(context, repository, item, cap, work):
    descriptor(item); require(item['bytes']<=cap['max_json_bytes'], 'ordinary JSON extent before read')
    context.ledger.charge(work,{'source_read_bytes':item['bytes']+1},'actual source-bound report metadata read before allocation')
    fd=repository.open(item); error=None
    try:
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_size==item['bytes'],'ordinary exact metadata extent')
        chunks=[];size=0;hasher=hashlib.sha256()
        while size<item['bytes']:
            context.tick(); block=os.read(fd,min(65536,item['bytes']-size))
            require(block,'complete ordinary metadata read');chunks.append(block);size+=len(block);hasher.update(block)
        require(not os.read(fd,1),'no trailing metadata bytes')
        after=os.fstat(fd)
        require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
                (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'stable ordinary metadata identity')
        require(hasher.hexdigest()==item['sha256'],'exact ordinary metadata hash')
        value=json.loads(b''.join(chunks),object_pairs_hook=_pairs,
                         parse_constant=lambda token: (_ for _ in ()).throw(ValueError('nonfinite JSON token')))
        bounded(value,cap);return value
    except BaseException as exc:error=exc;raise
    finally:
        try:os.close(fd)
        except BaseException as exc:
            if error is None:raise
            error.add_note('report metadata close failed: '+type(exc).__name__)


def write_json(context, output_fd, value, cap, work, name):
    # Concrete source-owned writer already owns storage admission, O_EXCL and
    # complete ordinary descriptor publication; no arbitrary writer callback.
    from n079_products import write_index
    bounded(value,cap)
    result=write_index(context,output_fd,value,work,name)
    descriptor(result);return result


def _seal(value):
    require(type(value) is dict and {'body','evidence','source','states'}<=set(value),'actual Controller seal')
    require(value['body']['method_pin']==value['source']['pin'],'seal source identity')
    pin(value['source']['pin'])
    return {'body':value['body'],'evidence':value['evidence'],'states':value['states']}


def _job(value, cap):
    require(type(value) is dict and {'context','phase','request_pin','output','inventory','closure'}<=set(value),'actual observed job return')
    require(value['phase']=='closed','completed actual job before report')
    return {'context':value['context'],'phase':value['phase'],'request_pin':value['request_pin'],
            'output_pin':ident(value['output'],cap),'inventory_pin':ident(value['inventory'],cap),'closure':value['closure']}



def validate_cost_prefix(value,bundle_id,policy_id,study_pin,cap):
    fields(value,('record','evidence'))
    record=value['record']
    fields(record,('schema','bundle_id','source_pin','study_pin','allocation_pin','work_ids','local_attempted',
        'ledger_attempt_count','observed_ns','future_report_included','meaning','actual_billing_and_remote_resources'))
    require(record['schema']=='n079_observed_bundle_cost_prefix_v1' and record['bundle_id']==bundle_id and
        record['study_pin']==study_pin and record['future_report_included'] is False,'actual pre-report own cost prefix')
    for name in ('source_pin','study_pin','allocation_pin'):pin(record[name])
    expected={'policy/'+policy_id,'training/'+bundle_id}|{'query/'+bundle_id+'/'+str(q) for q in QUERY}
    require(set(_unique(record['work_ids']))==expected,'shared policy and own training102query cost work only')
    require(type(record['local_attempted']) is dict,'actual attempted counters retained privately')
    integer(record['ledger_attempt_count']);integer(record['observed_ns'])
    require(record['meaning']=='central attempted reservations; policy row is shared across signals, not a new per-bundle cost' and
        record['actual_billing_and_remote_resources']=='unknown_without_independent_external_evidence','attempted and independently unknown physical/billing costs distinguished')
    require(value['evidence']==ident(record,cap),'exact source-defined observed cost record identity')

def _validate_input(value, alias):
    fields(value,('schema','bundle_alias','persons','training_people','query_people','train_videos','query_videos',
        'query_shape','support','person_support','person_failures','feature_manifest','feature_output_ids',
        'coordinate_manifest','fit_row_manifests','held_target_access','source_pin','observation_pin'))
    require(value['schema']=='n079_report_public_input_facts_v1' and value['bundle_alias']==alias,'current public input identity')
    persons=_unique(value['persons']);require(len(persons)==6,'all six opaque person aliases')
    require(value['training_people']==value['query_people']==persons and value['train_videos']==list(range(1,1001)) and
        value['query_videos']==list(QUERY) and value['query_shape']==[6,127,1800],'complete same-person generalization support')
    fields(value['support'],('people','sessions','channels','time_samples','train_videos','query_videos','status','failure_record_ids'))
    for key,wanted in zip(('people','sessions','channels','time_samples','train_videos','query_videos'),(6,48,127,1800,1000,102)):
        require(type(value['support'][key]) is int and value['support'][key]==wanted,'full original support counts')
    require(value['support']['status'] in ('complete','incomplete','unavailable'),'explicit support status')
    _unique(value['support']['failure_record_ids'])
    for name in ('person_support','person_failures'):
        require(type(value[name]) is dict and set(value[name])==set(persons),'exact six person evidence sets')
        for records in value[name].values():
            require(type(records) is list,'source-bound support/failure objects')
            for record in records:descriptor(record)
    descriptor(value['feature_manifest']);descriptor(value['coordinate_manifest'])
    require(len(_unique(value['feature_output_ids']))==17,'all17 available feature outputs')
    require(type(value['fit_row_manifests']) is list,'fitting support objects')
    for record in value['fit_row_manifests']:descriptor(record)
    require(value['held_target_access']=='none','no held target access')
    pin(value['source_pin']);pin(value['observation_pin'])


def _validate_snapshot(snapshot):
    fields(snapshot,('schema','bundle_id','bundle_alias','person_aliases','public_input','program','fitted','queries','jobs','cost_records','semantic_records'))
    require(snapshot['schema']=='n079_own_bundle_pre_report_snapshot_v1','source-owned pre-report snapshot')
    require(type(snapshot['bundle_id']) is str and snapshot['bundle_id'] and type(snapshot['bundle_alias']) is str and snapshot['bundle_alias'] and
        snapshot['bundle_alias']!=snapshot['bundle_id'],'opaque own-bundle alias')
    require(len(_unique(snapshot['person_aliases']))==6,'six current opaque aliases')
    descriptor(snapshot['public_input'])
    for name in ('program','fitted'):
        fields(snapshot[name],('body','evidence','states'))
        pin(snapshot[name]['body']['method_pin'])
    require(type(snapshot['queries']) is list and len(snapshot['queries'])==102,'all102 queries before report')
    require([r['video_id'] for r in snapshot['queries']]==list(QUERY),'exact ordered102 current stimuli')
    jobs={row['context']:row for row in snapshot['jobs']}
    require(len(jobs)==len(snapshot['jobs']) and all(name.startswith(snapshot['bundle_id']+'-') for name in jobs),'own-bundle unique observed jobs only')
    for row in snapshot['jobs']:
        fields(row,('context','phase','request_pin','output_pin','inventory_pin','closure'))
        require(row['phase']=='closed' and '-report' not in row['context'],'pre-report observed jobs only')
        for name in ('request_pin','output_pin','inventory_pin'):pin(row[name])
    require(snapshot['fitted']['body']['lineage']['training_job'] in jobs,'actual own training job')
    for row in snapshot['queries']:
        fields(row,('video_id','prediction','closure','source_seal','view_evidence','job'))
        descriptor(row['prediction']);require(row['prediction']['bytes']==6*127*1800*8,'full observed prediction extent')
        fields(row['source_seal'],('body','evidence','states'))
        require(row['job'] in jobs and row['closure']==jobs[row['job']]['closure'],'actual own query/closure join')
        require(row['source_seal']['body']['phase']=='query_final','actual query source seal')
    require(type(snapshot['cost_records']) is list and snapshot['cost_records'],'actual observed pre-report budget prefix required')
    for name in ('cost_records','semantic_records'):
        for row in snapshot[name]:descriptor(row)


def derive(snapshot, public_input, semantic_records, cap):
    """Pure derivation; trusted only after issuer admission of exact inputs."""
    _validate_snapshot(snapshot);_validate_input(public_input,snapshot['bundle_alias'])
    require(public_input['persons']==snapshot['person_aliases'],'same admitted person aliases')
    alias=snapshot['bundle_alias'];mapping={};evidence={};counters={}
    def ref(kind,record):
        key=kind+':'+ident(record,cap)['sha256']
        if key in mapping:return mapping[key]['id']
        count=counters.get(kind,0);counters[kind]=count+1
        name='own/'+alias+'/'+kind+'/'+str(count)
        mapping[key]={'id':name,'kind':kind,'record_pin':ident(record,cap)}
        return name
    coordinate=ref('coordinate_manifest',public_input['coordinate_manifest'])
    fit_manifests=[ref('fit_row_manifest',x) for x in public_input['fit_row_manifests']]
    row_default=fit_manifests[0] if fit_manifests else ref('training_rows',list(range(1,1001)))
    def ev(kind,record,row=row_default,status='observed'):
        name=ref(kind,record)
        evidence[name]={'id':name,'kind':kind,'status':status,'row_manifest_id':row,'coordinate_manifest_id':coordinate}
        return name
    sources=[ev('source',snapshot['program']['body']['method_pin']),ev('source',snapshot['fitted']['body']['method_pin'])]
    states=[ref('state',item) for _,item in sorted(snapshot['fitted']['states'].items())]
    queries=[];predictions=[];closures=[]
    for row in snapshot['queries']:
        queries.append(ref('query',{'video_id':row['video_id'],'job':row['job']}))
        rows=ref('query_rows',[row['video_id']])
        predictions.append(ev('prediction',row['prediction'],rows))
        closures.append(ref('closure',row['closure']))
        sources.append(ev('source',row['source_seal']['body']['method_pin']))
    sources=list(dict.fromkeys(sources));closures=list(dict.fromkeys(closures))
    costs=[ev('resource',record) for record in snapshot['cost_records']]
    completed=[ref('completed_action',row) for row in snapshot['jobs']]
    support={person:[ref('support',record) for record in public_input['person_support'][person]] for person in public_input['persons']}
    failures={person:[ev('failure',record,status='observed_failure') for record in public_input['person_failures'][person]] for person in public_input['persons']}
    failure_ids=list(dict.fromkeys(x for values in failures.values() for x in values))
    known_support=dict(public_input['support']);known_support['failure_record_ids']=failure_ids
    trusted={'persons':public_input['persons'],'bundle_alias':alias,'query_shape':[6,127,1800],
        'training_people':public_input['training_people'],'query_people':public_input['query_people'],
        'train_videos':public_input['train_videos'],'query_videos':public_input['query_videos'],
        'support':known_support,'person_support':support,'person_failures':failures,
        'transforms':[],'fit_row_manifests':fit_manifests,'held_target_access':'none',
        'selection_status':'unassessable','diagnostics':[],'selection_record':None,
        'feature_manifest':ref('feature_manifest',public_input['feature_manifest']),'available_output_count':17,
        'used_feature_outputs':[],'method_sources':sources,'method_states':states,'method_settings':[],
        'method_family':'unassessable','evidence':evidence,'person_analysis':{p:[] for p in public_input['persons']},
        'action_status':{'completed_record_ids':completed,'failed_record_ids':[],'unknown_record_ids':[],
                         'unexecuted_declarations':[],'cost_record_ids':costs},
        'bundle_seal':ref('training_seal',snapshot['fitted']['evidence']),'query_records':queries,
        'prediction_manifests':predictions,'closure_records':closures,
        'person_predictions':{p:list(predictions) for p in public_input['persons']},
        'item_assessment':{item:{'status':'assessable','reason':'independently admitted actual own-bundle record join',
                                'evidence_ids':[]} for item in ITEMS},
        'declared_consistency':{'semantic_credit':False,'actual_feature_use':'unknown','actual_model_family':'unknown',
                               'normalization_semantics':'unknown','selection_semantics':'unknown'}}
    for item in SEMANTIC_ITEMS:
        trusted['item_assessment'][item]={'status':'unassessable','reason':'arbitrary generated Python has no independently source-defined semantic observation for this item','evidence_ids':[]}
    # The initial implementation intentionally supports no semantic promotion.
    # Merely receiving a declaration or typed success record cannot change this.
    require(semantic_records==[] and snapshot['semantic_records']==[],
            'semantic observation promotion requires separately reviewed exact source adapter; declaration is insufficient')
    trusted['item_assessment']['target']['evidence_ids']=predictions
    trusted['item_assessment']['generalization']['evidence_ids']=fit_manifests+queries
    trusted['item_assessment']['support']['evidence_ids']=[v for xs in support.values() for v in xs]+failure_ids
    trusted['item_assessment']['evidence_integrity']['evidence_ids']=list(evidence)
    trusted['item_assessment']['failure_status']['evidence_ids']=costs+completed
    trusted['item_assessment']['failure_status']['reason']='Actual attempted budget prefixes are authenticated; semantic failed/unknown/unexecuted action dispositions and billing are not independently observed.'
    trusted['item_assessment']['prediction_lineage']['evidence_ids']=queries+predictions+closures
    public={'schema':'n079_own_bundle_pre_report_metadata_v1','bundle_alias':alias,'persons':list(public_input['persons']),
        'cutoff':'after_all102_predictions_before_report','facts':{k:trusted[k] for k in (
        'query_shape','support','person_support','person_failures','fit_row_manifests','held_target_access',
        'feature_manifest','available_output_count','method_sources','method_states','evidence','person_analysis',
        'action_status','bundle_seal','query_records','prediction_manifests','closure_records','person_predictions')},
        'available_feature_output_ids':list(public_input['feature_output_ids']),
        'observation_status':{item:trusted['item_assessment'][item]['status'] for item in ITEMS},
        'instructions':{'selection_and_method_declarations':'Describe your own sealed method honestly; these declarations do not establish actual semantic instrumentation.',
            'future_report_records':'Own report seal/closure/cost is joined privately later, outside this cutoff.',
            'action_disposition_scope':'Completed process IDs are observed. Empty failed/unknown/unexecuted lists do not establish absence; full failure_status remains unassessable.',
            'forbidden_feedback':['native','reference_results','held_targets','other_bundles','hidden_mismatch_map'],
            'prose_scored':False}}
    return {'trusted':clone(trusted,cap),'public':clone(public,cap),'private_record_map':list(mapping.values())}


class ReportEvidenceBuilder:
    def __init__(self,context,repository,output_fd,selected):
        from n079_products import ProducedRepository
        require(type(repository) is ProducedRepository and repository.context is context,'actual concrete same-context ProducedRepository')
        fields(selected,('schema','study_pin','source_pin','work_id','limits','bundles'))
        require(selected['schema']=='n079_report_evidence_selection_v1' and selected['work_id']=='controller','report builder selection')
        require(selected['source_pin']==context.source_pin,'actual admitted helper source closure')
        pin(selected['study_pin']);limits(selected['limits'])
        require(type(selected['bundles']) is dict and len(selected['bundles'])==36,'all36 source-owned report units')
        aliases=[]
        for value in selected['bundles'].values():
            fields(value,('alias','public_input','semantic_records'));descriptor(value['public_input'])
            require(type(value['alias']) is str and value['alias'],'opaque bundle alias')
            require(value['semantic_records']==[],'no invented semantic instrumentation')
            aliases.append(value['alias'])
        require(len(set(aliases))==36,'unique opaque aliases')
        self.context,self.repository,self.output_fd=context,repository,output_fd
        self.selected=clone(selected,selected['limits']);self.cap=self.selected['limits'];self.finished={}

    def prepare(self,controller,bundle,cost_records):
        from n079_controller import Controller
        require(type(controller) is Controller and controller.context is self.context,'actual concrete Controller instance')
        key=bundle['id'];require(key in self.selected['bundles'] and key not in self.finished,'one actual own-bundle report prefix')
        choice=self.selected['bundles'][key]
        require(controller.selected['public_bundles'][key]['alias']==choice['alias'],'same current opaque alias')
        input_facts=read_json(self.context,self.repository,choice['public_input'],self.cap,'controller')
        _validate_input(input_facts,choice['alias'])
        query=controller.queries[key]
        require(set(query)==set(QUERY),'all102 actual queries before report metadata')
        jobs=[_job(row,self.cap) for row in controller.jobs if row['context'].startswith(key+'-')]
        snapshot={'schema':'n079_own_bundle_pre_report_snapshot_v1','bundle_id':key,'bundle_alias':choice['alias'],
            'person_aliases':input_facts['persons'],'public_input':choice['public_input'],
            'program':_seal(controller.programs[bundle['policy_id']]),'fitted':_seal(controller.fitted[key]),
            'queries':[{'video_id':q,**{k:query[q][k] for k in ('prediction','closure','view_evidence','job')},
                        'source_seal':_seal(query[q]['source_seal'])} for q in QUERY],
            'jobs':jobs,'cost_records':cost_records,'semantic_records':choice['semantic_records']}
        _validate_snapshot(snapshot)
        for item in cost_records:
            value=read_json(self.context,self.repository,item,self.cap,'controller')
            validate_cost_prefix(value,key,bundle['policy_id'],self.selected['study_pin'],self.cap)
        number=len(self.finished);prefix='report-evidence-'+str(number)
        ordinary=write_json(self.context,self.output_fd,snapshot,self.cap,'controller',prefix+'-snapshot.json')
        self.repository.register(ordinary)
        # Issuer independently reopens this newly written ordinary object and
        # joins its existing original-clock jobs/source/budget-prefix records.
        admission=self.context.authority.exchange('report_evidence_input_admission',{
            'snapshot':ordinary,'source_pin':self.context.source_pin,'study_pin':self.selected['study_pin'],
            'bundle_id':key,'bundle_alias':choice['alias'],'pre_report_cutoff':True})
        admitted=read_json(self.context,self.repository,ordinary,self.cap,'controller')
        require(admitted==snapshot,'written actual snapshot equals source derivation')
        derived=derive(admitted,input_facts,[],self.cap)
        public=write_json(self.context,self.output_fd,derived['public'],self.cap,'controller',prefix+'-public.json')
        self.repository.register(public)
        private=write_json(self.context,self.output_fd,{'schema':'n079_report_private_evidence_v1',
            'snapshot':ordinary,'admission':admission,'public':public,'bundle_id':key,
            'bundle_alias':choice['alias'],'source_pin':self.context.source_pin,'study_pin':self.selected['study_pin'],
            'derived':derived},self.cap,'controller',prefix+'-private.json')
        self.repository.register(private)
        result={'public':public,'private':private,'snapshot':ordinary,'admission':admission}
        self.context.authority.exchange('publish_own_report_metadata',{'bundle_id':key,'bundle_alias':choice['alias'],**result})
        self.finished[key]=clone(result,self.cap);return clone(result,self.cap)


class ReportResultComposer:
    """Terminal audit on the retained exact outer AuditIO and finalizer row."""
    def __init__(self,io,selected):
        from n079_outer_common import AuditIO, AuditCounters
        require(type(io) is AuditIO and type(io.audit) is AuditCounters and io.clock is io.audit.clock,
                'exact retained original AuditIO/AuditCounters/clock')
        require(io.audit.reservation is not None,'original finalizer row already centrally reserved')
        fields(selected,('schema','source_pin','study_pin','limits','output_name','bundle_ids',
                         'report_root','controller_root','grader_root'))
        require(selected['schema']=='n079_report_result_selection_v1' and selected['source_pin']==io.audit.source_pin,
                'same original admitted source closure')
        pin(selected['study_pin']);limits(selected['limits'])
        require(selected['limits']['max_json_bytes']<=io.limits['file_bytes'], 'additive metadata bound cannot enlarge original finalizer file ceiling')
        require(len(_unique(selected['bundle_ids']))==36,'exact original36 bundles')
        name=selected['output_name'];require(type(name) is str and name not in ('','.','..') and '/' not in name and '\x00' not in name,'exclusive additive output basename')
        for name in ('report_root','controller_root','grader_root'):
            fields(selected[name],('path','identity'))
            fields(selected[name]['identity'],('device','inode'))
        require(len({selected[n]['path'] for n in ('report_root','controller_root','grader_root')})==3,'disjoint admitted terminal/controller/grader roots')
        self.io=io;self.selected=clone(selected,selected['limits']);self.cap=self.selected['limits']
        self.used=False;self.inventory={}

    def _root(self,role):
        from n079_outer_common import open_directory, canonical_path
        root=self.selected[role+'_root'];canonical_path(root['path'])
        fd=open_directory(root['path']);first_error=None
        try:
            st=os.fstat(fd);require({'device':st.st_dev,'inode':st.st_ino}==root['identity'],'same originally admitted output root')
        except BaseException as error:
            first_error=error;raise
        finally:
            try:os.close(fd)
            except BaseException as close_error:
                if first_error is None:raise
                first_error.n079_report_root_close_error=close_error
                first_error.add_note('independent report root descriptor close failed: '+type(close_error).__name__)
        return root['path']

    def _read(self,item,role,observed=True):
        from pathlib import PurePosixPath
        descriptor(item);require(item['bytes']<=self.cap['max_json_bytes'],'complete metadata extent before terminal audit read')
        path=PurePosixPath(item['path'])
        require(not path.is_absolute() and str(path)==item['path'] and '..' not in path.parts,'canonical relative observed artifact')
        if observed:
            require(item['path'] in self.inventory[role] and
                {k:self.inventory[role][item['path']][k] for k in ('path','bytes','sha256')}==item,
                'same actual complete observed output inventory member')
        raw=self.io.read(self._root(role).rstrip('/')+'/'+item['path'],
                         {k:item[k] for k in ('bytes','sha256')},'outer',maximum=self.cap['max_json_bytes'])
        self._root(role)
        value=json.loads(raw,object_pairs_hook=_pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError('nonfinite JSON token')))
        bounded(value,self.cap);return value

    def compose(self,outer_return,controller_observation):
        fields(outer_return,('path','bytes','sha256','audit_after_cleanup','terminal_boundary'))
        require(not self.used,'one additive terminal audit attempt');self.used=True
        # This equality is checked before the first added audit charge. The
        # bootstrap passes the actual retained finalizer instance and .run return.
        require(outer_return['audit_after_cleanup']==self.io.audit.snapshot(),
                'unchanged retained audit counters after actual successful original outer return')
        original_audit=clone(outer_return['audit_after_cleanup'],self.cap)
        root=self.selected['report_root']['path'];prefix=root.rstrip('/')+'/'
        require(outer_return['path'].startswith(prefix) and '/' not in outer_return['path'][len(prefix):],
                'actual original grade in fixed selected terminal root')
        outer_descriptor={k:outer_return[k] for k in ('path','bytes','sha256')}
        relative={**outer_descriptor,'path':outer_return['path'][len(prefix):]}
        outer=self._read(relative,'report',observed=False)
        require(outer['schema']=='n079_source_owned_outer_grade_v1' and outer['complete'] is True and
                outer['closed_snapshot']['state']=='closed_scope','actual successful original closed outer artifact')
        closed=self._read(outer['closed_scope_evidence'],'report',observed=False)
        require(outer['closed_snapshot']['raw_evidence_pin']=={k:outer['closed_scope_evidence'][k] for k in ('bytes','sha256')},
                'original exact closed physical evidence pin')
        require(controller_observation==closed['roles']['controller'],'same actual controller observation inside original closed evidence')
        grader=closed['roles']['grader']
        require(outer['grader_return']==grader and outer['grade']==grader['index'] and
                outer['grader_output_inventory']==grader['products'],'unchanged complete original grader observation')
        for role,observation in (('controller',controller_observation),('grader',grader)):
            require(observation['role']==role and observation['wait']['natural_zero'] is True and
                    observation['terminal']['role']==role,'actual completed observed source role')
            rows=observation['products'];self.inventory[role]={r['path']:r for r in rows}
            require(len(rows)==len(self.inventory[role]),'unique complete observed product paths')
        controller=self._read(controller_observation['index']['descriptor'],'controller')
        require(controller==controller_observation['index']['body'],'same observed controller index body')
        fields(controller,('schema','source_pin','study_pin','candidate_index','native_index','candidate_counts','native_jobs'))
        require(controller['schema']=='n079_complete_controller_index_v1' and controller['study_pin']==self.selected['study_pin'],
                'actual complete observed controller study')
        numerical_descriptor=grader['index']['descriptor']
        numeric=self._read(numerical_descriptor,'grader')
        require(numeric==grader['index']['body'],'original actual numerical grade unchanged')
        candidates=self._read(controller['candidate_index'],'controller')
        require(candidates['schema']=='n079_complete_candidate_programme_v1' and
            candidates['counts']=={'bundles':36,'queries':3672,'reports':36,'person_video_predictions':22032},'complete actual candidate programme')
        records=candidates['report_evidence']
        require(type(records) is dict and set(records)==set(self.selected['bundle_ids']),'all36 actual private report prefixes in observed controller output')
        panels={row['id']:row for row in candidates['consolidated']}
        require(len(candidates['consolidated'])==36 and set(panels)==set(records),'all36 actual consolidated report objects')
        trusted={};reports={};joins=[]
        for key in self.selected['bundle_ids']:
            self.io.clock.tick('outer')
            receipt=records[key];fields(receipt,('public','private','snapshot','admission'))
            private=self._read(receipt['private'],'controller')
            fields(private,('schema','snapshot','admission','public','bundle_id','bundle_alias','source_pin','study_pin','derived'))
            require(private['schema']=='n079_report_private_evidence_v1' and private['bundle_id']==key and
                    private['study_pin']==self.selected['study_pin'] and private['snapshot']==receipt['snapshot'] and
                    private['public']==receipt['public'] and private['admission']==receipt['admission'],
                    'same actual admitted own-bundle prefix receipt')
            snapshot=self._read(private['snapshot'],'controller');_validate_snapshot(snapshot)
            public_input=self._read(snapshot['public_input'],'controller')
            for cost in snapshot['cost_records']:
                validate_cost_prefix(self._read(cost,'controller'),key,snapshot['program']['body']['policy_id'],
                                     self.selected['study_pin'],self.cap)
            derived=derive(snapshot,public_input,[],self.cap)
            require(private['derived']==derived,'private trusted derivation recomputed from actual observed snapshot')
            public=self._read(private['public'],'controller')
            require(public==derived['public'],'actual pre-report public projection unchanged')
            panel=panels[key]
            require(_seal(panel['fit_record'])==snapshot['fitted'],'same actual sealed fit before and after report')
            require([q['video_id'] for q in panel['queries']]==list(QUERY),'all102 actual reported queries')
            for before,after in zip(snapshot['queries'],panel['queries']):
                row=after['record']
                expected={'video_id':after['video_id'],**{k:row[k] for k in ('prediction','closure','view_evidence','job')},
                          'source_seal':_seal(row['source_seal'])}
                require(before==expected,'exact unchanged own prediction before and after report')
            report=self._read(panel['report_object'],'controller')
            require(report==panel['report_record']['report'] and panel['report_record']==candidates['reports'][key],
                    'actual captured ordinary report body/source/closure join')
            alias=private['bundle_alias'];require(alias not in trusted,'unique opaque report alias')
            reports[alias]=report;trusted[alias]=derived['trusted']
            joins.append({'bundle_alias':alias,'private_evidence':receipt['private'],'pre_report_snapshot':private['snapshot'],
                'public_metadata':private['public'],'report_object':panel['report_object'],
                'post_report_capture':{'job':panel['report_record']['job'],'closure':panel['report_record']['closure'],
                                       'source_seal':_seal(panel['report_record']['source_seal'])},
                'report_costs':'retained in unchanged original closed observer/controller evidence; never inserted into earlier report body'})
        from n079_report_rubric import study_reports
        self.io.audit.charge({'validation_calls':36},'all36 fixed12-item report validations','outer')
        report_result=study_reports(reports,trusted)
        result={'schema':'n079_additive_report_result_v1','source_pin':self.selected['source_pin'],'study_pin':self.selected['study_pin'],
            'original_outer':{'object':outer_descriptor,'actual_return':outer_return},
            'original_controller':{'object':controller_observation['index']['descriptor'],
                'closed_scope_evidence':outer['closed_scope_evidence'],'observation_pin':ident(controller_observation,self.cap)},
            'original_numerical_grade':{'object':numerical_descriptor,'unchanged':True,'separate_endpoint':True,
                'original_output_inventory':grader['products']},
            'report_quality':report_result,'actual_report_joins':joins,'complete_benchmark_admitted':False,
            'scientific_qualification_added':False,'endpoint_qualification_gap':report_result['endpoint_qualification_gap'],
            'audit_before_report_composition':original_audit,'audit_before_additive_publication':self.io.audit.snapshot(),
            'terminal_boundary':'same original finalizer audit allocation/clock; common physical scope is already closed and excludes finalizer; no new whole-scope physical measurement',
            'holds':['Unassessable items retain0 contribution to fixed12/432 denominator and are not observed incorrect answers.',
                     'No scientific-reasoning accuracy claim under incomplete observability.',
                     'All original numeric/source/custody/physical/native/scientific dispositions remain in the unchanged outer result.']}
        from n079_outer_common import open_directory
        raw=bounded(result,self.cap);root_path=self._root('report');fd=open_directory(root_path);error=None
        try:
            st=os.fstat(fd);require({'device':st.st_dev,'inode':st.st_ino}==self.selected['report_root']['identity'],'same terminal publication directory')
            ordinary=self.io.write(fd,self.selected['output_name'],raw,'outer')
        except BaseException as exc:error=exc;raise
        finally:
            try:os.close(fd)
            except BaseException as exc:
                if error is None:raise
                error.add_note('additive terminal directory close failed: '+type(exc).__name__)
        # Explicit terminal boundary avoids a recursive self-accounting hash.
        written=self._read(ordinary,'report',observed=False)
        require(written==result,'actual complete additive artifact reread')
        self.io.clock.tick('outer')
        return {'index':{**ordinary,'path':root_path.rstrip('/')+'/'+ordinary['path']},
                'audit_after_publication':self.io.audit.snapshot(),
                'terminal_boundary':'post-publication original finalizer counters; physical common scope remains closed'}
