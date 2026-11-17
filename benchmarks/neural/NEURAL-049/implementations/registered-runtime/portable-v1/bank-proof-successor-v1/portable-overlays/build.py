# Source fragment2: complete immutable source instance construction/admission.
LAYOUT_CANONICAL_SHA='fb0881ee2616017f079f402218de2f2f2b956c5b55b38c83019cd6edf9baed08'
ORIGIN_MAP_PIN={'bytes':100847,'sha256':'1ef7cbe8500fee76e88deefe331a838c72fc4e48620bedb0da53273e21a7d3eb'}
ORIGINAL_PARENT_MANIFEST_PIN={'bytes': 10356, 'sha256': '1344647cfff641c7682ced4ddf0f66a03607094b4544b8352a73c77a7d50b954'}
PARENT_MANIFEST_PIN={'bytes': 10356, 'sha256': '6585fe967ebf845ee3b089b603970d69548ba4116dc8360035a413648dfd5ddd'}
PORTABLE_ROLES={'central/entry.py','central/routing.py','central/dispatch.py','central/portable_gate.py','constructor/neural049_instance.py','shared/stage_launcher.py','parent/program/authority.py','parent/program/bank.py','parent/RUNTIME_SOURCE_V3.json'}
CENTRAL_NAMES={'entry.py','routing.py','dispatch.py','portable_gate.py','io.py','readback.py','BINDINGS.json'}
LOCAL_GATE_LIMITS={'single_pass_read_bound':6*(131072+1),'two_pass_read_bound':12*(131072+1),'body_bytes':131072,'review_bytes':32768,'route_evidence_bytes':2097152,'evidence_count':32}
STATE_FIELDS={'schema','instance','source_manifest','parent_manifest','source_freeze','declaration','current_registry','predecessor_state','activation'}

def _dir(io,root,relative):
    relative_path(relative);p=root
    for part in relative.split('/'):
        p=p/part
        if not p.exists():io.mkdir(p)
        else:need(p.is_dir() and not p.is_symlink(),'ordinary selected build directory')
    return p

def _publish(io,root,relative,value,inventory,cap=2097152):
    relative_path(relative);_dir(io,root,str(Path(relative).parent)) if '/' in relative else None
    d=io.put(root/relative,value,cap=cap);inventory[relative]=d['pin'];return d

def _template(source,condition='default',grade=False):
    return ['{python}',SCORE_REL if grade else 'central/entry.py','--operation','grade' if grade else 'collect',
            '--panel','review' if grade else PROFILE,'--condition',condition,'--program','{program}','--output','{output}',
            '--review','{review}','--other-reserve-bytes','{other_reserve_bytes}','--source-bytes',str(source['bytes']),'--source-sha256',source['sha256']]

def _registry(original,root,source,freeze,selection,construction,entry_pin,parent_pin):
    # Preserve only explicitly selected original scientific fields; no old installation identity.
    keep={'schema_version','id','track','title','scientific_scope','counting_unit','complete_support'}
    need(keep<=set(original) and original['id']==TASK,'original canonical registry geometry')
    result={k:copy.deepcopy(original[k]) for k in keep}
    result.update({'status':'source_only_unqualified','admission':{'runnable':False,'scientifically_qualified':False},
                   'verification':{'status':'not_run'},'parent_source':{'path':'parent/RUNTIME_SOURCE_V3.json','pin':parent_pin},
                   'portable_instance':{'construction':construction,'selection':selection}})
    preferred={'path':'central','source':{'path':'central/SOURCE_MANIFEST.json',**source}}
    def meta(argv):return {'entrypoint':{'argv':argv,'sha256':entry_pin['sha256'],'working_directory':'.'},
                          'full_panel':PROFILE,'preferred_source_interface':preferred,
                          'source_freeze':{'path':'central/QUALIFICATION_SOURCE_FREEZE.json',**freeze['pin']},
                          'verification':{'status':'not_run','reason':'Local source constructed; execution and scientific qualifications remain unverified.'}}
    result['program_execution']=meta(_template(source))
    result['program_conditions']={PROFILE:meta(_template(source,PROFILE))}
    result['protected_grading_execution']=meta(_template(source,grade=True))
    score=_template(source,grade=True);score[score.index('{program}')]='{submission}'
    result['entrypoints']={'score':{'argv':score,'sha256':entry_pin['sha256'],'working_directory':'.'}}
    return result

