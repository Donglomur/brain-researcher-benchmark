"""Closed postscore role content and exact original authority subjects.

Pure ordinary-metadata functions: no reads, model calls, signing, token charging,
processes or numerical scoring. Captured bodies are supplied by the controller.
"""
import re
from .common import require, keys, integer, finite, descriptor, parse, encoded, sha

ROLES=('author','reviewer_1','reviewer_2','adjudicator')
COMPARISONS=('C01','C02','C03','C04')
ALL_CONTRASTS=tuple('C%02d'%i for i in range(1,33))
RUBRIC=('estimand_and_access','training_selection_calibration','paired_quantitative_evidence',
        'control_interpretation','uncertainty_failure_multiplicity','reproducible_supported_limitations')
METRICS=('assignment_accuracy','independent_accuracy','NLL','Brier','Top5','assignment_minus_independent')
POLICY='same_current_blinded_aggregate_no_prediction_feedback_no_retry_v1'
ANCHORS={'0':'absent_or_incorrect','1':'partly_correct_material_omission','2':'complete_and_supported'}
RESOURCE_FIELDS=('cpu_seconds','read_bytes','write_bytes','files','stream_bytes','model_calls')
RESOURCE_WORDING='Compared under the same prospectively selected measured resource envelopes; native cumulative logical I/O and native file churn were not measured.'
SETUP_WORDING='full standalone setup plus own work; physical unique-operation ledger separate'
CELL_STATUSES=('complete_valid','complete_valid_calibration_uninformative','safe_failed','blocked_unresolved_containment','reference_unqualified','mode_compliance_unqualified','unattempted_after_failure')
CONTRAST_BYTES=7938
CONTRAST_SHA256='b5b24650a8288272cd4642bb76bb68ffead79b1c116a5f7c43062874925d2411'
REQUEST_FIELDS=('schema','resource_policy','postscore_resource_policy','source','campaign','original_origin',
    'original_deadline','postscore_deadline','clock_domain','created','sequence','role','actor','actor_source',
    'aggregate','input','rubric','policy','comparisons','result_not_known_before_request',
    'maximum_original_operation_resources','input_namespace','token_reservation','memory_limit_bytes')
RESULT_SCHEMAS={'author':'neural055-current-scientific-report-v1',
    'reviewer_1':'neural055-current-interpretation-judgment-v1',
    'reviewer_2':'neural055-current-interpretation-judgment-v1',
    'adjudicator':'neural055-current-interpretation-adjudication-v1'}


def text(value):
    require(type(value) is str and bool(value.strip()) and '\x00' not in value,'nonempty ordinary text')
    value.encode('utf-8')
    return value


def digest(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None,'SHA256 identity')
    return value


def copy(value):
    """Plain immutable-byte roundtrip; rejects nonfinite or non-JSON objects."""
    return parse(encoded(value))


def resource_identity(value,version=None):
    keys(value,('version','bytes','sha256'));text(value['version']);integer(value['bytes'],1);digest(value['sha256'])
    require(version is None or value['version']==version,'selected resource semantics')


def rubric(value):
    require(value=={'dimensions':list(RUBRIC),'anchors':ANCHORS},'exact original six-dimension rubric')


def admit_output_policy(value):
    keys(value,('schema','model_payload','maximum_context_bytes','maximum_response_bytes','maximum_result_bytes'))
    require(value['schema']=='neural055-postscore-role-output-policy-v2' and value['model_payload']=='comparison_content_only','fixed role output policy')
    for key,ceiling in (('maximum_context_bytes',1048576),('maximum_response_bytes',8388608),('maximum_result_bytes',16777216)):
        integer(value[key],1,ceiling)
    return value


