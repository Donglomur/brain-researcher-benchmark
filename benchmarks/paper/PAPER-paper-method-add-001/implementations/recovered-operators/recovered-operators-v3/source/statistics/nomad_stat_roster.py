"""Literal complete source test roster; unknown original supports remain slots."""
from fractions import Fraction
from .nomad_stat_math import (Refusal,need,fields,integer,pin,budget,encode,bytes_pin,
    rational,from_rational,projected,quantiles,signed_rank)

MAIN=('Static decoder','Aligned FA','ADAN','NoMAD')
HUMAN=('Static','RTI','NoMAD','NoMAD+RTI')
S7=MAIN+('TNDM','Adaptive TNDM','Aligner ablated','Static LFADS')
COUNTS={'F3_F4':12,'F5':12,'S1':6,'S3':2,'S5':2,'S7':56,'S8':2,'S9':2,'S12_historical':2,'S14':6}
HOLD_TOPICS={'F3_F4':['actual rosters','historical numerical test profile'],
 'F5':['human stability transform/time/bin/solver profile','actual block and calibration joins','historical numerical test profile'],
 'S1':['identity of selected fixed readout run','monkey search history','historical numerical test profile'],
 'S3':['exact historical argument ordering','causal/acausal state/inference matching','historical numerical test profile'],
 'S5':['continuous fraction/split/support policy','historical numerical test profile'],
 'S7':['Adaptive TNDM/Aligner ablated/Static LFADS recipe and label mappings','all38 exact one-day pairs','historical numerical test profile'],
 'S8':['TNDM experiment revision/six-loss schedule','historical numerical test profile'],
 'S9':['actual original test support within complete forward roster','sequential update operator','historical numerical test profile'],
 'S12_historical':['historical adaptation profile','historical numerical test profile'],
 'S14':['matched normalization profile/run lineage','historical numerical test profile']}
SUPPORT_KEYS=('unit_id','source_support_pin','reference_day','pairs','test_pair_ids','evaluation_order','summary_products','calendar')
PAIR_KEYS=('pair_id','reference_id','query_id','day_gap','target_support_pin','products')

def combinations(methods):return [(methods[i],methods[j]) for i in range(len(methods)) for j in range(i)]

def definitions():
    rows=[]
    for endpoint in COUNTS:
        if endpoint=='F5':units=('session_slot_0','session_slot_1');methods=HUMAN;contrasts=combinations(methods)
        elif endpoint in ('S1','S14'):
            units=('isometric/0','isometric/28','isometric/95','reaching/0','reaching/10','reaching/38')
            methods=('fixed-HP LFADS with behavioral readout','AutoLFADS without behavioral readout') if endpoint=='S1' else ('normalization enabled','normalization disabled on both days')
            contrasts=[methods]
        else:
            units=('isometric','reaching')
            methods={'F3_F4':MAIN,'S3':('causal','acausal'),'S5':('trial-only FA','continuous FA'),
              'S7':S7,'S8':('NoMAD','fixed TNDM'),'S9':('single-reference FA','sequential FA'),
              'S12_historical':('NoMAD','historical Adaptive LFADS')}.get(endpoint)
            contrasts=combinations(methods) if endpoint in ('F3_F4','S7') else [methods]
        for unit in units:
            task=unit.split('/')[0]
            expected=None if endpoint=='F5' else (22 if task=='isometric' else 16) if endpoint=='S7' else (19 if task=='isometric' else 11) if endpoint in ('S1','S14') else (190 if task=='isometric' else 66) if endpoint=='S9' else (380 if task=='isometric' else 132)
            rows.append({'group_id':endpoint+'/'+unit,'endpoint':endpoint,'unit_slot':unit,'methods':list(methods),
                'expected_pair_count':expected,'contrasts':[list(x) for x in contrasts],
                'alternative':None if endpoint=='S3' else 'two-sided' if endpoint=='S7' else 'greater',
                'expected_reference_day':int(unit.split('/')[1]) if endpoint in ('S1','S14') else None})
    return rows