def _profile(io,profile,root,requirements):
    exact(profile,{'schema','instance_name','root','external_operator_metadata_root','selected_profile','requested_modules','cache_preference','unresolved','construction_limits'},'build profile fields')
    need(profile['schema']=='neural049_portable_build_profile_v1' and profile['selected_profile']==PROFILE,'selected full profile')
    token(profile['instance_name']);need(canonical_path(profile['root'])==root,'exact selected output root');modules(profile['requested_modules'])
    need(type(profile['cache_preference']) is bool,'explicit intended cache preference')
    exact(profile['construction_limits'],{'read_cap','write_cap','live_cap'},'construction caps')
    need(typed_equal(profile['construction_limits'],{k:getattr(io,k) for k in ('read_cap','write_cap','live_cap')}),'profile cannot reset caps')
    p=canonical_path(profile['external_operator_metadata_root']);io._parents(p)
    need(p!=root and root not in p.parents and p not in root.parents,'external protected metadata root outside instance')
    need(type(profile['unresolved']) is list and len(profile['unresolved'])==len(requirements),'complete unresolved requirement inventory')
    names=[]
    for item in profile['unresolved']:
        exact(item,{'name','status','reason','role'},'unresolved slot fields');token(item['name'])
        need(item['status']=='missing' and type(item['reason']) is str and item['reason'] and type(item['role']) is str,'unresolved slots are never qualified')
        names.append(item['name'])
    need(len(names)==len(set(names)) and set(names)=={r['name'] for r in requirements},'exact unresolved names')
    return p