def admit_service(value,role,selected_service,runtime_source):
    """Validate a controller-captured manifest; capture/qualification remain outside."""
    keys(value,('schema','identity','role','runtime_source','code','provider','prompt','output_policy','deployment'))
    require(value['schema']=='neural055-postscore-role-service-v2' and role in ROLES and value['role']==role,'selected role service')
    text(value['identity']);digest(value['runtime_source'])
    keys(selected_service,('identity','source','qualification'))
    for name in ('source','qualification'):descriptor(selected_service[name]);integer(selected_service[name]['bytes'],1)
    require(value['identity']==selected_service['identity'] and value['runtime_source']==runtime_source,'exact selected service/runtime')
    keys(value['code'],('dispatcher','role_adapter'))
    for item in value['code'].values():descriptor(item);integer(item['bytes'],1)
    keys(value['provider'],('kind','id','model_manifest','config','qualification','model_directory'))
    require(value['provider']['kind']=='local_transformers_text_v1','selected existing local text transport')
    require(type(value['provider']['id']) is str and re.fullmatch('[a-z][a-z0-9_]{0,47}',value['provider']['id']) is not None,'explicit provider ID')
    for name in ('model_manifest','config','qualification'):descriptor(value['provider'][name]);integer(value['provider'][name]['bytes'],1)
    directory=text(value['provider']['model_directory'])
    require(directory.startswith('/') and all(p not in ('.','..') for p in directory.split('/')),'explicit absolute local model root; physical admission remains controller-owned')
    for name in ('prompt','deployment'):descriptor(value[name]);integer(value[name]['bytes'],1)
    admit_output_policy(value['output_policy'])
    return copy(value)


def admit_request(value):
    keys(value,REQUEST_FIELDS)
    require(value['schema']=='neural055-postscore-operation-request-v2','prospective v2 request only')
    role=value['role'];require(role in ROLES and type(value['sequence']) is int and value['sequence']==ROLES.index(role),'fixed original role order')
    for name in ('source','campaign'):digest(value[name])
    for name in ('actor','clock_domain'):text(value[name])
    for name in ('actor_source','aggregate','input'):descriptor(value[name]);integer(value[name]['bytes'],1)
    for name in ('original_origin','original_deadline','postscore_deadline','created'):finite(value[name])
    require(value['original_origin']<=value['created']<value['postscore_deadline']<=value['original_deadline'],'same original request interval')
    resource_identity(value['resource_policy'],'n055-measured-envelopes-v1')
    resource_identity(value['postscore_resource_policy'],'neural055-postscore-resources-v2')
    rubric(value['rubric'])
    require(value['policy']==POLICY and value['comparisons']==list(COMPARISONS) and value['result_not_known_before_request'] is True,'original current scientific policy')
    require(value['input_namespace']=='exact files in this journal; no other journal or protected input is an actor capability','closed input capability boundary')
    resources=value['maximum_original_operation_resources'];keys(resources,RESOURCE_FIELDS)
    for key,n in resources.items():
        finite(n);require(n>=0,'nonnegative remaining operation resources')
        if key!='cpu_seconds':integer(n)
    reservation=value['token_reservation']
    keys(reservation,('scope','maximum_input','maximum_output','status','usage'))
    require(reservation['scope']=='current_postscore_operation' and reservation['status']=='reserved_before_dispatch' and reservation['usage'] is None,'existing unsettled request token reservation')
    integer(reservation['maximum_input'],1);integer(reservation['maximum_output'],1);integer(value['memory_limit_bytes'],1)
    if role=='author':require(value['input']==value['aggregate'],'author receives aggregate only')
    return value


def captured(raw,pin,cap):
    descriptor(pin);integer(pin['bytes'],1,cap)
    require(type(raw) is bytes and len(raw)==pin['bytes'] and sha(raw)==pin['sha256'],'exact authorized input bytes')
    return parse(raw)


def ratings(value):
    keys(value,('scores','reasons','rationale'));keys(value['scores'],RUBRIC);keys(value['reasons'],RUBRIC)
    require(all(type(x) is int and x in (0,1,2) for x in value['scores'].values()),'six exact ordinal integers; no booleans')
    for reason in value['reasons'].values():text(reason)
    text(value['rationale'])


def comparison_content(value,role,comparison_ids):
    keys(value,('comparisons',));keys(value['comparisons'],comparison_ids)
    for row in value['comparisons'].values():
        if role=='author':
            keys(row,('machine_interpretation','scientific_report'))
            require(type(row['machine_interpretation']) is dict,'original machine interpretation object')
            copy(row['machine_interpretation']);text(row['scientific_report'])
        else:ratings(row)
    return value


