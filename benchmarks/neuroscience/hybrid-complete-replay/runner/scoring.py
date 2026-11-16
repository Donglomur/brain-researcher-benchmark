"""Protected aggregate scoring; labels stay in the trusted evaluator."""
from collections import defaultdict
import math
import random
from consumer import GROUPS, MAIN_ELIGIBLE, MAIN_TRIALS, ContractError, probability_vector, validate_decisions

def score_complete(decisions, predictions, *, expected_decisions=MAIN_ELIGIBLE, expected_trials=MAIN_TRIALS):
    """Score exactly one committed probability vector for every eligible row.

    Predictions is an iterable of (private source_row, four probabilities), emitted
    only by the trusted OnlineSession after complete response commitment.
    """
    validate_decisions(decisions,expected_eligible=expected_decisions,expected_trials=expected_trials)
    truth={d.source_row:d for d in decisions}
    if len(truth)!=len(decisions):raise ContractError("truth row collision")
    pred={}
    for row,p in predictions:
        if type(row) is not int or row not in truth or row in pred:
            raise ContractError("unknown/duplicate prediction")
        pred[row]=probability_vector(p)
    if set(pred)!=set(truth):raise ContractError("incomplete prediction population")
    session=defaultdict(list);trials=defaultdict(list);confusion=[[0]*4 for _ in range(4)]
    stop_brier=[];correct=0
    for row,d in truth.items():
        p=pred[row];loss=-math.log(p[d.action-1]);guess=max(range(4),key=lambda k:p[k])+1
        session[(d.subject,d.session)].append(loss)
        trials[(d.subject,d.session,d.trial)].append(loss)
        confusion[d.action-1][guess-1]+=1;correct+=guess==d.action
        stop_brier.append((p[2]+p[3]-(d.action in (3,4)))**2)
    if set(session)!=GROUPS:raise ContractError("incomplete20x4 scored population")
    means={g:math.fsum(v)/len(v) for g,v in session.items()}
    subject={str(s):math.fsum(means[(str(s),k)] for k in range(1,5))/4 for s in range(1,21)}
    # Secondary trial balance is also participant/session-balanced.
    trial_by_session=defaultdict(list)
    for (s,k,t),values in trials.items():trial_by_session[(s,k)].append(math.fsum(values)/len(values))
    trial_means={g:math.fsum(v)/len(v) for g,v in trial_by_session.items()}
    recalls=[confusion[i][i]/sum(confusion[i]) if sum(confusion[i]) else None for i in range(4)]
    return {"schema":"hybrid-protected-main-score-v1",
        "primary_subject_session_mean_nll":math.fsum(subject.values())/20,
        "subject_mean_nll":subject,
        "session_mean_nll":{s+":"+str(k):means[(s,k)] for s,k in sorted(GROUPS)},
        "trial_balanced_nll":math.fsum(trial_means.values())/80,
        "decision_weighted_nll":math.fsum(math.fsum(v) for v in session.values())/len(decisions),
        "accuracy":correct/len(decisions),"per_action_recall":recalls,
        "macro_action_recall":math.fsum(v for v in recalls if v is not None)/sum(v is not None for v in recalls),
        "stop_brier":math.fsum(stop_brier)/len(stop_brier),
        "confusion":confusion,"participants":20,"sessions":80,
        "trials":len(trials),"decisions":len(decisions),
        "scoring_unit_for_uncertainty":"participant, not row/fold/coding",
        "claim":"conditional next-action prediction on selected completed two-option trials",
        "benchmark_ready":False,"scientific_count_delta":0}

def paired_comparison(candidate, reference, *, bootstrap_draws=10000, seed=20261114):
    """Predeclared paired participant bootstrap; no tuning or row pseudoreplication."""
    if type(bootstrap_draws) is not int or not 1000<=bootstrap_draws<=100000:raise ContractError("bootstrap budget")
    expected={str(s) for s in range(1,21)}
    if set(candidate["subject_mean_nll"])!=expected or set(reference["subject_mean_nll"])!=expected:
        raise ContractError("all20 paired participants required")
    if any(candidate[k]!=reference[k] for k in ("participants","sessions","trials","decisions")):
        raise ContractError("paired evaluation population differs")
    delta=[candidate["subject_mean_nll"][str(s)]-reference["subject_mean_nll"][str(s)] for s in range(1,21)]
    if not all(math.isfinite(v) for v in delta):raise ContractError("nonfinite comparison")
    rng=random.Random(seed)
    draws=sorted(math.fsum(delta[rng.randrange(20)] for _ in range(20))/20 for _ in range(bootstrap_draws))
    def quantile(q):
        pos=q*(len(draws)-1);i=int(pos);a=pos-i
        return draws[i]*(1-a)+draws[min(i+1,len(draws)-1)]*a
    return {"candidate_minus_reference_nll":math.fsum(delta)/20,
        "paired_participant_percentile95":[quantile(.025),quantile(.975)],
        "participants":20,"bootstrap_draws":bootstrap_draws,"seed":seed,
        "interpretation":"negative favors candidate; exploratory interval does not itself establish frontier improvement",
        "scientific_claim_requires":"qualified strongest references, locked selection budget and independent repeated-seed evidence",
        "count_delta":0}

