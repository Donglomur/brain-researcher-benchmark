"""Closed extraction of actual producer files; no supplied numerical answers.

The independently qualified projection records unresolved paper-to-output
mapping explicitly. Every selected value comes from a completed producer's
captured output. Failed prerequisites never become success or zero arrays.
"""
from banc_runtime.codec import need,parse,pin,encode,descriptor
from banc_runtime.collect import GRAPH_NULL_GAP
from .protected import capture_bundle
from .io import exact_fields,read_json,write_json,digest

def select(spec,jobs,meter,cap):
    exact_fields(spec,('job','file','mode','path'),'closed output selector')
    need(spec['job'] in jobs,'actual upstream producer')
    run=jobs[spec['job']];need(run['state']=='completed','selector depends on a failed/missing producer')
    need(spec['file'] in run['files'],'actual retained producer file')
    d=run['files'][spec['file']]
    if spec['mode']=='file_identity':
        need(spec['path']==[],'file identity has no value path')
        return [d['sha256']]
    need(spec['mode']=='json_path' and type(spec['path']) is list,'closed JSON selector')
    value=read_json(run['root'],d,meter,cap)
    for key in spec['path']:
        need(type(key) in (str,int) and type(key) is not bool,'exact JSON key/index')
        if type(key) is str:need(type(value) is dict and key in value,'present JSON member')
        else:need(type(value) is list and 0<=key<len(value),'present JSON index')
        value=value[key]
    return value

def producer_receipt(ids,jobs,source_identity,input_identity):
    need(ids and all(i in jobs and jobs[i]['state']=='completed' for i in ids),'all actual producer receipts')
    return {'producer':'+'.join(ids),'source_sha256':source_identity,'input_sha256':input_identity,
      'run_sha256':pin(encode([jobs[i]['receipt'] for i in ids]))['sha256']}

def project(plan,jobs,contracts,program_identity,root,attempts,source_identity,input_identity,meter,cap=1048576):
    exact_fields(plan,('schema','panels','families','legacy'),'full projection')
    need(plan['schema']=='banc_complete_projection_v1','closed projection schema')
    definitions={'panels':contracts['OBLIGATIONS']['rows'],'families':contracts['WORKFLOW']['families'],'legacy':contracts['WORKFLOW']['legacy_entries']}
    for kind,defs in definitions.items():
        key='entry' if kind=='legacy' else 'id'
        need(type(plan[kind]) is list and [x['id'] for x in plan[kind]]==[x[key] for x in defs],'complete ordered projection '+kind)
    bundle={'schema':'banc_complete_output_v2','program_identity':program_identity,'panels':[],'families':[],'legacy':[],
      'gates':[{'id':g['id'],'state':'open','reason':g.get('reason') or g.get('name') or 'Scientific gate remains open'} for g in contracts['GATES']['gates']],
      'attempts':attempts}
    for kind,defs in definitions.items():
        for item,definition in zip(plan[kind],defs):
            exact_fields(item,('id','jobs','gap','body'),'projection obligation')
            need(type(item['jobs']) is list and len(set(item['jobs']))==len(item['jobs']),'unique complete producer jobs')
            need(all(j in jobs for j in item['jobs']),'projection names actual jobs')
            gap=item['gap']
            if gap is not None:exact_fields(gap,('code','reason'),'explicit unresolved mapping')
            failed=[j for j in item['jobs'] if jobs[j]['state']!='completed']
            if item['id']=='randomized_graph_null_ensemble':
                need(kind=='legacy' and gap is not None and gap['code']==GRAPH_NULL_GAP and item['body'] is None,'original graph null unlocated remains required-unscorable')
            if gap is not None or failed:
                need(gap is None or (type(gap['reason']) is str and gap['reason'] and type(gap['code']) is str and gap['code']),'specific required gap')
                reason=gap['reason'] if gap else 'Failed actual prerequisite: '+','.join(failed)
                row={'id':item['id'],'state':'required_unscorable','reason':reason}
                if kind=='panels':row.update(family=definition['workflow_family'],payload=None)
                else:
                    row.update(products=[],gap_code=gap['code'] if gap else 'producer_failure')
                    if kind=='legacy':row['family']=definition['mapped_family']
                bundle[kind].append(row);continue
            receipt=producer_receipt(item['jobs'],jobs,source_identity,input_identity)
            body=item['body'];need(type(body) is dict,'actual complete projection recipe')
            # Each selector must be among the declared mandatory producer jobs.
            selectors=[body[k] for k in ('support','values' if kind=='panels' else 'content')]
            need(all(s['job'] in item['jobs'] for s in selectors),'selector/producer lineage')
            support=select(body['support'],jobs,meter,cap)
            if kind=='panels':
                exact_fields(body,('kind','estimand_identity','support','values'),'panel projection recipe')
                payload={'id':item['id'],'kind':body['kind'],'support':support,'values':select(body['values'],jobs,meter,cap),
                  'estimand_identity':digest(body['estimand_identity']),'producer_receipt':receipt}
                d=write_json(root,'panel-'+item['id']+'.json',payload,meter)
                bundle[kind].append({'id':item['id'],'family':definition['workflow_family'],'state':'produced_unqualified','payload':d,'reason':None})
            else:
                exact_fields(body,('support','content'),'product projection recipe')
                # A family cannot claim production when one of its panels failed.
                incomplete=kind=='families' and any(p['family']==item['id'] and p['state']!='produced_unqualified' for p in bundle['panels'])
                if incomplete:
                    bundle[kind].append({'id':item['id'],'state':'required_unscorable','products':[],'reason':'A required family panel is unscorable','gap_code':'incomplete_panel_production'});continue
                payload={'schema':'banc_complete_family_product_v1','kind':kind,'owner':item['id'],'id':'complete-product',
                  'producer_receipt':receipt,'support':support,'content':select(body['content'],jobs,meter,cap)}
                d=write_json(root,kind+'-'+item['id']+'.json',payload,meter)
                row={'id':item['id'],'state':'produced_unqualified','products':[{'id':'complete-product','payload':d}],'reason':None,'gap_code':None}
                if kind=='legacy':row['family']=definition['mapped_family']
                bundle[kind].append(row)
    d=write_json(root,'bundle.json',bundle,meter)
    seal=capture_bundle(root,d,contracts,program_identity=program_identity,meter=meter,cap=cap)
    return d,seal