def validate_result(value,role,aggregate,*,report=None,reviewer=None,judgments=(),comparison_ids=COMPARISONS):
    require(role in ROLES,'closed role')
    fields=['schema','aggregate','comparisons']
    if role!='author':fields+=['report','reviewer']
    if role=='adjudicator':fields+=['judgments']
    keys(value,fields)
    require(value['schema']==RESULT_SCHEMAS[role] and value['aggregate']==aggregate,'exact original result/aggregate binding')
    if role!='author':
        text(reviewer);require(value['reviewer']==reviewer and value['report']==report,'exact selected reviewer/report')
    if role=='adjudicator':require(value['judgments']==list(judgments),'ordered original judgments')
    comparison_content({'comparisons':value['comparisons']},role,comparison_ids)
    return value


def _extended(value):
    require(type(value) is dict,'extended scalar')
    if value.get('status')=='undefined':
        keys(value,('status','reason'));require(value['reason']=='infinite_minus_infinite','original undefined scalar')
    else:
        keys(value,('status','value'))
        require(value['status'] in ('finite','positive_infinity','negative_infinity'),'extended scalar status')
        if value['status']=='finite':finite(value['value'])
        else:require(value['value'] is None,'nonfinite value is explicitly unavailable')


def _interval(value):
    keys(value,('point','person','crossed_person_image','interpretation'));_extended(value['point'])
    for axis in ('person','crossed_person_image'):
        keys(value[axis],('percentile_2_5','percentile_97_5','valid_draws'))
        finite(value[axis]['percentile_2_5']);finite(value[axis]['percentile_97_5'])
        require(value[axis]['valid_draws']==10000,'full frozen paired schedule')
    require(value['interpretation']=='conditional sensitivity of fixed outputs; no population or validated familywise coverage claim','unchanged interval interpretation')


def _metric(value):
    if 'person' in value:_interval(value)
    else:
        keys(value,('point','interval_status','reason'));_extended(value['point'])
        require(value['interval_status']=='unavailable' and value['reason']=='extended_infinite_loss','original unavailable absolute metric')


def _condition(value):
    require(type(value) is list and len(value)==4,'aggregate condition')
    require(value[0] in ('R0','R1','R2','R3','CANDIDATE') and value[1] in ('F','I','REFERENCE') and value[2] in ('T0','T1','REFERENCE') and value[3] in ('FULL','IMAGE_ONLY','PRE_ONLY','POST_ONLY','ALIGN_SHUFFLE'),'closed blinded condition axes')
    require((value[1] in ('F','I') and value[2] in ('T0','T1')) if value[0]=='CANDIDATE' else value[1:3]==['REFERENCE','REFERENCE'],'source-owned condition combinations')