def build_instance(io,release_descriptor,public_root,root,profile_descriptor):
    descriptor(release_descriptor);descriptor(profile_descriptor);root=canonical_path(root);public_root=canonical_path(public_root)
    release_path=canonical_path(release_descriptor['path']);release_base=release_path.parent
    need(root!=public_root and root not in public_root.parents and public_root not in root.parents,'fresh output disjoint public source')
    need(root!=release_base and root not in release_base.parents and release_base not in root.parents,'output disjoint portable release')
    release_raw=io.read(release_path,release_descriptor['pin'],readonly=True);release=parse_json(release_raw)
    exact(release,{'schema','task_id','profile','public_origin_map','public_files','portable_sources','variant_pairs','context_order','source_layout','requirements'},'release fields')
    need(release['schema']=='neural049_portable_release_v1' and release['task_id']==TASK and release['profile']==PROFILE,'portable release identity')
    layout=release['source_layout'];need(hashlib.sha256(encode(layout).rstrip(b'\n')).hexdigest()==LAYOUT_CANONICAL_SHA,'exact accepted109 source layout')
    rows=layout['files'];need(len(rows)==109 and len({x['path'] for x in rows})==109,'full unique active layout')
    originals=[x for x in rows if x['kind']=='unchanged_original']
    need(len([x for x in originals if x['path'].startswith('parent/') and x['path']!='parent/RUNTIME_SOURCE_V3.json'])==68,'exact68 unchanged operative parent bodies plus2 variants')
    contexts=[x['path'] for x in rows if x['role']=='scientific_context']
    need(release['context_order']==contexts and len(contexts)==22,'exact22 context order')
    public=release['public_files'];need(type(public) is dict and len(public)==137,'exact137 archive public map')
    for path,pin in public.items():relative_path(path);valid_pin(pin)
    descriptor(release['public_origin_map']);relative_path(release['public_origin_map']['path'])
    need(release['public_origin_map']['pin']==ORIGIN_MAP_PIN,'reviewed original public map pin')
    map_raw=io.read(release_base/release['public_origin_map']['path'],ORIGIN_MAP_PIN,readonly=True);origin_map=parse_json(map_raw)
    need({x['path']:{'bytes':x['bytes'],'sha256':x['sha256']} for x in origin_map['files']}==public,'all137 public identities, no private source-path read')
    need(set(release['portable_sources'])==PORTABLE_ROLES,'exact nine supplied portable source roles')
    for value in release['portable_sources'].values():descriptor(value);relative_path(value['path'])
    variants={x['path']:x for x in rows if x['kind']=='future_reviewed_variant'}
    need(set(release['variant_pairs'])==set(variants),'exact five declared source variant relationships')
    for target,pair in release['variant_pairs'].items():
        exact(pair,{'original','replacement'},'variant pair');need(pair['original']==variants[target]['original'] and pair['replacement']==release['portable_sources'][target]['pin'],'exact original/new variant pins')
    requirements=release['requirements'];need(type(requirements) is list and requirements,'real unresolved requirements')
    for req in requirements:exact(req,{'name','role','reason'},'release requirement');token(req['name'])
    profile=read_descriptor(io,profile_descriptor);operator_metadata=_profile(io,profile,root,requirements)
    total=sum(x['bytes'] for x in public.values())+sum(x['pin']['bytes'] for x in release['portable_sources'].values())
    with io.hold(total*3+8*(len(release_raw)+len(map_raw))+4194304,'all captured source and metadata construction'):
        bodies={path:io.read(public_root/path,pin,cap=max(2097152,pin['bytes']),readonly=False) for path,pin in public.items()}
        portable={target:io.read(release_base/value['path'],value['pin'],cap=max(2097152,value['pin']['bytes']),readonly=True)
                  for target,value in release['portable_sources'].items()}
        for row in originals:need(row['public_path'] in public and public[row['public_path']]==row['original']['pin'],'active original identity')
        parentrow=next(x for x in rows if x['path']=='parent/RUNTIME_SOURCE_V3.json')
        need(parentrow['original']['pin']==ORIGINAL_PARENT_MANIFEST_PIN,'preserved original parent manifest pin')
        original_parent=parse_json(bodies[parentrow['public_path']])
        parent_manifest=parse_json(portable['parent/RUNTIME_SOURCE_V3.json'])
        need(pin_bytes(portable['parent/RUNTIME_SOURCE_V3.json'])==PARENT_MANIFEST_PIN,'exact selected derived parent manifest')
        expected_parent=copy.deepcopy(original_parent);expected_parent['revision']=4
        for name in ('program/authority.py','program/bank.py'):
            expected_parent['files'][name]=release['portable_sources']['parent/'+name]['pin']
        need(typed_equal(parent_manifest,expected_parent),'only2 operative bank-proof variants and declared revision')
        need(len(parent_manifest['files'])==70 and len(parent_manifest['overrides'])==2,'complete parent and original2 overlays')
        parent_members=parent_manifest['files']
        io.claim_root(root);inventory={}
        for path,body in bodies.items():_publish(io,root,'origin/'+path,body,inventory,cap=max(2097152,len(body)))
        for row in originals:_publish(io,root,row['path'],bodies[row['public_path']],inventory,cap=max(2097152,row['original']['pin']['bytes']))
        for target,body in portable.items():_publish(io,root,target,body,inventory,cap=max(2097152,len(body)))
        _publish(io,root,SCORE_REL,portable['central/entry.py'],inventory)
        rel=_publish(io,root,'PORTABLE_RELEASE.json',release_raw,inventory)
        origin=_publish(io,root,'PUBLIC_ORIGIN_MAP.json',map_raw,inventory)
        construction={'schema':'neural049_portable_construction_v1','task_id':TASK,'profile':PROFILE,'root':str(root),
                      'release':relative_descriptor(root,rel),'public_origin_map':relative_descriptor(root,origin),
                      'active_originals':{x['path']:x['original'] for x in originals},'portable_sources':{x:release['portable_sources'][x]['pin'] for x in sorted(PORTABLE_ROLES)},
                      'variant_pairs':release['variant_pairs'],'context':{p:inventory[p] for p in contexts},'parent_overrides':parent_manifest['overrides'],
                      'scope':{'people':12,'days':55,'parent_members':70,'archive_members':137,'active_members':109,'profile':PROFILE},'status':'source_constructed_unqualified'}
        construction_d=_publish(io,root,'CONSTRUCTION.json',construction,inventory)
        earlier={p:pin for p,pin in inventory.items() if not p.startswith('origin/') and not p.startswith('central/') and p!=SCORE_REL}
        need(len(earlier)==100,'exact100 earlier source rows')
        bindings={'schema':'neural049_portable_bindings_v1','parent_root':'parent','parent_manifest':{'path':'parent/RUNTIME_SOURCE_V3.json','pin':PARENT_MANIFEST_PIN},
                  'parent_runtime_members':parent_members,'parent_overrides':parent_manifest['overrides'],'source_rows':earlier,
                  'shared':{'qualification':'shared/qualification.py','launch_parser':'shared/launch_parser.py','stage_launcher':'shared/stage_launcher.py'},
                  'construction':relative_descriptor(root,construction_d),'local_gate_limits':LOCAL_GATE_LIMITS}
        _publish(io,root,'central/BINDINGS.json',bindings,inventory)
        central={'schema':'neural049_portable_central_runtime_source_v1','files':{name:inventory['central/'+name] for name in sorted(CENTRAL_NAMES)}}
        central_d=_publish(io,root,'central/SOURCE_MANIFEST.json',central,inventory)
        active={x['path']:inventory[x['path']] for x in rows};need(len(active)==109 and sum(p['bytes'] for p in active.values())<=16*2**20,'exact active closure/source-capture cap')
        freeze_d=_publish(io,root,'central/QUALIFICATION_SOURCE_FREEZE.json',{'schema':'neural049_portable_source_freeze_v1','task_id':TASK,'files':active},inventory)
        selection={'schema':'neural049_portable_source_selection_v1','task_id':TASK,'profile':PROFILE,'root':str(root),'construction':construction_d,
                   'central_source':central_d['pin'],'parent_source':PARENT_MANIFEST_PIN,'source_freeze':freeze_d,
                   'registered_templates':{'default':_template(central_d['pin']),'named':_template(central_d['pin'],PROFILE),'grade':_template(central_d['pin'],grade=True)},
                   'module_options':['core','T1','D'],'status':'selected_source_only','scientific_qualification':False}
        selection_d=_publish(io,root,'SELECTION.json',selection,inventory)
        registry_key=J_REL if J_REL in bodies else None;need(registry_key is not None,'original scientific registry template supplied')
        registry=_registry(parse_json(bodies[registry_key]),root,central_d['pin'],freeze_d,selection_d,construction_d,inventory['central/entry.py'],PARENT_MANIFEST_PIN)
        _dir(io,root,V_REL);_dir(io,root,Q_REL);_dir(io,root,R_REL)
        generation=_publish(io,root,V_REL+'/initial-registry.json',registry,inventory)
        j=io.put(root/J_REL,encode(registry));need(j['pin']==generation['pin'],'separate exact initial J copy')
        state={'schema':'neural049_portable_registry_state_v1','instance':construction_d,'source_manifest':central_d,
               'parent_manifest':{'path':str(root/'parent/RUNTIME_SOURCE_V3.json'),'pin':PARENT_MANIFEST_PIN},'source_freeze':freeze_d,
               'declaration':selection_d,'current_registry':j['pin'],'predecessor_state':None,'activation':None}
        state_d=_publish(io,root,V_REL+'/initial-state.json',state,inventory)
        req_d=_publish(io,root,'REQUIREMENTS.json',{'schema':'neural049_portable_requirements_v1','status':'unresolved_unqualified',
                      'instance':construction_d,'slots':profile['unresolved'],'scientific_qualification':False},inventory)
        result={'schema':'neural049_portable_build_result_v1','status':'source_constructed_unqualified','root':str(root),'profile':profile,
                'instance':construction_d,'release':rel,'public_origin_map':origin,'central_source':central_d,'parent_source':state['parent_manifest'],
                'source_freeze':freeze_d,'selection':selection_d,'initial_registry_state':state_d,
                'historical_initial_registry':{'generation':generation,'pin':j['pin']},'requirements':req_d,
                'immutable':inventory,'source_counts':{'parent':70,'archive':137,'active':109},'costs_before_this_publication':io.record(),
                'scientific_operation':False,'qualification_generated':False}
        built=io.put(root/'BUILD_RESULT.json',result);io.tick()
        return {'build':built,'result':result,'costs':io.record()}

