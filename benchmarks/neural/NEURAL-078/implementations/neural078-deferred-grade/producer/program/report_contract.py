"""Exact source-derived public report validation only; no matching or grading."""
import json,re
import numpy as np

PROTOCOL_SHA256='3424a79612d5a157377fd32615834652623edfb2fd662b56d89c2acf06fb71e2'

PEOPLE=tuple('sub-'+p for p in ('001','002','003','004','005','006','007','010'))

STRATA=('hand1_congruency1','hand1_congruency2','hand2_congruency1','hand2_congruency2')

COUNTS=('eligible_error_n','eligible_correct_n','matched_pairs_n')

NUMBERS=('mean_RT_difference_ms','max_abs_RT_difference_ms','unmatched_FCz_contrast',
         'matched_FCz_contrast','matched_HEOG_contrast','matched_VEOG_contrast',
         'matched_preresponse_FCz_placebo')

def need(condition,message):
    if not condition:raise ValueError(message)

def strict_json_bytes(raw):
    need(type(raw) is bytes and len(raw)<=65536,'Captured 64KiB JSON')
    def pairs(items):
        result={}
        for k,v in items:
            need(k not in result,'Duplicate JSON key');result[k]=v
        return result
    def invalid_constant(value):raise ValueError('Nonfinite JSON constant')
    return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=invalid_constant)

def validate_report(report):
    need(type(report) is dict and set(report)=={'schema','protocol_sha256','participants','aggregate'},'Exact report keys')
    need(report['schema']=='neural078_contrast_submission_v1' and report['protocol_sha256']==PROTOCOL_SHA256,'Exact report version')
    records=report['participants']
    need(type(records) is list and len(records)==8,'All eight participant records')
    seen=[]
    for row in records:
        need(type(row) is dict and set(row)==set(COUNTS+NUMBERS+('participant_id','pair_digest','stratum_support','status')),'Exact participant fields')
        need(row['participant_id'] in PEOPLE,'Known participant');seen.append(row['participant_id'])
        for k in COUNTS:need(type(row[k]) is int and 0<=row[k]<=512,'Bounded count '+k)
        need(row['eligible_error_n']+row['eligible_correct_n']<=512,'Total trial bound')
        need(row['matched_pairs_n']<=min(row['eligible_error_n'],row['eligible_correct_n']),'Pair support bound')
        need(type(row['pair_digest']) is str and re.fullmatch(r'[0-9a-f]{64}',row['pair_digest']) is not None,'Pair identity digest')
        support=row['stratum_support'];need(type(support) is dict and set(support)==set(STRATA),'All four strata')
        for s in support.values():
            need(type(s) is dict and set(s)=={'error_n','correct_n','pairs_n'},'Exact stratum fields')
            need(all(type(v) is int and 0<=v<=512 for v in s.values()),'Bounded stratum counts')
            need(s['pairs_n']<=min(s['error_n'],s['correct_n']),'Stratum pair support')
        for total,sub in [('eligible_error_n','error_n'),('eligible_correct_n','correct_n'),('matched_pairs_n','pairs_n')]:
            need(row[total]==sum(s[sub] for s in support.values()),'Stratum totals')
        supported=row['matched_pairs_n']>=10
        need(row['status']==('supported' if supported else 'insufficient_matched_pairs'),'Status matches frozen support threshold')
        for k in NUMBERS:
            v=row[k]
            need((type(v) in (int,float) and np.isfinite(v)) if supported else v is None,'Finite supported values; null unsupported')
    need(len(set(seen))==8 and set(seen)==set(PEOPLE),'Exactly one record per person')
    a=report['aggregate'];need(type(a) is dict and set(a)=={'status','matched_FCz_equal_person_mean','matched_FCz_between_person_descriptive_SE'},'Exact aggregate fields')
    supported=all(r['status']=='supported' for r in records)
    need(a['status']==('all_participants_supported' if supported else 'not_all_participants_supported'),'Aggregate support status')
    for k in ('matched_FCz_equal_person_mean','matched_FCz_between_person_descriptive_SE'):
        v=a[k];need((type(v) in (int,float) and np.isfinite(v)) if supported else v is None,'Finite/null aggregate')
    need(not supported or a['matched_FCz_between_person_descriptive_SE']>=0,'Nonnegative descriptive SE')
    return report