def aggregate_context(value,request):
    """Validate the source-owned safe shape; omit only provenance identities."""
    keys(value,('schema','source','campaign','numerical_report_identity','conditions','unavailable_conditions','contrasts',
        'resource_policy','resource_interpretation','schedule_draws','replicate_aggregation','comparison_ids','limitations',
        'private_targets_query_maps_cell_outputs_excluded','system_identity_blinding'))
    require(value['schema']=='neural055-current-safe-interpretation-aggregate-v1' and value['source']==request['source'] and value['campaign']==request['campaign'],'current source/campaign safe aggregate')
    keys(value['numerical_report_identity'],('bytes','sha256'));integer(value['numerical_report_identity']['bytes'],1);digest(value['numerical_report_identity']['sha256'])
    require(value['resource_policy']==request['resource_policy'],'same selected resource identity')
    require(value['resource_interpretation']==RESOURCE_WORDING,'source-owned resource interpretation')
    require(value['schedule_draws']==10000 and value['replicate_aggregation']=='mean before paired draws' and value['comparison_ids']==list(COMPARISONS),'full paired context')
    require(value['limitations']=={'one_public_dataset':True,'whole_paper_noncoverage':True,'population_pvalues':None,'open_scientific_gates':30,'scientific_qualification_claim':False},'original limitations retained')
    require(value['private_targets_query_maps_cell_outputs_excluded'] is True and value['system_identity_blinding']=='structural alias plus separately required independent procedural qualification','source-owned safe projection')
    require(type(value['conditions']) is list and type(value['unavailable_conditions']) is list,'complete condition lists')
    seen=set()
    for row in value['conditions']:
        keys(row,('condition','metrics'));_condition(row['condition']);keys(row['metrics'],METRICS)
        key=tuple(row['condition']);require(key not in seen,'duplicate condition');seen.add(key)
        for metric in row['metrics'].values():_metric(metric)
    for row in value['unavailable_conditions']:
        keys(row,('condition','required_cells','missing_status_counts','status'));_condition(row['condition'])
        key=tuple(row['condition']);require(key not in seen,'duplicate unavailable condition');seen.add(key)
        integer(row['required_cells'],1);require(row['status']=='unavailable' and type(row['missing_status_counts']) is dict,'original unavailable status')
        for status,count in row['missing_status_counts'].items():
            require(status in CELL_STATUSES,'closed original cell status');integer(count,1)
        require(0<sum(row['missing_status_counts'].values())<=row['required_cells'],'nonempty bounded missing support')
    expected={('CANDIDATE',m,t,a) for m in ('F','I') for t in ('T0','T1') for a in ('FULL','IMAGE_ONLY','PRE_ONLY','POST_ONLY','ALIGN_SHUFFLE')}
    expected.update((r,'REFERENCE','REFERENCE',a) for r in ('R0','R1','R2','R3') for a in ('FULL','IMAGE_ONLY','PRE_ONLY','POST_ONLY','ALIGN_SHUFFLE'))
    require(seen==expected,'all40 original condition dispositions; no selected subset')
    rows=value['contrasts'];require(type(rows) is list and [r['id'] for r in rows]==list(ALL_CONTRASTS),'all ordered32 contrast rows required')
    projected=[]
    for row in rows:
        keys(row,('id','status'),('reason','paired','joint_conditional_band','exploratory_secondary','qualification_dependencies','qualified_joint_family_disposition'))
        require(row['status'] in ('available','unavailable'),'contrast availability')
        require('joint_conditional_band' in row and 'qualification_dependencies' in row and 'qualified_joint_family_disposition' in row,'whole source-owned numerical/resource context')
        if row['status']=='available':
            require('paired' in row and 'reason' not in row,'complete available primary contrast')
            require(('exploratory_secondary' in row)==(row['id'] not in ('C29','C30','C31','C32')),'exact original secondary comparison domain')
        else:require('reason' in row and 'paired' not in row and 'exploratory_secondary' not in row,'unavailable contrast carries no numerical result')
        if 'reason' in row:require(row['reason']=='required_complete_condition_unavailable','original unavailable reason')
        if 'paired' in row:_interval(row['paired'])
        if 'joint_conditional_band' in row:
            band=row['joint_conditional_band']
            if 'status' in band:
                require(band=={'status':'unavailable','reason':'at_least_one_required_member_of_full32_family_unavailable'},'full32 band unavailable disposition')
            else:
                keys(band,('person','crossed_person_image'))
                for item in band.values():
                    keys(item,('lower','upper','full_family','quantile','validated_familywise_coverage'))
                    for name in ('lower','upper','quantile'):finite(item[name])
                    require(item['full_family']==32 and item['validated_familywise_coverage'] is False,'conditional full-family band')
        if 'exploratory_secondary' in row:
            keys(row['exploratory_secondary'],('independent_accuracy','NLL','Brier','Top5'))
            for name,item in row['exploratory_secondary'].items():
                keys(item,('point','favorable_direction','exploratory'),('paired','interval_status'));_extended(item['point'])
                require(item['exploratory'] is True and item['favorable_direction']==('negative; lower loss' if name in ('NLL','Brier') else 'positive; higher accuracy'),'original exploratory meaning')
                if 'paired' in item:_interval(item['paired'])
                if 'interval_status' in item:require(item['interval_status']=='unavailable_extended_or_undefined_loss','secondary unavailable status')
                require(('paired' in item)!=('interval_status' in item),'one complete secondary disposition')
        out=copy(row)
        if 'qualification_dependencies' in row:
            q=row['qualification_dependencies']
            keys(q,('resource_policy','numerical_availability','semantic_mode_qualification','measured_resource_comparison_qualification','interpretation','setup_attribution','native_cumulative_io_and_churn','same_allowances_not_same_consumption','required_cell_count'))
            require(q['resource_policy']==request['resource_policy'],'same qualification resource policy')
            require(q['numerical_availability'] in ('available','unavailable') and q['semantic_mode_qualification'] in ('qualified','unavailable') and q['measured_resource_comparison_qualification'] in ('qualified','unavailable'),'original qualification dispositions')
            require(q['interpretation']==RESOURCE_WORDING and q['setup_attribution']==SETUP_WORDING,'source-owned qualification interpretation')
            integer(q['required_cell_count'],1,960)
            require(q['numerical_availability']==row['status'],'same numerical availability')
            require(q['native_cumulative_io_and_churn']=='unobserved_by_selected_observer' and q['same_allowances_not_same_consumption'] is True,'no total-I/O implication')
            out['qualification_dependencies']['resource_policy']={'version':q['resource_policy']['version']}
        if 'qualified_joint_family_disposition' in row:
            q=row['qualified_joint_family_disposition'];keys(q,('status','required_family','reason','raw_numerical_band_retained_separately','validated_familywise_coverage'))
            require(q['status'] in ('available_conditional_only','unavailable') and q['required_family']==32 and q['raw_numerical_band_retained_separately'] is True and q['validated_familywise_coverage'] is False,'full qualified family meaning')
            require(q['reason'] is None or q['reason']=='at_least_one_required_numerical_semantic_or_measured_resource_dependency_unavailable','source family reason')
            require((q['reason'] is None)==(q['status']=='available_conditional_only'),'same family availability/reason')
        projected.append(out)
    context={k:copy(v) for k,v in value.items() if k not in ('source','campaign','numerical_report_identity','resource_policy','contrasts')}
    context['resource_policy']={'version':value['resource_policy']['version']};context['contrasts']=projected
    return context


