"""Actual unchanged campaign predicates with bounded exact task source joins."""
import sys
from pathlib import Path
import common as c
import n081_shared_gate as shared_gate
import n081_portable_gate as gate
import n081_shared_campaign as campaign

TASK='NEURAL-081'
ALIAS='full10_instructed_excerpt_v1'
REGISTRY='benchmarks/neuroscience/neural-081/manifest.json'
QUALIFICATION='neural081/central/runtime-qualification'

def selected_condition(value):
    c.need(value in('default',ALIAS),'one full programme route');return None if value=='default'else value

def argv_template(ctx,condition):
    return gate.template(ctx,condition)

def actual_argv(ctx,args):
    values={'{python}':sys.executable,'{program}':args.program,'{output}':args.output,'{review}':args.review,'{other_reserve_bytes}':args.other_reserve_bytes}
    result=[values.get(x,x)for x in argv_template(ctx,args.condition)];result[6]=str(ctx['here']/'entry.py')
    c.need(sys.orig_argv==result,'literal actual central argv, no hidden switches');return result

def helper_bound(ctx):
    # Four bounded evidence JSONs, wrapper read, one possible failing source,
    # every remaining valid source and EOF probe, plus two captured gate loads.
    # Reservation is never refunded; first failing read aborts the helper.
    return 4*(2*2**20+1)+2*(16*2**20+1)+sum(v['bytes']+1 for v in ctx['rows'].values())+2*(ctx['bindings']['tools']['campaign_gate']['bytes']+1)

def qualify(ctx,condition,budget):
    path=ctx['repo']/REGISTRY;budget.charge('read_bytes',131073)
    raw=shared_gate.capture(path,131072);doc=shared_gate.metadata(raw)
    c.need(type(doc)is dict and doc.get('id')==TASK,'actual fixed task registry')
    meta=doc.get('program_execution')
    if selected_condition(condition)is not None:
        c.need(type(doc.get('program_conditions'))is dict and set(doc['program_conditions'])=={ALIAS},'one exact whole-study named route')
        meta=doc['program_conditions'][ALIAS]
        if meta=='default':meta=doc.get('program_execution')
    c.need(type(meta)is dict and meta.get('verification',{}).get('status')=='passed','missing runtime qualification; no operands admitted')
    freeze_path=str((ctx['here']/'QUALIFICATION_SOURCE.json').relative_to(ctx['repo']))
    freeze=meta.get('source_freeze');c.exact(freeze,('path','bytes','sha256'));c.need(freeze['path']==freeze_path,'fixed complete task source-freeze path');c.digest(freeze['sha256']);c.integer(freeze['bytes'],1,2*2**20)
    budget.charge('read_bytes',2*2**20+1);fraw=shared_gate.capture(ctx['repo']/freeze_path,2*2**20,{k:freeze[k]for k in('bytes','sha256')})
    c.need(c.pin(fraw)['sha256']==freeze['sha256'],'exact task source-freeze pin')
    fdoc=shared_gate.metadata(fraw);c.exact(fdoc,('schema','task_id','files'))
    c.need(fdoc['schema']=='neural081_portable_qualification_source_v1'and fdoc['task_id']==TASK and c.typed_equal(fdoc['files'],ctx['rows']),'full current source map, no rehashed subset')
    entry=meta.get('entrypoint');c.exact(entry,('argv','working_directory','sha256'))
    c.need(c.typed_equal(entry['argv'],argv_template(ctx,condition))and entry['working_directory']=='.'and entry['sha256']==ctx['manifest']['files']['entry.py']['sha256'],'exact source-owned full launch')
    preferred={'path':str(ctx['here'].relative_to(ctx['repo'])),'source':{'path':str(Path(ctx['source']['path']).relative_to(ctx['repo'])),'bytes':ctx['source']['bytes'],'sha256':ctx['source']['sha256']}}
    c.need(c.typed_equal(meta.get('preferred_source_interface'),preferred),'same full preferred source interface')
    for key in('receipt_path','qualification_path','source_binding_path'):
        value=meta['verification'].get(key);c.need(type(value)is str,'metadata-only qualification locator')
        q=shared_gate.relative_file(ctx['repo'],value);c.need(q.is_relative_to(ctx['repo']/QUALIFICATION)and q.suffix=='.json','protected fixed qualification metadata namespace')
    budget.charge('read_bytes',helper_bound(ctx));candidate=dict(doc,program_execution=meta)
    c.need(campaign.verified_program_runtime(path,candidate,ctx['repo'])is True,'actual original qualification helper refuses')
    budget.check_clock();return {'document':doc,'descriptor':{'path':str(path),**c.pin(raw)},'selected':meta}

def campaign_admit(ctx,args,review,registry,budget):
    # Keep the unchanged dispatch call site; the receipt explicitly means local
    # development selection and makes no WORK or independently fresh claim.
    c.exact(review['local_declaration'],('request','selection'))
    ctx['invocation_operands']={k:getattr(args,k)for k in('program','output','review','other_reserve_bytes')}
    admitted=gate.admit(ctx,args.condition,review['local_declaration']['request'],review['local_declaration']['selection'],registry)
    budget.check_clock();return admitted

def recheck_sources(ctx,budget):
    for path,body in ctx['bodies'].items():
        current=c.capture({'path':path,**c.pin(body)},budget,[Path(path).parent]);c.need(current==body,'current complete source bytes unchanged')
    budget.check_clock()
