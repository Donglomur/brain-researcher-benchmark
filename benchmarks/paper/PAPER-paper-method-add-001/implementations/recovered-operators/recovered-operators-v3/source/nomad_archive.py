"""Complete local archive closure, distinct from unavailable native process proof."""
from .nomad_math import need,closed,array_identity


def expected_archive(roster,selection,t11):
    closed(selection,['schema','scope','endpoints','groups','facts_selection_pin'],'source-selected complete archive scope')
    need(selection['schema']=='nomad_expected_archive_v2' and selection['facts_selection_pin']==roster['facts_selection_pin'],
         'archive selection binds exact independent scientific support')
    groups=roster['groups'];known={g['group_id']:g for g in groups}
    if selection['scope']=='test_only_groups':
        need(roster['mode']=='test_only' and selection['endpoints']==[],'partial scope cannot admit original production')
        ids=selection['groups'];need(type(ids) is list and ids and len(set(ids))==len(ids) and set(ids)<=set(known),'explicit tiny test groups')
    else:
        need(selection['scope'] in ('complete_paper','complete_endpoints') and selection['groups']==[], 'no production group thinning')
        endpoints=selection['endpoints'];all_endpoints={g['endpoint'] for g in groups}
        need(type(endpoints) is list and endpoints and len(set(endpoints))==len(endpoints) and set(endpoints)<=all_endpoints,'complete declared endpoints')
        if selection['scope']=='complete_paper':need(set(endpoints)==all_endpoints,'all original statistical endpoint families')
        ids=[g['group_id'] for g in groups if g['endpoint'] in endpoints]
    selected=[known[g] for g in ids]
    need(all(g['status']=='structurally_bound_source_support' for g in selected),'unresolved/invalid scientific archive support before targets')
    human=[g for g in selected if g['endpoint']=='F5'];production_human=bool(human) and selection['scope']!='test_only_groups'
    if production_human:need(len(human)==2 and t11 is not None,'both complete T11 sessions and actual replay required before targets')
    if not human:need(t11 is None,'no unselected chronological archive')
    calibration={}
    if t11 is not None:
        need(t11['logical_prediction_barrier']=='complete','actual chronological release object must finish')
        calibration={r['session_id']:r['block_id'] for r in t11['calibration_bindings']}
        need(len(calibration)==2 and len(t11['calibration_bindings'])==8,'complete two-session calibration uses')
        for g in human:
            sid=g['support']['unit_id'];need(sid in calibration,'F5 identity joins actual replay session')
            order=[]
            for r in t11['roster']['slots']:
                if r['session_id']==sid and r['block_id'] not in order:order.append(r['block_id'])
            need(g['support']['evaluation_order']==order,'entire chronological evaluation order joins statistical support')
    expected={}
    def add(pid,row):
        need(type(pid) is str and pid,'complete product identity')
        if pid in expected:
            old=expected[pid]
            need(all(old[k] is None or row[k] is None or old[k]==row[k] for k in old),'one scientific identity for every shared product')
            expected[pid]={k:old[k] if old[k] is not None else row[k] for k in old}
        else:expected[pid]=row
    for g in selected:
        actual=g['support'];unit=actual['unit_id']
        refs={p['reference_id'] for p in actual['pairs']}
        initial=calibration.get(unit)
        if g['endpoint']=='F5' and initial is None and len(refs)==1:initial=next(iter(refs))
        for pair in actual['pairs']:
            for method,names in pair['products'].items():
                add(names['query'],{'method':method,'task':unit,'role':'post_first_evaluation' if g['endpoint']=='F5' else 'query',
                    'reference_id':pair['reference_id'],'query_id':pair['query_id'],'target_support_pin':pair['target_support_pin']})
                if names['anchor'] is not None:
                    add(names['anchor'],{'method':method,'task':unit,'role':'anchor','reference_id':pair['reference_id'],
                        'query_id':pair['reference_id'],'target_support_pin':None})
        for method,lists in actual['summary_products'].items():
            for kind,pids in lists.items():
                role={'anchors':'anchor','calibration':'calibration','first_evaluation':'first_evaluation'}[kind]
                for pid in pids:
                    ref=initial if g['endpoint']=='F5' else None
                    query=(initial if kind=='calibration' else actual['evaluation_order'][0]) if g['endpoint']=='F5' else None
                    add(pid,{'method':method,'task':unit,'role':role,'reference_id':ref,'query_id':query,'target_support_pin':None})
    return expected,selected,production_human


