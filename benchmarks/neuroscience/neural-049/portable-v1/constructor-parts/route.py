# Source fragment3: actual generic qualification, V-only one-path publication/state.
VERIFICATION_FIELDS={'status','receipt_path','receipt_sha256','qualification_path','qualification_sha256','source_binding_path','source_binding_sha256'}
QUALIFICATION_ORIGINAL='authoring/delivery-20261105/common/campaign-exposure-capacity-successor-v1/tools/neurobench_campaign.py'

def _generic(io,instance):
    root=instance['root'];inventory=instance['immutable']
    q=io.read(root/'shared/qualification.py',inventory['shared/qualification.py'],readonly=True)
    p=io.read(root/'shared/launch_parser.py',inventory['shared/launch_parser.py'],readonly=True)
    parser=types.ModuleType('_neural049_original_python_parser');parser.__file__=str(root/'shared/launch_parser.py')
    io.tick();exec(compile(p,parser.__file__,'exec'),parser.__dict__);io.tick()
    base=types.ModuleType('_neural049_original_generic_qualification');base.__file__=str(root/'origin'/QUALIFICATION_ORIGINAL)
    io.tick();exec(compile(q,base.__file__,'exec'),base.__dict__);io.tick()
    base._campaign_module=lambda unused_root=root:parser
    return base,parser

def _verification(value,evidence,root):
    exact(value,VERIFICATION_FIELDS,'original verification fields');need(value['status']=='passed','actual external qualification required')
    for prefix in ('receipt','qualification','source_binding'):
        path=value[prefix+'_path'];relative_path(path)
        need(Path(path).parent.as_posix()==Q_REL,'all route evidence direct Q child')
        name=Path(path).name;need(name.endswith('.json'),'metadata evidence extension');token(name[:-5])
        need(path in evidence and evidence[path]['sha256']==value[prefix+'_sha256'],'typed registered evidence pin')
    return value

def _generic_check(io,instance,base,parser,doc,kind,evidence):
    root=instance['root'];meta=doc['program_execution']
    expected_wrapper=SCORE_REL if kind=='grade' else 'central/entry.py'
    entry=meta['entrypoint'];idx=parser.python_launch(entry['argv'])
    need(idx==1 and entry['argv']==instance['selection_body']['registered_templates'][kind]
         and entry['argv'][idx]==expected_wrapper and entry['sha256']==instance['immutable'][expected_wrapper]['sha256']
         and entry['working_directory']=='.','actual original parser/template/source join')
    need(meta['source_freeze']=={'path':'central/QUALIFICATION_SOURCE_FREEZE.json',**instance['freeze']['pin']},'exact complete freeze descriptor')
    _verification(meta['verification'],evidence,root)
    need(instance['source_freeze']['files']=={p:instance['immutable'][p] for p in instance['source_freeze']['files']},'all109 exact dependency pins')
    G=4*(2097152+1)+2*(16777216+1)+sum(x['bytes']+1 for x in instance['source_freeze']['files'].values())
    io.reserve_read(G,'actual original generic qualification conservative full maximum')
    io.unobserved_external_read_reservations=getattr(io,'unobserved_external_read_reservations',0)+G
    io.tick();passed=base.verified_program_runtime(root/J_REL,doc,root);io.tick()
    need(passed is True,'actual unchanged generic helper must pass')
    return {'kind':kind,'reserved_read_maximum':G,'direct_helper_actual_bytes':'not instrumented; reservation retained'}

def _route_static_unchanged(old,new):
    x=copy.deepcopy(new);y=copy.deepcopy(old)
    for z in (x,y):
        z['program_execution']['verification']=None
        z['program_conditions'][PROFILE]['verification']=None
        z['protected_grading_execution']['verification']=None
        z['verification']=None;z['admission']['runnable']=False
    need(typed_equal(x,y),'only explicit route verification/runnable fields may change')
    need(new['admission']['scientifically_qualified'] is False and new['status']=='source_only_unqualified','no scientific/status promotion')

def _apply_routes(current,routes):
    new=copy.deepcopy(current)
    new['program_execution']['verification']=copy.deepcopy(routes['default'])
    new['program_conditions'][PROFILE]['verification']=copy.deepcopy(routes['named'])
    if routes['grade'] is not None:
        new['protected_grading_execution']['verification']=copy.deepcopy(routes['grade']['program'])
        new['verification']=copy.deepcopy(routes['grade']['scoring']);new['admission']['runnable']=True
    else:
        new['protected_grading_execution']['verification']={'status':'not_run','reason':'Protected grading source route is not qualified by this selection.'}
        new['verification']={'status':'not_run'};new['admission']['runnable']=False
    _route_static_unchanged(current,new)
    return new

