"""Task-local declared development exposure and exact source-route admission.

This module never opens global catalogue/history files or evidence bodies.
Admission is not freshness, input custody, execution or scientific qualification.
"""
import re
import sys
from pathlib import Path
import common as c
import n081_shared_gate as shared

TASK='NEURAL-081'
CONDITIONS=('default','full10_instructed_excerpt_v1')
REQUEST_CAP=131072
SELECTION_CAP=131072

def _budget(ctx):
    return ctx['budget'] if 'budget' in ctx else ctx['bootstrap']

def _read(ctx,desc,maximum,expected_path=None,operator=False):
    c.descriptor(desc);c.integer(desc['bytes'],1,maximum);p=c.absolute(desc['path'])
    if expected_path is not None:c.need(p==expected_path,'exact fixed local metadata path before open')
    if operator:
        roots=ctx['review']['roots']
        denied=[c.absolute(v)for k in('raw','secret','protected')for v in roots[k]]
        allowed=[ctx['here']/'operator-selections',*[c.absolute(v)for v in roots['operator']]]
        c.need(not any(p==r or p.is_relative_to(r)or r.is_relative_to(p)for r in denied),'protected operand cannot be a declaration')
        c.need(any(p.is_relative_to(r)for r in allowed)and p.suffix=='.json'and not p.name.endswith('-labels.json')and p.name!='PERSON_PROTECTED.json','selected metadata-only declaration path before open')
    budget=_budget(ctx);budget.charge('read_bytes',desc['bytes']+1)
    raw=shared.capture(p,desc['bytes'],{k:desc[k]for k in('bytes','sha256')});budget.check_clock()
    return shared.metadata(raw),len(raw)+1

def template(ctx,condition):
    c.need(type(condition)is str and condition in CONDITIONS,'one complete local route')
    return ['{python}','-I','-S','-B','-X','pycache_prefix='+str(ctx['here']/'fresh-central-pycache'),str((ctx['here']/'entry.py').relative_to(ctx['repo'])),'--condition',condition,'--program','{program}','--output','{output}','--review','{review}','--other-reserve-bytes','{other_reserve_bytes}','--source-bytes',str(ctx['source']['bytes']),'--source-sha256',ctx['source']['sha256']]

def read_selection(ctx,descriptor):
    """Read only the fixed local selection and its exact complete source map."""
    selected,used=_read(ctx,descriptor,SELECTION_CAP,ctx['repo']/'neural081/local-selection/SELECTION.json')
    c.exact(selected,('schema','task_id','construction','parent_source','central_source','source_freeze','routes','selection_scope','runtime_authorization'))
    c.need(selected['schema']=='neural081_local_source_selection_v1'and selected['task_id']==TASK and selected['selection_scope']=='local_instance'and selected['runtime_authorization']is False,'local construction identity, never root or runtime authority')
    for key,value in(('construction',ctx['construction']),('parent_source',ctx['parent_source']),('central_source',ctx['source'])):
        c.descriptor(selected[key]);c.need(c.typed_equal(selected[key],value),'exact current '+key)
    freeze,n=_read(ctx,selected['source_freeze'],2*2**20,ctx['here']/'QUALIFICATION_SOURCE.json');used+=n
    c.exact(freeze,('schema','task_id','files'))
    c.need(freeze['schema']=='neural081_portable_qualification_source_v1'and freeze['task_id']==TASK and c.typed_equal(freeze['files'],ctx['rows'])and len(ctx['rows'])==72,'exact complete current72 source map')
    c.exact(selected['routes'],CONDITIONS)
    for condition in CONDITIONS:
        route=selected['routes'][condition];c.exact(route,('argv','working_directory','sha256'))
        expected={'argv':template(ctx,condition),'working_directory':'.','sha256':ctx['manifest']['files']['entry.py']['sha256']}
        c.need(c.typed_equal(route,expected),'complete local relative route template')
        c.need(shared.python_launch(route['argv'])==6,'original isolated launch grammar and fresh cache')
    _budget(ctx).check_clock()
    return {'document':selected,'descriptor':descriptor,'metadata_read_charge_bytes':used}

def preferred_route(ctx,condition,selection,registry):
    """Bind local selection to the actual fixed current registry, not a callback."""
    c.need(type(condition)is str and condition in CONDITIONS,'literal local condition')
    desc=registry['descriptor'];doc,used=_read(ctx,desc,131072,ctx['repo']/'benchmarks/neuroscience/neural-081/manifest.json')
    c.need(c.typed_equal(doc,registry['document'])and doc.get('id')==TASK,'same actual current registration')
    c.exact(doc.get('program_conditions'),(CONDITIONS[1],))
    meta=doc.get('program_execution')if condition=='default'else doc['program_conditions'][condition]
    if meta=='default':meta=doc.get('program_execution')
    c.need(type(meta)is dict,'actual complete selected program')
    source={'path':str(Path(ctx['source']['path']).relative_to(ctx['repo'])),'bytes':ctx['source']['bytes'],'sha256':ctx['source']['sha256']}
    interface={'path':str(ctx['here'].relative_to(ctx['repo'])),'source':source}
    c.need(c.typed_equal(meta.get('preferred_source_interface'),interface)and c.typed_equal(meta.get('entrypoint'),selection['document']['routes'][condition]),'registry agrees with independently captured local source selection')
    freeze=selection['document']['source_freeze'];relative_freeze={**freeze,'path':str(Path(freeze['path']).relative_to(ctx['repo']))}
    c.need(c.typed_equal(meta.get('source_freeze'),relative_freeze),'same full source freeze')
    wrapper={'path':str(ctx['here']/'entry.py'),**ctx['manifest']['files']['entry.py']}
    budget=_budget(ctx);budget.charge('read_bytes',wrapper['bytes']+1)
    shared.capture(Path(wrapper['path']),wrapper['bytes'],{k:wrapper[k]for k in('bytes','sha256')});used+=wrapper['bytes']+1
    budget.check_clock()
    return {'status':'preferred_source_bound','selection':selection['descriptor'],'interface':interface,'registration':desc,'wrapper':wrapper,'wrapper_absolute':wrapper['path'],'wrapper_index':6,'registered_argv':selection['document']['routes'][condition]['argv'],'working_directory_absolute':str(ctx['repo']),'existing_runtime_qualification_still_required':True,'runtime_authorization':False,'metadata_read_charge_bytes':used}