def _validate(group,support,profiles,b):
    fields(support,SUPPORT_KEYS);pin(support['source_support_pin'])
    need(type(support['unit_id']) is str and support['unit_id'],'actual_unit_identity')
    need(support['reference_day']==group['expected_reference_day'],'fixed_reference_day_join')
    pairs=support['pairs'];need(type(pairs) is list,'ordered_full_pair_roster');b.take(items=len(pairs))
    expected=group['expected_pair_count']
    if expected is not None:need(len(pairs)==expected,'full_pair_count',expected=expected,observed=len(pairs))
    else:
        order=support['evaluation_order'];need(type(order) is list and len(order)>=1 and len(set(order))==len(order),'full_original_human_evaluation_order')
        need([p['query_id'] for p in pairs]==order[1:],'human_summary_excludes_first_evaluation_only')
    ids=set();edges=set()
    for p in pairs:
        fields(p,PAIR_KEYS);pin(p['target_support_pin'])
        need(all(type(p[k]) is str and p[k] for k in ('pair_id','reference_id','query_id')),'actual_literal_pair_identity')
        need(p['pair_id'] not in ids and p['reference_id']!=p['query_id'] and (p['reference_id'],p['query_id']) not in edges,'no_missing_or_duplicate_pair')
        ids.add(p['pair_id']);edges.add((p['reference_id'],p['query_id']))
        need(type(p['day_gap']) is int,'explicit_source_day_gap')
        if group['endpoint']=='S7':need(p['day_gap']==1,'actual_one_day_support')
        if group['endpoint']=='S9':need(p['day_gap']>0,'full_chronological_forward_support')
        need(type(p['products']) is dict and set(p['products'])==set(group['methods']),'all_literal_methods_no_alias')
        for method,record in p['products'].items():
            fields(record,('query','anchor'))
            need(type(record['query']) is str and record['query'],'actual_query_product_identity')
            if group['endpoint']=='S7':need(type(record['anchor']) is str and record['anchor'],'method_specific_reference_anchor_required')
            else:need(record['anchor'] is None,'no_unselected_decrease_transform')
    if group['endpoint'] in ('F3_F4','S3','S5','S8','S12_historical'):
        sessions={v for e in edges for v in e};n=20 if group['unit_slot']=='isometric' else 12
        need(len(sessions)==n and len(edges)==n*(n-1),'complete_directed_session_graph')
    if group['endpoint'] in ('S1','S14'):need(len({p['reference_id'] for p in pairs})==1,'one_exact_reference_per_alignment_group')
    if group['endpoint']=='S9':
        sessions={v for e in edges for v in e};n=20 if group['unit_slot']=='isometric' else 12
        calendar=support['calendar'];need(type(calendar) is list and len(calendar)==n,'full_selected_S9_calendar')
        for row in calendar:
            fields(row,('session_id','day'));need(type(row['session_id']) is str and row['session_id'],'actual_calendar_session');integer(row['day'],'calendar_day')
        order=[r['session_id'] for r in calendar];days=[r['day'] for r in calendar]
        need(len(set(order))==n and set(order)==sessions and all(a<c for a,c in zip(days,days[1:])), 'one_consistent_ordered_calendar')
        expected={(order[i],order[j]):days[j]-days[i] for i in range(n) for j in range(i+1,n)}
        need(edges==set(expected) and all(p['day_gap']==expected[(p['reference_id'],p['query_id'])] for p in pairs),
             'every_forward_edge_and_day_gap_matches_one_calendar')
        test=support['test_pair_ids'];need(type(test) is list and test and len(set(test))==len(test) and set(test)<=ids,'actual_original_S9_test_subset_within_full_forward_roster')
    else:
        need(support['calendar'] is None,'no_unselected_calendar_profile')
        need(support['test_pair_ids']==[p['pair_id'] for p in pairs],'no_test_support_drop_or_reorder')
    need(type(support['summary_products']) is dict and set(support['summary_products'])==set(group['methods']),'full_method_summary_support')
    for method in group['methods']:
        need(method in profiles,'exact_method_profile_mapping_missing',method=method)
        fields(profiles[method],('label','profile_pin'));pin(profiles[method]['profile_pin'])
        need(profiles[method]['label']==method,'literal_method_profile_no_alias')
        row=support['summary_products'][method];fields(row,('anchors','calibration','first_evaluation'))
        for name,seq in row.items():need(type(seq) is list and all(type(x) is str and x for x in seq) and len(set(seq))==len(seq),'complete_summary_product_ids')
        if group['endpoint']=='F5':need(len(row['calibration'])==len(row['first_evaluation'])==1,'separate_calibration_and_first_evaluation')
        if group['endpoint'] in ('F3_F4','S3','S5','S8','S12_historical'):
            need(len(row['anchors'])==(20 if group['unit_slot']=='isometric' else 12),'full_within_day_anchors')