def _state(io,root,state_d,build,selection_d,freeze_d,instance,central_d,parent_d):
    descriptor(state_d);need(canonical_path(state_d['path']).parent==root/V_REL,'state directly in V')
    state=read_descriptor(io,state_d);exact(state,STATE_FIELDS,'typed registry-state fields')
    need(state['schema']=='neural049_portable_registry_state_v1','state schema')
    invariants={'instance':instance,'source_manifest':central_d,'parent_manifest':parent_d,'source_freeze':freeze_d,'declaration':selection_d}
    for k,v in invariants.items():need(typed_equal(state[k],v),'state immutable invariant '+k)
    valid_pin(state['current_registry'])
    if state['predecessor_state'] is None:
        need(state['activation'] is None and state_d==build['initial_registry_state'] and state['current_registry']==build['historical_initial_registry']['pin'],'exact initial state')
    else:
        descriptor(state['predecessor_state']);descriptor(state['activation'])
        need(canonical_path(state['predecessor_state']['path']).parent==root/V_REL and canonical_path(state['activation']['path']).parent==root/V_REL,'transition evidence confined V')
        old=read_descriptor(io,state['predecessor_state']);exact(old,STATE_FIELDS,'predecessor state fields')
        need(old['schema']=='neural049_portable_registry_state_v1','predecessor schema')
        for k,v in invariants.items():need(typed_equal(old[k],v),'predecessor immutable invariant '+k)
        valid_pin(old['current_registry'])
        a=read_descriptor(io,state['activation']);need(a.get('schema')=='neural049_portable_activation_v1' and a.get('status')=='observed_complete'
              and a.get('new_registry')==state['current_registry'] and a.get('old_state')==state['predecessor_state'] and a.get('old_registry')==old['current_registry'] and a.get('instance')==instance,'actual activation/state join')
        descriptor(a['transaction']);need(canonical_path(a['transaction']['path']).parent==root/V_REL,'transaction direct V')
        tx=read_descriptor(io,a['transaction'])
        need(tx.get('schema')=='neural049_portable_registry_transaction_v1' and tx.get('state')=='prepared' and tx.get('old_state')==state['predecessor_state'] and tx.get('old_registry')==old['current_registry'] and tx.get('new_registry')==state['current_registry'] and tx.get('instance')==instance and tx.get('source_freeze')==freeze_d and tx.get('allowed_path')==str(root/J_REL),'actual retained transaction/state')
        need(a.get('rename_returned') is True and a.get('v_synced') is True and a.get('j_parent_synced') is True and a.get('readback_pin')==state['current_registry'],'complete publication facts')
        cp=canonical_path(a['closure_path']);need(cp.parent==root/V_REL,'closure direct V child')
        closed=io.json(cp,cap=131072,readonly=True)
        need(closed.get('schema')=='neural049_portable_activation_closure_v1' and closed.get('status')=='observed_complete'
             and closed.get('activation')==state['activation'] and closed.get('registry_state')==state_d
             and closed.get('lock_released_and_v_synced') is True and closed.get('registry')==state['current_registry'],'actual state/lock closure')
    current=io.read(root/J_REL,state['current_registry'],cap=131072,readonly=True)
    return state,parse_json(current)

