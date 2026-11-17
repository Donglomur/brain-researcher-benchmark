"""Future trusted integration only; never imported or invoked by collection route.

Caller must separately authorize private grading and authenticate a source-bound
successful outer closure plus all captured documents. This function is not a CLI
and metadata claims alone are not custody evidence. No target callback is invoked
until both complete outputs are admitted. Original scalar metric is unchanged.
"""
def score(candidate,operator,public,private_loader,core,contract):
    answers,fixed=contract.admit_pair(candidate,operator,public,core)
    target=private_loader()
    core.validate_targets(target,public)
    # Cross-check independently produced public-only reference against the exact
    # original five-public-block analytic comparator after private authority.
    for row in target['sessions']:
        expected=core.baseline(row['calibration_peaks'],row['calibration_active'])
        for q in row['queries']:
            core.need(fixed[q['query_id']]==expected,'independent operator baseline exact original-public-reference agreement')
    candidate_result=core.grade(candidate,public,lambda:target)
    operator_result=core.grade(operator,public,lambda:target)
    core.need(candidate_result['baseline_rank_mae']==operator_result['primary_rank_mae'],'same source baseline and full support')
    return {'candidate':candidate_result,'operator':operator_result,'private_scoring_performed':True,'scientific_qualified':False}
