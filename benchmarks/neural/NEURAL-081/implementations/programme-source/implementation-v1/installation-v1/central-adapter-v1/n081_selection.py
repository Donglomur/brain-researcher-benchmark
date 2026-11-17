"""Protected metadata-only selection, complete clock/cost and custody joins."""
import resource,re
from pathlib import Path
import common as c
import custody

REVIEW_KEYS=('schema','task_id','condition','central_source','parent_source','parent_proposal','registry','program','run','campaign','origin','normal_endpoint','central_limits','total_limits','external_limits','memory','roots','launch','qualification')

def discovered(path,cap,budget):
    """Fixed operator metadata only; no guessed operand or recursive inventory."""
    p=c.absolute(str(path));size=p.lstat().st_size;c.integer(size,1,cap)
    # First bounded capture establishes a pin; exact recapture prevents races.
    import n081_shared_gate as gate
    budget.charge('read_bytes',cap+1);raw=gate.capture(p,cap)
    return c.parse(raw),{'path':str(p),**c.pin(raw)}

def review_document(args,ctx,registry):
    boot=ctx['bootstrap'];root=ctx['here']/'operator-selections';path=c.absolute(args.review)
    c.need(path.parent==root and path.suffix=='.json'and path.name!='APPROVAL_REGISTRY.json','fixed protected review directory')
    review,descriptor=discovered(path,32768,boot);c.exact(review,REVIEW_KEYS)
    c.need(review['schema']=='neural081_central_review_v1'and review['task_id']==c.TASK and review['condition']==args.condition,'complete current central review')
    for k,v in [('central_source',ctx['source']),('parent_source',ctx['parent_source']),('parent_proposal',ctx['bindings']['parent_proposal']),('registry',registry['descriptor'])]:c.need(c.typed_equal(review[k],v),'review exact '+k)
    c.descriptor(review['program']);c.descriptor(review['run']);c.need(review['program']['path']==args.program,'exact selected complete execution envelope')
    c.exact(review['campaign'],('request','work_sha256'));c.descriptor(review['campaign']['request']);c.digest(review['campaign']['work_sha256'])
    c.need(type(review['origin'])is float and type(review['normal_endpoint'])is float,'retain exact original float clock')
    c.finite(review['origin'],0);c.finite(review['normal_endpoint'],0)
    c.need(review['origin']<=boot.started<review['normal_endpoint'],'bootstrap is within selected original interval')
    c.exact(review['roots'],('operator','protected','secret','raw'))
    for values in review['roots'].values():c.need(type(values)is list and values and len(values)<=32,'complete nonempty bounded custody roots')
    output=c.absolute(args.output)
    c.need(not output.is_relative_to(ctx['repo'])and not ctx['repo'].is_relative_to(output),'fresh external output distinct from source repository')
    allroots=[output,*[c.absolute(v)for values in review['roots'].values()for v in values]];custody.disjoint_roots([str(v)for v in allroots])
    c.need(not output.exists(),'fresh one-shot central result root')
    c.exact(review['memory'],('address_space_bytes','readback_live_bytes','metadata_cap_bytes','other_reserve_bytes'))
    mem=review['memory'];c.integer(mem['address_space_bytes'],512*2**20,256*2**30);c.integer(mem['readback_live_bytes'],64*2**20,mem['address_space_bytes']);c.integer(mem['metadata_cap_bytes'],32768,mem['readback_live_bytes']//8);c.integer(mem['other_reserve_bytes'],0)
    c.need(type(args.other_reserve_bytes)is str and str(int(args.other_reserve_bytes))==args.other_reserve_bytes and int(args.other_reserve_bytes)==mem['other_reserve_bytes'],'literal separately selected memory reservation')
    c.need(mem['readback_live_bytes']+mem['other_reserve_bytes']+512*2**20<=mem['address_space_bytes'],'separate source/bootstrap/readback/other memory envelopes')
    c.exact(review['launch'],('python','parent_entry','cwd','host_environment','credential_name','inherited_address_space_bytes'))
    c.need(c.typed_equal(review['launch']['parent_entry'],ctx['parent']['entry'])and review['launch']['cwd']=='/'and review['launch']['inherited_address_space_bytes']==mem['address_space_bytes'],'genuine entry and explicit inherited OS limit')
    c.absolute(review['launch']['python']);environment=review['launch']['host_environment'];c.exact(environment,('PATH','PYTHONDONTWRITEBYTECODE'))
    c.need(type(environment['PATH'])is str and environment['PATH']and '\0'not in environment['PATH']and environment['PYTHONDONTWRITEBYTECODE']=='1','clean source-selected host environment')
    c.need(type(review['launch']['credential_name'])is str and re.fullmatch('[A-Z][A-Z0-9_]{0,127}',review['launch']['credential_name']),'literal bounded qualified credential name')
    # Qualification is issued before this review and binds its complete payload
    # except the qualification descriptor. The independently protected registry
    # is issued afterward and approves the exact review; no hash cycle.
    qdesc=c.descriptor(review['qualification']);c.need(Path(qdesc['path']).parent==root and qdesc['bytes']<=65536,'fixed protected qualification metadata')
    qualification=c.parse(boot.capture(qdesc,65536));c.exact(qualification,('schema','status','selected_actual','issuer','binding','capabilities'))
    expected={k:v for k,v in review.items()if k!='qualification'}
    c.need(qualification['schema']=='neural081_central_launch_qualification_v1'and qualification['status']=='qualified'and qualification['selected_actual']is True and c.typed_equal(qualification['binding'],expected),'independently issued whole selection qualification')
    capabilities={'physical_root_disjointness':True,'operator_namespace_immutable':True,'single_credential_boundary':True,'actual_linux_procfs_observer':True,'parent_and_central_interpreters':True,'complete_graph_readback_resources':True,'inherited_address_space_limit':True,'independent_central_exit_observer_required':True,'statistical_semantic_reviewer':False}
    c.need(c.typed_equal(qualification['capabilities'],capabilities),'complete selected deployment capabilities, no semantic reviewer')
    approvals,approval_desc=discovered(root/'APPROVAL_REGISTRY.json',131072,boot)
    c.exact(approvals,('schema','selected_actual','allowed_issuers','reviews'))
    c.need(approvals['schema']=='neural081_protected_central_approvals_v1'and approvals['selected_actual']is True and type(approvals['allowed_issuers'])is list and qualification['issuer']in approvals['allowed_issuers'],'independent protected operator-channel trust anchor')
    c.need(type(approvals['reviews'])is dict and c.typed_equal(approvals['reviews'].get(descriptor['sha256']),{'review':descriptor,'qualification':qdesc}),'independent exact review approval')
    budget=c.Budget(review['origin'],review['central_limits']);c.need(budget.end==review['normal_endpoint'],'unchanged original central deadline')
    budget.charge('read_bytes',boot.used);budget.charge('host_processes',1)
    for key in('native_cpu_seconds','native_processes','provider_requests','provider_tokens','tool_processes'):c.need(budget.limits[key]==0,'central adds no scientific/native/provider operation')
    c.need(budget.limits['host_processes']==1,'exactly one additional central host')
    soft,hard=resource.getrlimit(resource.RLIMIT_AS);c.need(hard==resource.RLIM_INFINITY or hard>=mem['address_space_bytes'],'selected host address-space capacity')
    resource.setrlimit(resource.RLIMIT_AS,(mem['address_space_bytes'],hard))
    ctx['budget']=budget;ctx['review']=review;ctx['review_desc']=descriptor;ctx['approval_desc']=approval_desc;ctx['qualification']=qualification
    return review,budget

class MetadataGuard:
    """Every parent metadata capture keeps the selected private/raw deny boundary."""
    def __init__(self,ctx,output):
        self.ctx=ctx;self.review=ctx['review'];self.base_capture=c.capture
        roots=self.review['roots'];self.denied=[c.absolute(x)for key in('protected','secret','raw')for x in roots[key]]
        self.allowed=[c.absolute(output),*[c.absolute(x)for x in roots['operator']],ctx['here']/'operator-selections']
        self.sources=set(ctx['bodies']);self.maximum=self.review['memory']['metadata_cap_bytes']
    def admit(self,desc,empty=False):
        c.descriptor(desc,empty);p=c.absolute(desc['path'])
        c.need(not any(p==r or p.is_relative_to(r)or r.is_relative_to(p)for r in self.denied),'no protected/raw/credential body in central process')
        c.need(p.as_posix()in self.sources or any(p.is_relative_to(r)for r in self.allowed),'selected exact source or operator metadata namespace')
        c.need(desc['bytes']<=self.maximum,'preventive per-object metadata extent before capture')
        c.need(p.as_posix()in self.sources or(p.suffix in('.json','.txt')and not p.name.endswith('-labels.json')and p.name!='PERSON_PROTECTED.json'),'metadata only, no numerical/model/training-label body')
    def capture(self,desc,budget,roots,*,empty=False):
        self.admit(desc,empty);return self.base_capture(desc,budget,roots,empty=empty)
    def protect(self,descriptors):
        for d in descriptors:c.descriptor(d);self.denied.append(c.absolute(d['path']))

def bind_envelope(ctx,args,review,budget):
    guard=MetadataGuard(ctx,args.output);c.capture=guard.capture;ctx['guard']=guard
    envelope=c.capture_json(review['program'],budget,[Path(review['program']['path']).parent]);run=c.capture_json(review['run'],budget,[Path(review['run']['path']).parent])
    c.need(c.typed_equal(envelope['source_manifest'],ctx['parent_source'])and c.typed_equal(envelope['controller']['run'],review['run']),'same original parent/run descriptors')
    config=envelope['controller'];c.need(envelope['outer_output']==str(Path(args.output)/'parent-outer')and config['output_root']==str(Path(args.output)/'parent-controller'),'source-owned original output geometry')
    c.need(c.typed_equal(config['protected_roots'],review['roots']['protected']),'complete selected protected-root boundary')
    c.need(run['origin']==review['origin']and type(run['origin'])is float and run['normal_endpoint']==review['normal_endpoint']and type(run['normal_endpoint'])is float,'exact original parent clock')
    import authority
    authority.run_allocation(run,budget)
    for field in('total_limits','external_limits'):
        c.exact(review[field],('seconds',*budget.limits));c.need(c.typed_equal(review[field]['seconds'],review['central_limits']['seconds']),'same whole interval for all allocations')
        for key in budget.limits:c.integer(review[field][key])
    for key,value in budget.limits.items():c.need(review['total_limits'][key]>=run['whole_limits'][key]+value+review['external_limits'][key],'complete parent+central+external resource allocation')
    c.need(review['total_limits']['host_processes']>=4+review['external_limits']['host_processes'],'four task hosts plus explicit external orchestration')
    ctx['envelope']=envelope;ctx['run']=run
    return envelope,run

def parent_authority(ctx):
    import outer
    review=ctx['review'];budget=ctx['budget'];envelope=ctx['envelope'];config=envelope['controller']
    selected,conditions=outer.admit_launch(envelope,review['program'],ctx['parent_source'],ctx['parent_files'],ctx['run'],budget)
    launch=review['launch'];c.need(c.typed_equal(conditions['observer'].get('entry'),launch['parent_entry'])and c.typed_equal(envelope['controller_entry'],launch['parent_entry']),'actual original entry authority')
    c.need(conditions['observer'].get('host_python')==config['host_python']==launch['python']and c.typed_equal(conditions['observer'].get('host_environment'),config['host_environment'])and c.typed_equal(config['host_environment'],launch['host_environment']),'same independently qualified clean environment')
    c.need(c.typed_equal(conditions['provider'].get('configuration'),config['provider_config']),'exact original provider metadata authority')
    provider=c.capture_json(config['provider_config'],budget,[Path(config['provider_config']['path']).parent]);name=provider['api_key_env']
    c.need(type(name)is str and name==conditions['provider'].get('launch_credential_name')==launch['credential_name']and name not in launch['host_environment'],'one metadata-bound credential name before value access')
    budget.check_clock();return name

def recheck_selection(ctx):
    for desc in(ctx['review_desc'],ctx['approval_desc'],ctx['review']['qualification']):c.capture(desc,ctx['budget'],[Path(desc['path']).parent])
    c.need(c.typed_equal(c.capture_json(ctx['review']['program'],ctx['budget'],[Path(ctx['review']['program']['path']).parent]),ctx['envelope']),'same final envelope before launch')
    c.need(c.typed_equal(c.capture_json(ctx['review']['run'],ctx['budget'],[Path(ctx['review']['run']['path']).parent]),ctx['run']),'same original run before launch')
    return parent_authority(ctx)