def _immutable_geometry(io,root,build,inventory,release,construction,central,parent,freeze,selection,bindings):
    need(build['scientific_operation'] is False and build['qualification_generated'] is False
         and build['source_counts']=={'parent':70,'archive':137,'active':109},'source-only complete build scope')
    layout=release['source_layout']
    need(hashlib.sha256(encode(layout).rstrip(b'\n')).hexdigest()==LAYOUT_CANONICAL_SHA,'exact accepted source layout on reload')
    rows=layout['files'];active={r['path'] for r in rows}
    need(len(active)==109 and set(freeze['files'])==active,'exact active path membership')
    public=release['public_files'];need(type(public) is dict and len(public)==137,'complete public source archive')
    need(set(inventory)==active|{'origin/'+p for p in public}|{'central/QUALIFICATION_SOURCE_FREEZE.json','SELECTION.json','REQUIREMENTS.json',V_REL+'/initial-registry.json',V_REL+'/initial-state.json'},'exact immutable source/metadata inventory')
    fixed={'instance':'CONSTRUCTION.json','release':'PORTABLE_RELEASE.json','public_origin_map':'PUBLIC_ORIGIN_MAP.json',
           'central_source':'central/SOURCE_MANIFEST.json','parent_source':'parent/RUNTIME_SOURCE_V3.json',
           'source_freeze':'central/QUALIFICATION_SOURCE_FREEZE.json','selection':'SELECTION.json',
           'initial_registry_state':V_REL+'/initial-state.json','requirements':'REQUIREMENTS.json'}
    for key,rel in fixed.items():need(build[key]=={'path':str(root/rel),'pin':inventory[rel]},'fixed build descriptor '+key)
    need(build['parent_source']['pin']==PARENT_MANIFEST_PIN and build['public_origin_map']['pin']==ORIGIN_MAP_PIN,'unchanged parent/map source pins')
    for p,pin in public.items():relative_path(p);valid_pin(pin);need(inventory['origin/'+p]==pin,'exact archived public member')
    origin_map=read_descriptor(io,build['public_origin_map'])
    need({r['path']:{'bytes':r['bytes'],'sha256':r['sha256']} for r in origin_map['files']}==public,'original reviewed public map join')
    originals=[r for r in rows if r['kind']=='unchanged_original']
    for r in originals:need(inventory[r['path']]==public[r['public_path']]==r['original']['pin'],'unchanged active original member')
    need(set(release['portable_sources'])==PORTABLE_ROLES,'exact nine supplied portable roles')
    for path,d in release['portable_sources'].items():descriptor(d);relative_path(d['path']);need(inventory[path]==d['pin'],'portable reviewed body pin')
    need(inventory[SCORE_REL]==inventory['central/entry.py'],'literal score/entry copy')
    need(central=={'schema':'neural049_portable_central_runtime_source_v1','files':{n:inventory['central/'+n] for n in sorted(CENTRAL_NAMES)}},'exact seven-member central manifest')
    members={r['path'][7:]:r['original']['pin'] for r in originals if r['path'].startswith('parent/')}
    need(len(members)==68,'exact unchanged operative parent subset')
    for name in ('program/authority.py','program/bank.py'):
        members[name]=release['portable_sources']['parent/'+name]['pin']
    parentrow=next(r for r in rows if r['path']=='parent/RUNTIME_SOURCE_V3.json')
    original_parent=io.json(root/'origin'/parentrow['public_path'],ORIGINAL_PARENT_MANIFEST_PIN,readonly=True)
    expected_parent=copy.deepcopy(original_parent);expected_parent['revision']=4;expected_parent['files']=members
    need(typed_equal(parent,expected_parent) and len(members)==70 and len(parent['overrides'])==2,'exact original70 with only2 selected variants and revision')
    contexts=[r['path'] for r in rows if r['role']=='scientific_context'];need(release['context_order']==contexts and len(contexts)==22,'exact context order')
    variants={r['path']:r for r in rows if r['kind']=='future_reviewed_variant'}
    need(set(release['variant_pairs'])==set(variants),'exact variant path membership')
    for target,pair in release['variant_pairs'].items():need(pair=={'original':variants[target]['original'],'replacement':inventory[target]},'exact source variant pair')
    expected_construction={'schema':'neural049_portable_construction_v1','task_id':TASK,'profile':PROFILE,'root':str(root),
          'release':relative_descriptor(root,build['release']),'public_origin_map':relative_descriptor(root,build['public_origin_map']),
          'active_originals':{r['path']:r['original'] for r in originals},'portable_sources':{p:inventory[p] for p in sorted(PORTABLE_ROLES)},
          'variant_pairs':release['variant_pairs'],'context':{p:inventory[p] for p in contexts},'parent_overrides':parent['overrides'],
          'scope':{'people':12,'days':55,'parent_members':70,'archive_members':137,'active_members':109,'profile':PROFILE},'status':'source_constructed_unqualified'}
    need(typed_equal(construction,expected_construction),'exact construction declaration')
    earlier={p:inventory[p] for p in active if not p.startswith('central/') and p!=SCORE_REL}
    need(len(earlier)==100,'exact earlier source count')
    need(bindings=={'schema':'neural049_portable_bindings_v1','parent_root':'parent','parent_manifest':{'path':'parent/RUNTIME_SOURCE_V3.json','pin':PARENT_MANIFEST_PIN},
           'parent_runtime_members':members,'parent_overrides':parent['overrides'],'source_rows':earlier,
           'shared':{'qualification':'shared/qualification.py','launch_parser':'shared/launch_parser.py','stage_launcher':'shared/stage_launcher.py'},
           'construction':relative_descriptor(root,build['instance']),'local_gate_limits':LOCAL_GATE_LIMITS},'exact bindings closure')
    need(selection=={'schema':'neural049_portable_source_selection_v1','task_id':TASK,'profile':PROFILE,'root':str(root),'construction':build['instance'],
           'central_source':build['central_source']['pin'],'parent_source':PARENT_MANIFEST_PIN,'source_freeze':build['source_freeze'],
           'registered_templates':{'default':_template(build['central_source']['pin']),'named':_template(build['central_source']['pin'],PROFILE),'grade':_template(build['central_source']['pin'],grade=True)},
           'module_options':['core','T1','D'],'status':'selected_source_only','scientific_qualification':False},'exact fixed selection/routes')
    need(build['historical_initial_registry']=={'generation':{'path':str(root/V_REL/'initial-registry.json'),'pin':inventory[V_REL+'/initial-registry.json']},'pin':inventory[V_REL+'/initial-registry.json']},'historical initial J identity')
    original=io.json(root/'origin'/J_REL,public[J_REL],readonly=True)
    initial=io.json(root/V_REL/'initial-registry.json',inventory[V_REL+'/initial-registry.json'],readonly=True)
    expected=_registry(original,root,build['central_source']['pin'],build['source_freeze'],build['selection'],build['instance'],inventory['central/entry.py'],PARENT_MANIFEST_PIN)
    need(typed_equal(initial,expected),'exact initial inactive registry from original public scientific fields')
    return initial