def bind_route(io,build_descriptor,input_descriptor):
    request=read_descriptor(io,input_descriptor)
    exact(request,{'schema','registry_state','name','routes','evidence'},'bind route input')
    need(request['schema']=='neural049_portable_bind_route_v1','bind route schema');name=token(request['name'])
    instance=load_instance(io,build_descriptor,request['registry_state']);root=instance['root'];v=root/V_REL
    need(not (v/(name+'-transaction.json')).exists() and not (v/(name+'-registry.json')).exists(),'fresh generation namespace')
    routes=request['routes'];exact(routes,{'default','named','grade'},'all route conditions')
    supplied=request['evidence'];need(type(supplied) is dict and 1<=len(supplied)<=32,'bounded externally issued route evidence set')
    captured={};pins={}
    for basename,d in supplied.items():
        need(type(basename) is str and basename.endswith('.json'),'route evidence JSON names');token(basename[:-5]);descriptor(d)
        path=canonical_path(d['path']);need(root not in path.parents,'external evidence input outside instance')
        raw=io.read(path,d['pin'],cap=2097152,readonly=True);parse_json(raw)
        rel=Q_REL+'/'+basename;captured[rel]=raw;pins[rel]=d['pin']
    for kind in ('default','named'):_verification(routes[kind],pins,root)
    if routes['grade'] is not None:
        exact(routes['grade'],{'program','scoring'},'grade proof pair');_verification(routes['grade']['program'],pins,root)
        score=routes['grade']['scoring'];exact(score,{'status','receipt_path','receipt_sha256'},'separate scoring receipt')
        need(score['status']=='passed' and score['receipt_path'] in pins and score['receipt_sha256']==pins[score['receipt_path']]['sha256'],'score receipt exact Q pin')
        terminal=parse_json(captured[score['receipt_path']])
        need(terminal.get('candidate_id')==TASK and terminal.get('status')=='passed' and type(terminal.get('returncode')) is int
             and terminal['returncode']==0 and terminal.get('source_freeze_sha256')==instance['freeze']['pin']['sha256'],'separate grade terminal/freeze join')
    for rel,raw in captured.items():
        if (root/rel).exists():io.read(root/rel,pins[rel],readonly=True)
        else:io.put(root/rel,raw)
    new=_apply_routes(instance['registry_document'],routes)
    base,parser=_generic(io,instance);checks=[]
    checks.append(_generic_check(io,instance,base,parser,new,'default',pins))
    checks.append(_generic_check(io,instance,base,parser,{**new,'program_execution':new['program_conditions'][PROFILE]},'named',pins))
    if routes['grade'] is not None:checks.append(_generic_check(io,instance,base,parser,{**new,'program_execution':new['protected_grading_execution']},'grade',pins))
    # Actual live J and every immutable source remain current after helper direct reads.
    load_instance(io,build_descriptor,request['registry_state'])
    generation=io.put(v/(name+'-registry.json'),new,cap=131072)
    transaction={'schema':'neural049_portable_registry_transaction_v1','instance':instance['instance'],
                 'old_registry':instance['registry_state']['current_registry'],'new_registry':generation['pin'],'source_freeze':instance['freeze'],
                 'allowed_path':str(root/J_REL),'state':'prepared','qualified_evidence':{'inputs':pins,'checks':checks},
                 'generation':generation,'old_state':request['registry_state'],'name':name}
    tx=io.put(v/(name+'-transaction.json'),transaction)
    return {'transaction':tx,'generation':generation,'registry_state':request['registry_state'],'costs':io.record()}

def _publication_geometry(io,instance):
    root=instance['root'];v=root/V_REL;j=root/J_REL
    io.tick();io._parents(v);io._parents(j)
    a=os.lstat(v);b=os.lstat(j.parent)
    need(stat.S_ISDIR(a.st_mode) and stat.S_ISDIR(b.st_mode) and a.st_dev==b.st_dev,'same-device V/J-parent atomic publication')
    return v,j,_directory_identity(a),_directory_identity(b)