def model_output_schema(role,comparison_ids):
    require(role in ROLES and comparison_ids and set(comparison_ids)<=set(COMPARISONS),'selected output comparisons')
    def obj(properties):return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
    nonempty={'type':'string','minLength':1}
    item=obj({'machine_interpretation':{'type':'object'},'scientific_report':nonempty}) if role=='author' else obj({
        'scores':obj({k:{'type':'integer','enum':[0,1,2]} for k in RUBRIC}),
        'reasons':obj({k:nonempty for k in RUBRIC}),'rationale':nonempty})
    return obj({'comparisons':obj({key:copy(item) for key in comparison_ids})})


def render_role(request,service_manifest,prompt_bytes,aggregate_bytes,*,contrast_registry_bytes,
                report_bytes=None,judgment_bytes=(),adjudication_input_bytes=None,reviewer_identities=()):
    admit_request(request);role=request['role'];service=service_manifest;limits=admit_output_policy(service['output_policy'])
    require(service['role']==role and service['identity']==request['actor'] and service['runtime_source']==request['source'],'current selected service')
    descriptor(service['prompt']);require(type(prompt_bytes) is bytes and len(prompt_bytes)==service['prompt']['bytes'] and sha(prompt_bytes)==service['prompt']['sha256'],'exact selected prompt')
    prompt=text(prompt_bytes.decode('utf-8'))
    require(type(contrast_registry_bytes) is bytes and len(contrast_registry_bytes)==CONTRAST_BYTES and sha(contrast_registry_bytes)==CONTRAST_SHA256,'exact original full32 definition source')
    registry=parse(contrast_registry_bytes)
    aggregate=captured(aggregate_bytes,request['aggregate'],16777216)
    context={'schema':'neural055-postscore-model-context-v2','role':role,'selected_instructions':prompt,
        'aggregate':aggregate_context(aggregate,request),'contrast_definitions':registry,
        'rubric':copy(request['rubric'])}
    report_pin=None;judgment_pins=[];comparison_ids=list(COMPARISONS)
    if role=='author':
        require(report_bytes is None and not judgment_bytes and adjudication_input_bytes is None and not reviewer_identities,'author has no reports or reviews')
    elif role in ('reviewer_1','reviewer_2'):
        require(not judgment_bytes and adjudication_input_bytes is None and not reviewer_identities,'reviewers cannot see the other review')
        report_pin=request['input']
    else:
        require(type(reviewer_identities) in (tuple,list) and len(reviewer_identities)==2 and len(set(reviewer_identities))==2 and request['actor'] not in reviewer_identities,'two precommitted distinct reviewer identities')
        for ident in reviewer_identities:text(ident)
        adjudication=captured(adjudication_input_bytes,request['input'],16777216)
        require(encoded(adjudication)==adjudication_input_bytes,'original journal canonical adjudication bytes')
        keys(adjudication,('schema','aggregate','report','judgments','comparisons','rubric'))
        require(adjudication['schema']=='neural055-current-adjudication-input-v1' and adjudication['aggregate']==request['aggregate'] and adjudication['rubric']==request['rubric'],'original current adjudication input')
        report_pin=adjudication['report'];judgment_pins=adjudication['judgments']
        require(type(judgment_pins) is list and len(judgment_pins)==2 and len(judgment_bytes)==2 and judgment_pins[0]!=judgment_pins[1],'two ordered original judgment captures')
        reviews=[]
        for i,(raw,p) in enumerate(zip(judgment_bytes,judgment_pins)):
            result=captured(raw,p,16777216)
            validate_result(result,'reviewer_'+str(i+1),request['aggregate'],report=report_pin,reviewer=reviewer_identities[i])
            reviews.append(result)
        comparison_ids=[c for c in COMPARISONS if reviews[0]['comparisons'][c]['scores']!=reviews[1]['comparisons'][c]['scores']]
        require(comparison_ids and adjudication['comparisons']==comparison_ids,'exact score-vector disagreements only')
        context['judgments']=[{'reviewer':'reviewer_'+str(i+1),'comparisons':copy(value['comparisons'])} for i,value in enumerate(reviews)]
    if report_pin is not None:
        report=captured(report_bytes,report_pin,16777216);validate_result(report,'author',request['aggregate'])
        context['report']={'comparisons':copy(report['comparisons'])}
    context['required_comparisons']=comparison_ids;context['output_schema']=model_output_schema(role,comparison_ids)
    content=encoded(context)
    require(len(content)<=limits['maximum_context_bytes'],'complete role context unavailable within selected byte cap; never truncate')
    authorized={'request_sha256':sha(encoded(request)),'role':role,'aggregate':copy(request['aggregate']),
        'report':copy(report_pin),'judgments':copy(judgment_pins),'comparisons':list(comparison_ids),
        'reviewer':None if role=='author' else request['actor']}
    return {'messages':[{'role':'user','content':content.decode('utf-8')}],
        'authorized_inputs':authorized,'response_contract':model_output_schema(role,comparison_ids),
        'request_identity':sha(encoded(request)),'context_bytes':len(content),
        'token_fit':'actual selected provider tokenizer must measure complete context including its selected system prompt; no truncation or retry'}