def _tree_geometry(io,root,inventory):
    allowed=set(inventory)|{J_REL,'BUILD_RESULT.json'};dirs={'.'}
    for path in allowed:
        p=Path(path).parent
        while p.as_posix()!='.':dirs.add(p.as_posix());p=p.parent
    dirs|={Q_REL,R_REL,V_REL};todo=[root];count=0
    while todo:
        directory=todo.pop();io.tick();before=_directory_identity(os.lstat(directory));parents=io._parents(directory)
        with os.scandir(directory) as stream:
            for entry in stream:
                count+=1;need(count<=4096,'bounded instance metadata inventory');io.tick()
                path=Path(entry.path);rel=path.relative_to(root).as_posix();s=entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(s.st_mode):need(rel in dirs,'no undeclared source directories');todo.append(path)
                else:
                    dynamic=path.parent in (root/Q_REL,root/R_REL,root/V_REL)
                    need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and (rel in allowed or dynamic),'ordinary declared source or selected metadata file')
                    if dynamic:need(len(path.name)<=128 and (path.name.endswith('.json') or rel==V_REL+'/ACTIVATION.lock'),'bounded direct metadata filenames')
        need(_directory_identity(os.lstat(directory))==before,'inventory directory custody');io._check_parents(parents);io.tick()