def activate_route(io,build_descriptor,input_descriptor):
    request=read_descriptor(io,input_descriptor);exact(request,{'schema','registry_state','transaction'},'activation input')
    need(request['schema']=='neural049_portable_activate_route_v1','activation schema')
    instance=load_instance(io,build_descriptor,request['registry_state']);root=instance['root'];v,j,vid,jpid=_publication_geometry(io,instance)
    publication_parents=io._parents(v)
    descriptor(request['transaction']);need(canonical_path(request['transaction']['path']).parent==v,'transaction in exact V')
    tx=read_descriptor(io,request['transaction']);exact(tx,{'schema','instance','old_registry','new_registry','source_freeze','allowed_path','state','qualified_evidence','generation','old_state','name'},'transaction positive fields')
    name=token(tx['name'])
    need(tx['schema']=='neural049_portable_registry_transaction_v1' and tx['state']=='prepared' and tx['instance']==instance['instance']
         and tx['source_freeze']==instance['freeze'] and tx['allowed_path']==str(j) and tx['old_state']==request['registry_state']
         and tx['old_registry']==instance['registry_state']['current_registry'],'transaction exact old instance/state/registry')
    descriptor(tx['generation']);need(canonical_path(tx['generation']['path'])==v/(name+'-registry.json') and tx['generation']['pin']==tx['new_registry'],'fixed generation identity')
    new_raw=io.read(tx['generation']['path'],tx['new_registry'],cap=131072,readonly=True)
    _route_static_unchanged(instance['registry_document'],parse_json(new_raw))
    # Re-run actual original predicates on the actual proposed bytes, not transaction booleans.
    evidence=tx['qualified_evidence']['inputs'];base,parser=_generic(io,instance);new=parse_json(new_raw)
    _generic_check(io,instance,base,parser,new,'default',evidence)
    _generic_check(io,instance,base,parser,{**new,'program_execution':new['program_conditions'][PROFILE]},'named',evidence)
    if new['protected_grading_execution']['verification']['status']=='passed':
        scoring=new['verification'];exact(scoring,{'status','receipt_path','receipt_sha256'},'separate scoring receipt')
        need(scoring['status']=='passed' and scoring['receipt_path'] in evidence and scoring['receipt_sha256']==evidence[scoring['receipt_path']]['sha256'],'actual scoring evidence pin')
        terminal=io.json(root/scoring['receipt_path'],evidence[scoring['receipt_path']],cap=2097152,readonly=True)
        need(terminal.get('candidate_id')==TASK and terminal.get('status')=='passed' and type(terminal.get('returncode')) is int and terminal['returncode']==0 and terminal.get('source_freeze_sha256')==instance['freeze']['pin']['sha256'],'actual scoring terminal/freeze')
        _generic_check(io,instance,base,parser,{**new,'program_execution':new['protected_grading_execution']},'grade',evidence)
    lock=v/'ACTIVATION.lock';need(not os.path.lexists(lock),'abandoned/active lock requires separate inspection')
    lock_d=io.put(lock,{'schema':'neural049_portable_activation_lock_v1','transaction':request['transaction'],'old_state':request['registry_state']})
    lock_id=_stamp(os.lstat(lock));staged=v/(name+'-staged.json')
    facts={'schema':'neural049_portable_activation_v1','status':'entered_incomplete','transaction':request['transaction'],
           'instance':instance['instance'],'old_state':request['registry_state'],'old_registry':tx['old_registry'],'new_registry':tx['new_registry'],
           'rename_returned':False,'v_synced':False,'j_parent_synced':False,'readback_pin':None,'lock':lock_d,
           'closure_path':str(v/(name+'-closed.json')),'automatic_retry':False}
    try:
        io.put(staged,new_raw,cap=131072)
        io.read(j,tx['old_registry'],cap=131072,readonly=True)
        # All fixed sources/state remain exact while this invocation owns the global lock.
        load_instance(io,build_descriptor,request['registry_state'])
        need(_directory_identity(os.lstat(v))==vid and _directory_identity(os.lstat(j.parent))==jpid and _stamp(os.lstat(lock))==lock_id,'publication namespace and lock custody')
        io.tick();os.replace(staged,j);io.operations+=1;facts['rename_returned']=True;io.tick()
        io.sync_dir(v);facts['v_synced']=True;io.sync_dir(j.parent);facts['j_parent_synced']=True
        io.read(j,tx['new_registry'],cap=131072,readonly=True);facts['readback_pin']=tx['new_registry'];io.tick()
        facts['status']='observed_complete';facts['costs_before_publication']=io.record()
        observation=io.put(v/(name+'-activation.json'),facts)
        state=copy.deepcopy(instance['registry_state']);state.update({'current_registry':tx['new_registry'],'predecessor_state':request['registry_state'],'activation':observation})
        state_d=io.put(v/(name+'-state.json'),state)
        # Retain exact owned lock bytes before releasing only that still-owned namespace.
        io.put(v/(name+'-lock-history.json'),io.read(lock,lock_d['pin'],readonly=True))
        need(_stamp(os.lstat(lock))==lock_id,'release only original owned lock');io.tick();os.unlink(lock);io.operations+=1;io.tick();io.sync_dir(v)
        closed=io.put(v/(name+'-closed.json'),{'schema':'neural049_portable_activation_closure_v1','status':'observed_complete',
                 'activation':observation,'registry_state':state_d,'lock_released_and_v_synced':True,'registry':tx['new_registry']})
        # No remembered current-J cache advances before the actual successful bounded observation.
        verified=load_instance(io,build_descriptor,state_d);need(verified['registry_state']['current_registry']==tx['new_registry'],'post-activation full invariant check')
        instance['registry_state']=verified['registry_state'];instance['registry_state_descriptor']=state_d
        io.tick();return {'activation':observation,'closure':closed,'registry_state':state_d,'registry':tx['new_registry'],'costs':io.record()}
    except BaseException as error:
        io.later.append(_error(error,'activation partial/unknown publication; retain V artifacts'))
        try:
            need(_directory_identity(os.lstat(v))==vid and _directory_identity(os.lstat(j.parent))==jpid,'failure publication namespace remains owned')
            io._check_parents(publication_parents)
            io.put(v/(name+'-failure.json'),{'schema':'neural049_portable_activation_failure_v1','facts':facts,'error':_error(error,'activation'),'costs':io.record(),'automatic_retry':False})
        except BaseException as later:io.later.append(_error(later,'activation failure receipt'))
        raise