def close_archive(roster,selection,captured,t11):
    expected,groups,production_human=expected_archive(roster,selection,t11)
    by={support['product_id']:(row,support,array,lineage) for row,support,array,lineage in captured}
    need(len(by)==len(captured) and set(by)==set(expected),'every expected method/anchor/attempt exactly once before targets')
    for pid,want in expected.items():
        row,sp,array,lineage=by[pid]
        for key,value in want.items():
            if value is not None:need(sp[key]==value,'actual expected archive identity '+key)
        need(sp['source_pin']==roster['source_pin'] and sp['method_profile_pin']==roster['method_profiles'][sp['method']]['profile_pin'],
             'actual source and method profile before targets')
    # Verify the full within-day support before opening any protected target.
    for g in groups:
        if g['endpoint'] not in ('F3_F4','S3','S5','S8','S12_historical'):continue
        actual=g['support'];sessions={v for p in actual['pairs'] for v in (p['reference_id'],p['query_id'])};signatures={}
        for method in g['methods']:
            seen=set()
            for pid in actual['summary_products'][method]['anchors']:
                _,sp,_,_=by[pid];sid=sp['reference_id']
                need(sp['query_id']==sid and sid in sessions and sid not in seen,'one actual anchor for each expected session/method')
                seen.add(sid);sig=(sp['sample_ids'],sp['axis_ids'],sp['target_artifact_pin'],sp['target_support_pin'])
                if sid not in signatures:signatures[sid]=sig
                need(sig==signatures[sid],'cross-method full anchor support and target identity before targets')
            need(seen==sessions,'complete independently expected anchor session coverage')
    if t11 is not None:
        slots={}
        for r in t11['calibration_bindings']:
            slots[(r['session_id'],r['block_id'],r['method'],'calibration')]=r
        first={sid:next(r['block_id'] for r in t11['roster']['slots'] if r['session_id']==sid)
               for sid in {r['session_id'] for r in t11['roster']['slots']}}
        for r in t11['prediction_bindings']:
            role='first_evaluation' if first[r['session_id']]==r['block_id'] else 'post_first_evaluation'
            slots[(r['session_id'],r['block_id'],r['method'],role)]=r
        human_units={g['support']['unit_id'] for g in groups if g['endpoint']=='F5'};joined=set()
        for pid,(row,sp,array,lineage) in by.items():
            if sp['task'] not in human_units:continue
            key=(sp['task'],sp['query_id'],sp['method'],sp['role']);need(key in slots and key not in joined,'actual T11 grade slot joins one chronological seal')
            joined.add(key);binding=slots[key]
            if row['status']=='complete':
                need(binding['status']=='complete' and binding['pin']==array_identity(array),'actual graded full array matches sealed block/calibration product')
                need(lineage['state_pin']==binding['state_pin'],'actual graded T11 state joins sealed state')
                need(sp['axis_ids']==t11['axes'] and lineage['axis_units']==t11['units'],'T11 sealed prediction axes/units')
            else:
                need(binding['status']=='failed' and binding['pin']['failure_evidence']['prefix_pin']==row['failure_descriptor']['sha256'],
                     'same captured failed attempt in chronology and grading archive')
        need(joined==set(slots),'every T11 calibration/first/post slot joined before targets')
    need(not production_human or t11 is not None,'production T11 target access cannot bypass local chronology')
    return {'schema':'nomad_complete_local_archive_v2','scope':selection['scope'],'selection':selection,
        'expected_product_ids':sorted(expected),'expected_count':len(expected),
        'complete_count':sum(r['status']=='complete' for r,_,_,_ in captured),
        'failed_attempts':[{'product_id':sp['product_id'],'evidence':r['failure_descriptor'],'captured_prefix':lineage}
            for r,sp,_,lineage in captured if r['status']=='failed'],
        't11_logical_closure':t11,'native_process_closure_verified':False,
        'scope_limit':'Complete selected scientific archive; no native generation or external OS closure attestation.'}