def load_instance(io,build_descriptor,registry_state_descriptor=None):
    build=read_descriptor(io,build_descriptor);need(build.get('schema')=='neural049_portable_build_result_v1' and build.get('status')=='source_constructed_unqualified','complete source build')
    root=canonical_path(build['root']);need(canonical_path(build_descriptor['path'])==root/'BUILD_RESULT.json','fixed BUILD_RESULT path')
    inventory=build['immutable'];need(type(inventory) is dict and len(inventory)<=512,'bounded immutable inventory')
    for rel,pin in inventory.items():relative_path(rel);valid_pin(pin);io.read(root/rel,pin,cap=max(2097152,pin['bytes']),readonly=True)
    release=read_descriptor(io,build['release']);construction=read_descriptor(io,build['instance'])
    central=read_descriptor(io,build['central_source']);parent=read_descriptor(io,build['parent_source'])
    freeze=read_descriptor(io,build['source_freeze']);selection=read_descriptor(io,build['selection'])
    bindings=io.json(root/'central/BINDINGS.json',inventory['central/BINDINGS.json'],readonly=True)
    need(freeze.get('schema')=='neural049_portable_source_freeze_v1' and freeze.get('task_id')==TASK and len(freeze.get('files',{}))==109,'exact source freeze')
    need({k:inventory[k] for k in freeze['files']}==freeze['files'],'freeze inventory join')
    need(len(parent.get('files',{}))==70 and len([p for p in inventory if p.startswith('origin/')])==137,'all70 parent/137 archive identities')
    need(construction['root']==str(root) and construction['status']=='source_constructed_unqualified','construction identity')
    need(selection['construction']==build['instance'] and selection['source_freeze']==build['source_freeze'] and selection['central_source']==build['central_source']['pin'] and selection['parent_source']==build['parent_source']['pin'],'immutable selection joins')
    initial=_immutable_geometry(io,root,build,inventory,release,construction,central,parent,freeze,selection,bindings)
    _tree_geometry(io,root,inventory)
    state_d=registry_state_descriptor or build['initial_registry_state']
    state,registry_doc=_state(io,root,state_d,build,build['selection'],build['source_freeze'],build['instance'],build['central_source'],build['parent_source'])
    _route_static_unchanged(initial,registry_doc)
    need(registry_doc.get('id')==TASK and registry_doc.get('portable_instance')=={'construction':build['instance'],'selection':build['selection']},'current registry instance')
    io.tick()
    return {'root':root,'parent':root/'parent','central':root/'central','operator_metadata':canonical_path(build['profile']['external_operator_metadata_root']),
            'release':release,'construction':construction,'instance':build['instance'],'construction_descriptor':build['instance'],
            'central_source':build['central_source']['pin'],'parent_source':build['parent_source']['pin'],
            'freeze':build['source_freeze'],'selection':build['selection'],'registry':root/J_REL,'registry_document':registry_doc,
            'registry_state':state,'registry_state_descriptor':state_d,'immutable':inventory,'build':build_descriptor,'build_result':build,
            'bindings':bindings,'parent_manifest':parent,'central_manifest':central,'selection_body':selection,'source_freeze':freeze}