def compile_roster(facts,b):
    values=facts['values'];supports=values.get('supports',{});profiles=values.get('method_profiles',{})
    need(type(supports) is dict and type(profiles) is dict,'source_support_and_profile_maps')
    selected_source=values.get('source_pin')
    if selected_source is not None:pin(selected_source)
    specs=definitions();known={g['group_id'] for g in specs}
    need(set(supports)<=known,'no_unreported_endpoint_or_test_group')
    b.take(items=102+304+len(specs),metadata_bytes=512*(102+304+len(specs)));b.hold(512*(102+304+len(specs)))
    groups=[];tests=[];s7slots=[]
    for g in specs:
        actual=supports.get(g['group_id']);status='unavailable_missing_source_support';error=None
        if actual is not None:
            try:
                need(selected_source is not None,'missing_selected_operator_source_pin')
                _validate(g,actual,profiles,b);status='structurally_bound_source_support'
            except Refusal as refusal:
                # Preserve all planned slots; malformed support is never filtered.
                status='unavailable_invalid_source_support';error={'code':refusal.code,'details':refusal.details}
        row={**g,'support':actual,'status':status,'support_error':error,'unresolved_original_topics':HOLD_TOPICS[g['endpoint']]}
        groups.append(row)
        for i,(first,second) in enumerate(g['contrasts']):
            tests.append({'test_id':g['group_id']+'/contrast-'+str(i),'group_id':g['group_id'],
                          'first':first,'second':second,'alternative':g['alternative'],
                          'difference':'unadmitted_argument_order' if g['endpoint']=='S3' else 'anchor_minus_query_first_minus_second' if g['endpoint']=='S7' else 'first_minus_second',
                          'status':status,'source_direction_held':g['endpoint']=='S3'})
        if g['endpoint']=='S7':
            for i in range(g['expected_pair_count']):
                for method in S7:s7slots.append({'slot_id':g['group_id']+'/pair-slot-'+str(i)+'/'+method,
                    'group_id':g['group_id'],'pair_ordinal':i,'method':method,'status':status})
    need(len(tests)==102 and len(s7slots)==304,'full_source_roster_internal_count')
    return {'schema':'nomad_complete_statistical_roster_v1','mode':facts['mode'],'facts_selection_pin':facts['selection_pin'],
            'groups':groups,'tests':tests,'method_profiles':profiles,'source_pin':selected_source,'s7_decrease_slots':s7slots,'nominal_tests':102,
            'endpoint_test_counts':dict(COUNTS),'human_stability_slots':[{'session_slot':s,'method':m,'status':'unavailable_original_human_fit_profile'} for s in ('session_slot_0','session_slot_1') for m in HUMAN],
            'additional_summary_obligations':{'S6':'eight main four-method/task original five-day Eq5 stability fits; preserve V6, no changed fit operator',
              'S11':'12 R2 cells, six decoders, three dPCA fits; no invented significance test',
              'S13':'full actual latency samples/failures/histograms; no invented significance test',
              'S15':'both full matrices/failure/time summaries; no significance test',
              'S16':'six references, three methods, full original dimension grid; unadmitted grid remains unavailable'},
            'original_unresolved_ids':['U'+str(i).zfill(2) for i in range(1,22)],'original_parity':False}

def _value(product_id,products,method,profile,reference,query,target_pin,b,role=None):
    if product_id not in products:return None,{'status':'unavailable_missing_product','product_id':product_id}
    row=products[product_id];s=row['support']
    need(s['method']==method and s['method_profile_pin']==profile['profile_pin']
         and s['reference_id']==reference and s['query_id']==query,'computed_product_method_and_pair_join',product_id=product_id)
    if target_pin is not None:need(s['target_support_pin']==target_pin,'complete_matched_target_support',product_id=product_id)
    if role is not None:need(s['role']==role,'computed_product_role',product_id=product_id)
    if row['status']!='computed':return None,{'status':row['status'],'product_id':product_id,'invalid_prediction_cells':row['invalid_prediction_cells'],'invalid_target_cells':row['invalid_target_cells'],'constant_target_axes':row['constant_target_axes']}
    return from_rational(row['exact_value'],b),{'status':'computed','product_id':product_id}