def bind_result(request,model_output_bytes,authorized_inputs,output_policy):
    admit_request(request);limits=admit_output_policy(output_policy);a=authorized_inputs
    keys(a,('request_sha256','role','aggregate','report','judgments','comparisons','reviewer'))
    require(a['request_sha256']==sha(encoded(request)) and a['role']==request['role'] and a['aggregate']==request['aggregate'],'same current trusted rendering context')
    role=request['role'];comparison_ids=a['comparisons']
    require(type(comparison_ids) is list and comparison_ids and comparison_ids==[c for c in COMPARISONS if c in comparison_ids],'canonical selected comparisons')
    require(role=='adjudicator' or comparison_ids==list(COMPARISONS),'all four author/reviewer comparisons')
    require(type(model_output_bytes) is bytes and 0<len(model_output_bytes)<=limits['maximum_response_bytes'],'bounded one-shot original model output')
    value=parse(model_output_bytes);comparison_content(value,role,comparison_ids)
    result={'schema':RESULT_SCHEMAS[role],'aggregate':copy(a['aggregate']),'comparisons':copy(value['comparisons'])}
    if role=='author':require(a['report'] is None and not a['judgments'] and a['reviewer'] is None,'author trusted binding')
    else:
        require(a['reviewer']==request['actor'],'selected reviewer identity')
        descriptor(a['report']);result.update(report=copy(a['report']),reviewer=request['actor'])
        if role in ('reviewer_1','reviewer_2'):require(a['report']==request['input'] and not a['judgments'],'reviewer exact original report')
    if role=='adjudicator':
        require(type(a['judgments']) is list and len(a['judgments'])==2,'ordered adjudication judgment pins')
        for item in a['judgments']:descriptor(item)
        adjudication={'schema':'neural055-current-adjudication-input-v1','aggregate':a['aggregate'],
            'report':a['report'],'judgments':a['judgments'],'comparisons':comparison_ids,'rubric':request['rubric']}
        original=encoded(adjudication)
        require(len(original)==request['input']['bytes'] and sha(original)==request['input']['sha256'],'trusted adjudication metadata reconstructs exact original request input')
        result['judgments']=copy(a['judgments'])
    validate_result(result,role,a['aggregate'],report=a['report'],reviewer=a['reviewer'],judgments=a['judgments'],comparison_ids=comparison_ids)
    raw=encoded(result);require(len(raw)<=limits['maximum_result_bytes'],'complete original bound result exceeds selected cap')
    return result