def admit(ctx,condition,request_descriptor,selection_descriptor,registry):
    c.need(type(condition)is str and condition in CONDITIONS,'literal local condition')
    selected=read_selection(ctx,selection_descriptor)
    declaration,used=_read(ctx,request_descriptor,REQUEST_CAP,operator=True)
    c.exact(declaration,('schema','task_id','action','condition','context_id','instance','selection','declared_exposures','claim'))
    c.need(declaration['schema']=='neural081_local_development_request_v1'and declaration['task_id']==TASK and declaration['action']=='run'and declaration['condition']==condition,'exact task action and condition')
    c.need(type(declaration['context_id'])is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}',declaration['context_id']),'bounded local declared context')
    c.need(c.typed_equal(declaration['instance'],ctx['construction'])and c.typed_equal(declaration['selection'],selection_descriptor),'current construction and independently materialized local selection')
    c.need(declaration['claim']=='development_only_no_freshness_claim','only explicit development claim; no freshness inference')
    rows=declaration['declared_exposures'];c.need(type(rows)is list and len(rows)==5,'all five exposure categories, no omission')
    for row,kind in zip(rows,('source','data','results','models','other')):
        c.exact(row,('kind','disposition','evidence'))
        c.need(row['kind']==kind and row['disposition']in('declared','none_declared','unknown')and type(row['evidence'])is list and len(row['evidence'])<=16,'ordered bounded explicit exposure disposition')
        for evidence in row['evidence']:c.descriptor(evidence)
    operands=ctx['invocation_operands'];c.exact(operands,('program','output','review','other_reserve_bytes'))
    for key in('program','output','review'):c.absolute(operands[key])
    reserve=operands['other_reserve_bytes'];c.need(type(reserve)is str and reserve.isascii()and reserve.isdecimal()and str(int(reserve))==reserve,'literal nonnegative reservation argument')
    c.need(c.typed_equal(ctx['review']['local_declaration'],{'request':request_descriptor,'selection':selection_descriptor})and ctx['review']['program']['path']==operands['program'],'review binds this declaration and envelope')
    route=preferred_route(ctx,condition,selected,registry)
    return {'schema':'neural081_local_dispatch_admission_v1','task_id':TASK,'action':'run','condition':condition,'context_id':declaration['context_id'],'request':request_descriptor,'selection':selection_descriptor,'construction':ctx['construction'],'declared_exposures':rows,'claim':declaration['claim'],'declared_history_only':True,'history_independently_verified':False,'input_mount_authorization':False,'runtime_authorization':False,'preferred_program_route':route,'bound_operands':dict(operands),'metadata_read_charge_bytes':used+selected['metadata_read_charge_bytes']+route['metadata_read_charge_bytes']}

def _invocation(first,second,command,cwd,python):
    def without_charge(value):
        return {k:({kk:vv for kk,vv in v.items()if kk!='metadata_read_charge_bytes'}if k=='preferred_program_route'else v)for k,v in value.items()if k!='metadata_read_charge_bytes'}
    c.need(c.typed_equal(without_charge(first),without_charge(second))and second['schema']=='neural081_local_dispatch_admission_v1','same complete typed declaration and selection before launch')
    c.need(type(command)is list and all(type(x)is str and '\0'not in x and len(x)<=4096 for x in command),'bounded literal actual argv')
    route=second['preferred_program_route'];c.need(route['status']=='preferred_source_bound'and shared.python_launch(route['registered_argv'])==6,'same current isolated relative template')
    c.absolute(python)
    values={'{python}':python,**{'{'+k+'}':v for k,v in second['bound_operands'].items()}}
    expected=[values.get(token,token)for token in route['registered_argv']];expected[6]=route['wrapper_absolute']
    c.need(c.typed_equal(command,expected)and type(cwd)is str and cwd==route['working_directory_absolute'],'exact A(c), including all bound variable operands and cwd')
    invocation=c.encoded({'argv':command,'working_directory':cwd});c.need(len(invocation)<=65536,'bounded invocation identity')
    result={**second,'invocation':c.pin(invocation),'metadata_read_charge_bytes':first['metadata_read_charge_bytes']+second['metadata_read_charge_bytes'],'current_request_and_selection_rechecked_before_launch':True}
    c.need(len(c.encoded(result))<=131072,'bounded complete local admission receipt');return result


def finish(first,second,command,cwd):
    """Actual dispatch binding; original process completion remains external."""
    return _invocation(first,second,command,cwd,sys.executable)

def plan(first,second,command,cwd,python):
    """Metadata-only selected invocation; never assert this interpreter ran."""
    value=_invocation(first,second,command,cwd,python)
    value['schema']='neural081_local_planned_invocation_v1'
    value['actual_invocation_observed']=False
    value['current_request_and_selection_rechecked_for_plan']=value.pop('current_request_and_selection_rechecked_before_launch')
    return value
