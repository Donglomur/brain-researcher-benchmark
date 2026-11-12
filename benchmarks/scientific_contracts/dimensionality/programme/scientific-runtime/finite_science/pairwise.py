"""Complete fixed-comparison diagnostics, separate from the selected macro claim.

One call evaluates one prespecified variant/key/endpoint. The controller must
retain every scheduled comparison and its actual input/output custody. No hidden
truth chooses a comparator and no family-only comparison claims 72-cell success.
"""
import math
from .common import LEVELS,require,result
from .catalog import PRIMARY_KEYS,REFERENCE_BANK,UNCERTAINTY_RULES
from .scoring import loss,interval_value,INFRA


def execute(payload):
    req=payload['request'];p=payload['protocol'];comp=req['comparison']
    require(p.get('score_stage')=='target_last' and p.get('paired_states_sealed') is True and p.get('pairwise_manifest_admitted') is True,'protected presealed complete pairwise manifest required','qualification_required')
    key=next((x for x in PRIMARY_KEYS if x['id']==comp['key_id']),None)
    ref=next((x for x in REFERENCE_BANK if x['id']==comp['reference_id']),None)
    require(key is not None and ref is not None,'exact comparison key and reference family')
    kind=comp['kind'];endpoint=comp['endpoint'];variant=comp['variant']
    require(kind in ('primary_bank_variant','diagnostic_or_literal') and endpoint in ('point','uncertainty'),'comparison kind/endpoint')
    require(comp.get('comparison_id') and comp.get('reference_source_version') and comp.get('target_class') and comp.get('protocol_id'),'exact scientific version/target/protocol identity')
    require(variant in ref['variants'] or (ref['id']=='REF13_LITERAL_SOURCE' and kind=='diagnostic_or_literal'),'unlisted comparison variant')
    point_id=f"{key['id']}/{ref['id']}/{variant}"
    if kind=='primary_bank_variant':
        require(ref['id'] in key['eligible_reference_ids_before_qualification'] and comp['target_class']==key['target_class'] and comp['protocol_id']==key['protocol'],'primary comparison cannot relabel target/protocol or comparator')
        expected_variant=point_id
        if endpoint=='uncertainty':
            rule=comp['rule'];scale=comp['scale'];law=UNCERTAINTY_RULES.get(rule)
            require(law is not None and key['family'] in law['families'] and key['trial_view'] in law['views'],'exact structural uncertainty compatibility')
            require(scale in ((1,) if rule=='U03_TWO_AXIS_PERCENTILE' else (1,1.25,1.5,2)),'exact fixed CI scale')
            expected_variant=f'{point_id}/{rule}/{scale}'
        require(comp['reference_variant_id']==expected_variant,'canonical fixed variant identity')
    else:
        require(ref['selection_role'] in ('literal_diagnostic','secondary_target_only','diagnostic','nongeometric_diagnostic'),'primary control mislabeled diagnostic')
        require(comp.get('reference_variant_id'),'exact diagnostic/literal variant identity')
    expected=req['expected_cases'];records=req['records'];roster={x['case_id']:x for x in expected};by={x['case_id']:x for x in records}
    require(len(roster)==len(expected)==len(by)==len(records)==1200 and set(roster)==set(by),'complete1200 unique case comparison roster')
    cells={x['cell'] for x in expected};require(cells==set(key['cells']),'all six original comparison cells')
    require(all(sum(x['cell']==cell for x in expected)==200 for cell in cells),'200 original independent worlds per cell')
    require(len({x['world_id'] for x in expected})==1200,'distinct worlds within one designated view')
    compatibility=comp['compatibility'];require(type(compatibility.get('same_estimand')) is bool and compatibility.get('reason'),'explicit scientific compatibility disposition')
    compatible=compatibility['same_estimand']
    if compatible:
        require(compatibility.get('qualification_id'),'common estimand qualification absent','qualification_required')
        require(comp['target_class'] in ref['target_classes'] and key['family'] in ref['families'] and key['trial_view'] in ref['trial_views'],'cannot borrow numerical truth from a different reference target')
    rows=[];percell={c:[] for c in cells};failures={'candidate':{},'reference':{}};blocked=[];reference_states=set();candidate_states=set();source_ids=set()
    for case in expected:
        row=by[case['case_id']]
        require(case['family']==key['family'] and case['view']==key['trial_view'],'case family/view differs from exact comparison key')
        require(case['target_class']==comp['target_class'] and case['protocol_id']==comp['protocol_id'],'comparison target/protocol identity mismatch')
        for field in ('world_id','family','cell','view','input_identity','target_identity','target_class','protocol_id','candidate_state_id','candidate_source_sha256','reference_state_id','reference_source_sha256','reference_variant_id'):
            require(row[field]==case[field],'original pairwise identity mismatch: '+field)
        require(row['reference_variant_id']==comp['reference_variant_id'],'unselected variant substitution')
        reference_states.add(row['reference_state_id']);candidate_states.add(row['candidate_state_id']);source_ids.add(row['reference_source_sha256'])
        cs=row['candidate']['status'] if endpoint=='point' else row['candidate_status']
        rs=row['reference']['status'] if endpoint=='point' else row['reference_status']
        failures['candidate'][cs]=failures['candidate'].get(cs,0)+1;failures['reference'][rs]=failures['reference'].get(rs,0)+1
        if rs in INFRA:blocked.append(case['case_id'])
        if not compatible:continue
        if endpoint=='point':
            cm=loss(row['candidate'],case['truth']);rm=loss(row['reference'],case['truth'])
            percell[case['cell']].append((cm['loss'],rm['loss']))
        else:
            cm=[];rm=[]
            for level in LEVELS:
                cm.append(interval_value(row.get('candidate_sets',{}).get(str(level),{}),case['truth'],level))
                rm.append(interval_value(row.get('reference_sets',{}).get(str(level),{}),case['truth'],level))
            percell[case['cell']].append((cm,rm))
    require(len(reference_states)==1 and len(source_ids)==1,'fixed reference state/source must persist across every comparison world')
    support={'comparison':comp,'original_cases':1200,'independent_worlds':1200,'cells':6,'views':[key['trial_view']],'candidate_state_ids':sorted(candidate_states,key=lambda value:(value is not None,str(value))),'reference_state_ids':sorted(reference_states),'reference_source_sha256s':sorted(source_ids),'status_counts':failures,'blocked_reference_cases':blocked,'actual_original_records_retained_by':'original scientific request and controller custody, without duplicate raw result copies','scope':'one exact key/variant; not the72-cell selected macro comparator'}
    if not compatible:return result({'comparison_id':comp['comparison_id'],'numeric_comparison':None,'unsupported_reason':compatibility['reason'],'macro_improvement_claim':False},support,status='unsupported_target_pair')
    if endpoint=='point':
        cell_metrics={cell:{'candidate_risk':math.fsum(v[0] for v in values)/200,'reference_risk':math.fsum(v[1] for v in values)/200} for cell,values in percell.items()}
        cr=math.fsum(v['candidate_risk'] for v in cell_metrics.values())/6;rr=math.fsum(v['reference_risk'] for v in cell_metrics.values())/6
        metrics={'candidate_risk':cr,'reference_risk':rr,'candidate_minus_reference_risk':cr-rr,'relative_risk_reduction':1-cr/rr if rr>0 else None,'per_cell':cell_metrics}
    else:
        metrics={};weights=[(1-c)/2 for c in LEVELS]
        for side,index in [('candidate',0),('reference',1)]:
            levels={}
            for j,level in enumerate(LEVELS):
                entries=[pair[index][j] for values in percell.values() for pair in values];topology={}
                for value in entries:topology[value['topology']]=topology.get(value['topology'],0)+1
                levels[str(level)]={'coverage':math.fsum(v['coverage'] for v in entries)/1200,'normalized_interval_score':math.fsum(v['normalized_interval_score'] for v in entries)/1200,'mean_log_set_width':math.fsum(v['log_width'] for v in entries)/1200,'topology_counts':topology}
            metrics[side]={'levels':levels,'weighted_interval_score':math.fsum(w*levels[str(c)]['normalized_interval_score'] for w,c in zip(weights,LEVELS))/math.fsum(weights)}
        cr=metrics['candidate']['weighted_interval_score'];rr=metrics['reference']['weighted_interval_score'];metrics['relative_interval_score_reduction']=1-cr/rr if rr>0 else None
    return result({'comparison_id':comp['comparison_id'],'metrics':metrics,'macro_improvement_claim':False,'inference_performed':False},support,['Descriptive fixed compatible comparison only. Every observed scientific failure retains worst loss/noncoverage; infrastructure blocks qualification, never denominator removal.'],status='qualification_required' if blocked else 'ok')