def service_subject(source,service,policy,resource_policy):
    """Exact original pre-exposure subject; no enclosing policy or own receipt hash."""
    digest(source);keys(service,('identity','source','qualification'));text(service['identity']);descriptor(service['source'])
    require(policy['policy']==POLICY,'same scientific policy');rubric(policy['rubric']);text(policy['clock_domain'])
    for k in ('memory_bytes','maximum_input_tokens','maximum_output_tokens'):integer(policy[k],1)
    resource_identity(resource_policy)
    return copy({'source':source,'service_identity':service['identity'],'service_source':service['source'],
        'policy':policy['policy'],'rubric':policy['rubric'],'clock_domain':policy['clock_domain'],'resource_policy':resource_policy,
        'operation_limits':{k:policy[k] for k in ('memory_bytes','maximum_input_tokens','maximum_output_tokens')}})


def blinded_report_subject(source,campaign,aggregate,report,reviewer_identities):
    digest(source);digest(campaign);descriptor(aggregate);descriptor(report)
    require(type(reviewer_identities) in (list,tuple) and len(reviewer_identities)==2 and len(set(reviewer_identities))==2,'two distinct actual reviewers')
    for item in reviewer_identities:text(item)
    return copy({'source':source,'campaign':campaign,'aggregate':aggregate,'report':report,'reviewers':list(reviewer_identities)})


def operation_subject(source,campaign,original_origin,policy,request_pin,response,aggregate,input_descriptor,service):
    """Exact original shape. Only operation qualification is excluded from payload."""
    digest(source);digest(campaign);finite(original_origin)
    for item in (request_pin,aggregate,input_descriptor):descriptor(item)
    keys(service,('identity','source','qualification'));text(service['identity'])
    fields=('schema','role','request_sha256','actor','actor_source','result','original_operation')
    role=response['role'];require(role in ROLES,'closed response role')
    keys(response,(*fields,'blinding_qualification') if role=='author' else fields,('qualification',))
    require(response['schema']=='neural055-postscore-operation-response-v2' and response['request_sha256']==request_pin['sha256'] and response['actor']==service['identity'] and response['actor_source']==service['source'],'current v2 response binding')
    for name in ('result','original_operation'):descriptor(response[name])
    if role=='author':descriptor(response['blinding_qualification'])
    return copy({'source':source,'campaign':campaign,'original_origin':original_origin,'policy':sha(encoded(policy)),
        'request':request_pin,'response_payload':{k:v for k,v in response.items() if k!='qualification'},
        'aggregate':aggregate,'input':input_descriptor,'actor':service,'result':response['result'],
        'original_operation':response['original_operation']})