def _summary(values,failures,expected,policy,b):
    b.take(operations=3*len(values))
    counts={'expected':expected,'computed':len(values),'negative':sum(v<0 for v in values),
            'zero':sum(v==0 for v in values),'positive':sum(v>0 for v in values),'unavailable':expected-len(values)}
    if failures or len(values)!=expected:return {'status':'unavailable_incomplete_or_invalid','expected':expected,'computed':len(values),'outcome_counts':counts,'failures':failures,'quantiles':None}
    if policy is None:return {'status':'unavailable_quantile_policy','expected':expected,'computed':len(values),'outcome_counts':counts,'failures':[],'quantiles':None}
    return {'status':'computed','expected':expected,'computed':len(values),'outcome_counts':counts,'failures':[],'quantiles':quantiles(values,policy,b)}

def _missing_summaries(group,b):
    b.take(items=len(group['methods']),metadata_bytes=1024*len(group['methods']));b.hold(1024*len(group['methods']))
    return [{'group_id':group['group_id'],'method':method,'kind':'all_complete_group_pairs',
        'status':group['status'],'expected':group['expected_pair_count'],'computed':0,'quantiles':None,
        'failures':[{'source_support_error':group['support_error']}],
        'full_pair_values':None,'other_required_summaries':group['unresolved_original_topics']}
        for method in group['methods']]

def validate_anchor_coverage(group,products,profiles,source_pin,b):
    if group['endpoint'] not in ('F3_F4','S3','S5','S8','S12_historical'):return
    actual=group['support'];expected={v for pair in actual['pairs'] for v in (pair['reference_id'],pair['query_id'])}
    signatures={}
    for method in group['methods']:
        ids=actual['summary_products'][method]['anchors'];seen=set()
        for pid in ids:
            if pid not in products:continue  # missing products retain unavailable summaries
            row=products[pid];sp=row['support'];session=sp['reference_id']
            need(sp['role']=='anchor' and sp['query_id']==session and session in expected and session not in seen,
                 'one_within_day_anchor_per_expected_session_method')
            need(sp['method']==method and sp['method_profile_pin']==profiles[method]['profile_pin']
                 and sp['source_pin']==source_pin and sp['task']==actual['unit_id'],'actual_anchor_method_source_unit')
            seen.add(session)
            signature=(sp['sample_ids'],sp['axis_ids'],sp['target_artifact_pin'],sp['target_support_pin'],
                       row['consumed_target_digest'],row['shape'])
            if session not in signatures:signatures[session]=signature
            need(signatures[session]==signature,'same_session_anchor_full_target_support_across_methods')
        if all(pid in products for pid in ids):need(seen==expected,'full_anchor_session_coverage')


def reduce_roster(roster,products,captured,b):
    need(roster['schema']=='nomad_complete_statistical_roster_v1' and len(roster['tests'])==102
         and len(roster['s7_decrease_slots'])==304,'complete_immutable_source_roster')
    selected=captured['values'].get('statistics');profile_error=None
    if selected is not None:
        need(type(selected) is dict,'selected_literal_statistical_profile')
        required={'algorithm','difference_arithmetic','zero_policy','tie_policy','alternative','all_zero','continuity','quantile_policy','multiplicity','scope'}
        if set(selected)!=required or selected.get('alternative')!='per_roster':profile_error='unavailable_incomplete_or_nonroster_statistical_profile'
        elif not (selected['algorithm']=='conditional_sign_midrank_v1' and selected['difference_arithmetic']=='exact_score_rationals' and selected['zero_policy']=='wilcox' and selected['tie_policy']=='exact_midrank' and selected['all_zero'] in ('p_one','undefined') and selected['continuity']=='none' and selected['quantile_policy'] in ('linear_type7','inverted_cdf') and selected['multiplicity']=='none_report_only' and selected['scope'] in ('original_unresolved','test_only','selected_operator_not_historical')):profile_error='unavailable_unsupported_statistical_profile'
    policy=None if selected is None or selected.get('quantile_policy') not in ('linear_type7','inverted_cdf') else selected['quantile_policy']
    if roster['mode']=='original':policy=None  # no test/prospective quantile rule becomes historical authority
    profiles=roster['method_profiles'];group_values={};summaries=[];used=set();decreases=[]
    for group in roster['groups']:
        gid=group['group_id'];actual=group['support'];cache={}
        if group['status']!='structurally_bound_source_support':
            summaries.extend(_missing_summaries(group,b));group_values[gid]=cache;continue
        validate_anchor_coverage(group,products,profiles,roster['source_pin'],b)
        n=len(actual['pairs']);lease=n*len(group['methods'])*(1024+16*((b.limits['integer_bits']+7)//8))
        b.hold(lease);b.take(metadata_bytes=lease,items=n*len(group['methods']))
        for pair in actual['pairs']:
            signatures={'query':None,'anchor':None}
            for method in group['methods']:
                for role,pid in pair['products'][method].items():
                    if pid is None or pid not in products:continue
                    product=products[pid];sp=product['support']
                    signature=(sp['sample_ids'],sp['axis_ids'],sp['target_artifact_pin'],sp['target_support_pin'],product['consumed_target_digest'],product['shape'])
                    if signatures[role] is None:signatures[role]=signature
                    need(signatures[role]==signature,'actual_complete_matched_target_arrays_across_methods')
        for method in group['methods']:
            entries={};valid=[];failures=[]
            for pair in actual['pairs']:
                ids=pair['products'][method];used.add(ids['query'])
                for pid in (ids['query'],ids['anchor']):
                    if pid is not None and pid in products:
                        need(products[pid]['support']['task']==actual['unit_id'] and products[pid]['support']['source_pin']==roster['source_pin'],'actual_unit_and_operator_source_join')
                if ids['query'] in products:need(products[ids['query']]['support']['role']==('post_first_evaluation' if group['endpoint']=='F5' else 'query'),'actual_query_support_role')
                value,diagnostic=_value(ids['query'],products,method,profiles[method],pair['reference_id'],pair['query_id'],pair['target_support_pin'],b)
                anchor=None;anchor_diagnostic=None
                if group['endpoint']=='S7':
                    used.add(ids['anchor']);anchor,anchor_diagnostic=_value(ids['anchor'],products,method,profiles[method],pair['reference_id'],pair['reference_id'],None,b,'anchor')
                    if value is not None and anchor is not None:
                        from .nomad_statistics import _anchor_decrease_rows
                        value=_anchor_decrease_rows(products[ids['anchor']],products[ids['query']],b)
                    else:value=None
                record={'pair_id':pair['pair_id'],'method':method,'value':None if value is None else {'exact':rational(value,b),**projected(value)},
                        'query':diagnostic,'anchor':anchor_diagnostic}
                entries[pair['pair_id']]=(value,record)
                if value is None:failures.append(record)
                else:valid.append(value)
                if group['endpoint']=='S7':decreases.append({'group_id':gid,**record})
            cache[method]=entries
            summaries.append({'group_id':gid,'method':method,'kind':'all_complete_group_pairs',**_summary(valid,failures,n,policy,b),
                              'full_pair_values':[row for _,row in entries.values()]})
            for kind,ids in actual['summary_products'][method].items():
                values=[];failed=[]
                for pid in ids:
                    used.add(pid)
                    if pid not in products:failed.append({'product_id':pid,'status':'unavailable_missing_product'});continue
                    s=products[pid]['support'];need(s['task']==actual['unit_id'] and s['source_pin']==roster['source_pin'],'summary_actual_unit_source')
                    need(s['method']==method and s['method_profile_pin']==profiles[method]['profile_pin'],'summary_method_source_join')
                    expected_role={'anchors':'anchor','calibration':'calibration','first_evaluation':'first_evaluation'}[kind]
                    need(s['role']==expected_role,'separate_summary_support_role')
                    if kind=='anchors':need(s['reference_id']==s['query_id'],'within_day_anchor_identity')
                    if group['endpoint']=='F5' and kind=='first_evaluation':need(s['query_id']==actual['evaluation_order'][0],'exact_first_human_evaluation')
                    v,diagnostic=_value(pid,products,method,profiles[method],s['reference_id'],s['query_id'],None,b,expected_role)
                    if v is None:failed.append(diagnostic)
                    else:values.append(v)
                summaries.append({'group_id':gid,'method':method,'kind':kind,**_summary(values,failed,len(ids),policy,b)})
        group_values[gid]=cache
    # An extra score dictionary/product cannot enter unnoticed as hidden support.
    need(set(products)<=used,'unselected_or_tampered_product_identity',unused=sorted(set(products)-used))
    tests=[]
    for test in roster['tests']:
        group=next(g for g in roster['groups'] if g['group_id']==test['group_id']);cache=group_values[test['group_id']]
        out={**test,'paired_values':[],'differences':[],'invalid_pairs':[],'statistic':None,
             'unresolved_original_topics':group['unresolved_original_topics'],'independent_subject_superiority_claim':False}
        if not cache:out['status']=group['status'];tests.append(out);continue
        support=group['support'];ids=support['test_pair_ids'];differences=[]
        b.take(items=len(ids),metadata_bytes=1024*len(ids));b.hold(1024*len(ids))
        for pid in ids:
            first,fr=cache[test['first']][pid];second,sr=cache[test['second']][pid]
            out['paired_values'].append({'pair_id':pid,'first':fr,'second':sr})
            if first is None or second is None:out['invalid_pairs'].append(pid);out['differences'].append({'pair_id':pid,'value':None})
            elif test['source_direction_held']:
                out['differences'].append({'pair_id':pid,'value':None,'status':'historical_argument_order_unadmitted'})
            else:
                difference=b.add(first,-second);differences.append(difference)
                out['differences'].append({'pair_id':pid,'value':{'exact':rational(difference,b),**projected(difference)}})
        if out['invalid_pairs']:out['status']='unavailable_incomplete_paired_values'
        elif test['source_direction_held']:out['status']='unavailable_S3_historical_argument_order'
        elif selected is None:out['status']='unavailable_historical_statistical_profile'
        elif profile_error is not None:out['status']=profile_error
        else:
            profile=dict(selected);profile['alternative']=test['alternative']
            # A test-only or prospective exact operator never qualifies original
            # historical tests merely because the score/support arrays exist.
            if roster['mode']=='original':profile['scope']='original_unresolved'
            out['statistic']=signed_rank(differences,profile,b);out['status']=out['statistic']['status']
        out['expected_pairs']=len(ids);out['computed_pairs']=len(differences);tests.append(out)
    all_decreases=[];by={(x['group_id'],x['pair_id'],x['method']):x for x in decreases}
    for slot in roster['s7_decrease_slots']:
        group=next(g for g in roster['groups'] if g['group_id']==slot['group_id'])
        actual=group['support'];record=None
        if group['status']=='structurally_bound_source_support':
            pid=actual['pairs'][slot['pair_ordinal']]['pair_id'];record=by.get((slot['group_id'],pid,slot['method']))
        all_decreases.append({**slot,'computed_record':record})
    heatmaps={}
    for task in ('isometric','reaching'):
        cells=[[{'status':'not_tested_diagonal','test_id':None,'pvalue':None} if i==j else None for j in range(8)] for i in range(8)]
        for test in tests:
            if test['group_id']!='S7/'+task:continue
            i=S7.index(test['first']);j=S7.index(test['second']);stat=test['statistic']
            cell={'status':test['status'],'test_id':test['test_id'],'pvalue':None if stat is None else stat['pvalue']}
            cells[i][j]=dict(cell);cells[j][i]=dict(cell)
        heatmaps[task]={'labels':list(S7),'cells':cells,'visual_outlier_exclusion_applied':False}
    result={'schema':'nomad_computed_statistical_study_v1','tests':tests,'nominal_tests':102,'s7_decreases':all_decreases,
      's7_decrease_count':304,'s7_heatmaps':heatmaps,'summaries':summaries,
      'human_stability':roster['human_stability_slots'],'additional_summary_obligations':roster['additional_summary_obligations'],
      'full_original_profile_complete':False,'original_parity':False,'original_unresolved_ids':roster['original_unresolved_ids'],
      'statistical_selection_pin':captured['selection_pin'],'support_selection_pin':roster['facts_selection_pin'],
      'multiplicity_adjustment':None,'independent_subject_superiority_claim':False,'budget_prefix':b.snapshot()}
    encode(result,b) # preventive complete output encoding/copy bound, no artifact write
    return result
