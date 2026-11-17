"""Meaningful proposed complete-path synthetic controls. Never imports real data."""
from dataclasses import replace
import io,json,math,tempfile
from pathlib import Path
import unittest
from consumer import *
from scoring import score_complete,paired_comparison
from reference import Uniform,ContextCounts,fit_ridge,mean_nll,design,relative_action
from cognitive import subjective,predict,logits

def fixture_lines():
    rows=[];row=0
    for subject in map(str,range(1,21)):
        for session in range(1,5):
            for phase in range(11):
                row+=1;group={"subject":subject,"session":str(session),"trial":1}
                rec={"schema":"hybrid-private-source-case-map-v1","private_only":True,
                     "ct1":{"source_row_1based":row},"ct2":{"source_row_1based":row},
                     "coding_mismatches":[],"group":group}
                if phase in (0,1,10):rec["source_eligibility"]="EXCLUDED"
                else:
                    i=phase-2;left=i in (0,1,2,6,7);nL=2+i;nR=3+i;rL=i%2;rR=(i+1)%3
                    x={"nL":nL,"nR":nR,"nB":10,"rL":rL,"rR":rR,
                       "muL":(rL+1)/(nL+2),"muR":(rR+1)/(nR+2),
                       "gL":left,"gR":not left,"first_visit":i<3,"after_first_visit":i>=3,
                       "t":(0,1,2,0,1,2,0,1)[i]}
                    if i==0:x.update(nR=60,rR=0,muR=.5) # Initial cue is not evidence.
                    next_left=(i+1) in (0,1,2,6,7)
                    action=(1 if next_left else 2) if i<7 else (3 if int(subject)%2 else 4)
                    rec.update(source_eligibility="ELIGIBLE",predictors=x,action=action,
                               row_mapping_qualified=True,row_mapping_problems=[])
                rows.append(json.dumps(rec,allow_nan=False,separators=(",",":")).encode()+b"\n")
    return rows

def cohort():
    return parse_private_stream(fixture_lines(),expected_rows=880,expected_eligible=640,expected_trials=80)

def synthetic_score(ds,preds):
    return score_complete(ds,preds,expected_decisions=640,expected_trials=80)

class FullPathControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.ds=cohort()
    def test_full_serialized_twocoding20x4_to_queries_and_score(self):
        all_predictions=[]
        for s,k in sorted(GROUPS):
            train,test=outer_fold(self.ds,s,k);model=ContextCounts(train)
            protocol=OnlineSession(test,b"fixture-key-never-authentic-data!!")
            while True:
                q=protocol.next_query()
                if q is None:break
                self.assertEqual(set(q),{"schema","token","new_trial","observation"})
                self.assertEqual(set(q["observation"]),set(FEATURES))
                protocol.commit({"token":q["token"],"probabilities":model.predict(q["observation"])})
            all_predictions.extend((d.source_row,p) for d,p in protocol.finished_predictions())
        result=synthetic_score(self.ds,all_predictions)
        self.assertEqual((result["participants"],result["sessions"],result["trials"],result["decisions"]),(20,80,80,640))
        self.assertTrue(math.isfinite(result["primary_subject_session_mean_nll"]))
    def test_uniform_complete_primary_and_secondary_known_answer(self):
        r=synthetic_score(self.ds,[(d.source_row,[.25]*4) for d in self.ds])
        for k in ("primary_subject_session_mean_nll","trial_balanced_nll","decision_weighted_nll"):
            self.assertAlmostEqual(r[k],math.log(4),places=12)
    def test_oracle_negative_control_better_is_not_a_candidate_result(self):
        preds=[(d.source_row,[.97 if i==d.action-1 else .01 for i in range(4)]) for d in self.ds]
        r=synthetic_score(self.ds,preds);self.assertAlmostEqual(r["primary_subject_session_mean_nll"],-math.log(.97),places=12)
    def test_missing_group_and_missing_decision_refused(self):
        with self.assertRaises(ContractError):validate_decisions(self.ds[1:],expected_eligible=640,expected_trials=80)
        with self.assertRaises(ContractError):synthetic_score(self.ds,[(d.source_row,[.25]*4) for d in self.ds[:-1]])
    def test_duplicate_and_unknown_prediction_refused(self):
        p=[(d.source_row,[.25]*4) for d in self.ds]
        for altered in (p+[p[0]],p[:-1]+[(999999,[.25]*4)]):
            with self.assertRaises(ContractError):synthetic_score(self.ds,altered)
    def test_authentic_defaults_do_not_accept_small_fixture(self):
        with self.assertRaises(ContractError):score_complete(self.ds,[(d.source_row,[.25]*4) for d in self.ds])
    def test_wrong_accepted_file_hash_refuses_before_population_construction(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"invented.jsonl";p.write_bytes(b"".join(fixture_lines()))
            with self.assertRaises(ContractError):load_accepted_private_cases(p)
    def test_no_query_lookahead_before_commit(self):
        protocol=OnlineSession(self.ds[:8],b"x"*32);q=protocol.next_query()
        with self.assertRaises(ContractError):protocol.next_query()
        self.assertNotIn("action",q);self.assertNotIn("remaining",q);self.assertNotIn("event",q)
    def test_wrong_token_and_duplicate_reply_refused(self):
        p=OnlineSession(self.ds[:8],b"x"*32);q=p.next_query()
        with self.assertRaises(ContractError):p.commit({"token":"wrong","probabilities":[.25]*4})
        with self.assertRaises(ContractError):p.next_query()
        p=OnlineSession(self.ds[:8],b"x"*32);q=p.next_query()
        p.commit({"token":q["token"],"probabilities":[.25]*4})
        with self.assertRaises(ContractError):p.commit({"token":q["token"],"probabilities":[.25]*4})
    def test_incomplete_session_cannot_return_predictions(self):
        p=OnlineSession(self.ds[:8],b"x"*32);p.next_query()
        with self.assertRaises(ContractError):p.finished_predictions()
    def test_future_state_and_label_perturbation_cannot_change_current_query(self):
        test=list(self.ds[:8]);x=test[-1].observation();x["nL"]=30;x["muL"]=(x["rL"]+1)/32
        changed=test[:-1]+[replace(test[-1],action=4,values=tuple(x[k] for k in FEATURES))]
        a=OnlineSession(test,b"x"*32);b=OnlineSession(changed,b"x"*32)
        self.assertEqual(a.next_query(),b.next_query())
    def test_outer_labels_unavailable_to_training_projection(self):
        train,test=outer_fold(self.ds,"1",1)
        changed=[replace(d,action=4 if d.action==3 else 3) if d.subject=="1" and d.session==1 and d.action>=3 else d for d in self.ds]
        train2,_=outer_fold(changed,"1",1)
        self.assertEqual(training_view(train),training_view(train2))
        self.assertEqual({r["training_session_group"] for r in training_view(train)},{1,2,3})
    def test_no_source_identifier_in_public_observation(self):
        p=OnlineSession(self.ds[:8],b"x"*32);q=p.next_query()
        self.assertEqual(len(q["token"]),64)
        self.assertTrue(set(q["observation"]).isdisjoint({"subject","session","trial","source_row","choice","stay","sss","n_samples","n_visits","outcome","accuracy","rt","event"}))
    def test_current_observation_return_is_not_mutable_private_state(self):
        p=OnlineSession(self.ds[:8],b"x"*32);q=p.next_query();q["observation"]["nB"]=99
        self.assertEqual(self.ds[0].observation()["nB"],10)
    def test_green_cover_branch_not_false_posterior_identity(self):
        x=self.ds[0].observation();self.assertEqual(x["muR"],.5)
        self.assertNotEqual(x["muR"],(x["rR"]+1)/(x["nR"]+2));validate_observation(x)
    def test_invalid_evidence_and_missingness_refuse(self):
        x=self.ds[1].observation()
        for patch in ({"rL":101},{"muL":.99},{"nL":float("nan")},{"gL":1},{"muR":0}):
            with self.assertRaises(ContractError):validate_observation({**x,**patch})
    def test_prefix_clock_and_first_visit_gate(self):
        for name,value in (("t",999),("first_visit",True)):
            ds=list(self.ds);x=ds[6].observation();x[name]=value
            if name=="first_visit":x["after_first_visit"]=False
            ds[6]=replace(ds[6],values=tuple(x[k] for k in FEATURES))
            with self.assertRaises(ContractError):validate_decisions(ds,expected_eligible=640,expected_trials=80)
    def test_terminal_is_last_and_never_a_current_predictor(self):
        ds=list(self.ds);ds[0]=replace(ds[0],action=3)
        with self.assertRaises(ContractError):validate_decisions(ds,expected_eligible=640,expected_trials=80)
    def test_blocked_cue_change_is_not_silently_accepted(self):
        ds=list(self.ds);x=ds[3].observation();x["nB"]=11
        ds[3]=replace(ds[3],values=tuple(x[k] for k in FEATURES))
        with self.assertRaises(ContractError):validate_decisions(ds,expected_eligible=640,expected_trials=80)
    def test_probability_failures_are_whole_errors(self):
        for p in ([0,.2,.3,.5],[.25]*3,[True,.2,.3,.5],[float("nan"),.2,.3,.5],[.2]*4):
            with self.assertRaises(ContractError):probability_vector(p)
    def test_duplicate_json_key_nonfinite_and_oversized_reply_refused(self):
        for b in (b'{"token":"a","token":"b"}',b'{"x":NaN}',b"x"*4097):
            with self.assertRaises((ContractError,ValueError)):decode_reply(b)
    def test_paired_uncertainty_is20_participants(self):
        r=synthetic_score(self.ds,[(d.source_row,[.25]*4) for d in self.ds])
        c=paired_comparison(r,r,bootstrap_draws=1000)
        self.assertEqual(c["participants"],20);self.assertEqual(c["paired_participant_percentile95"],[0,0])
    def test_relative_action_and_side_swap(self):
        x=self.ds[1].observation();flipped={**x,"gL":False,"gR":True}
        self.assertEqual(relative_action(1,x),relative_action(2,flipped))
    def test_active_cognitive_first_visit_known_values(self):
        x=self.ds[1].observation();nl,nr,rl,rr=subjective(x,.4,.3,.2)
        self.assertEqual(nl,2+x["nL"]);self.assertEqual(rl,1+x["rL"])
        self.assertAlmostEqual(nr,2+.3*x["nR"]+.7*x["nB"])
        self.assertAlmostEqual(rr/nr,.5+(x["muL"]-.5)*.4)
    def test_active_decay_preserves_prior_not_whole_count(self):
        x=self.ds[7].observation();nl,nr,rl,rr=subjective(x,.4,.3,.2)
        self.assertAlmostEqual(nr,2+x["nR"]*math.exp(-.2*x["t"]))
        self.assertAlmostEqual(rr,1+x["rR"]*math.exp(-.2*x["t"]))
    def test_cognitive_left_right_exchange_and_probability_sum(self):
        x=self.ds[1].observation();y=dict(x)
        for a,b in (("nL","nR"),("rL","rR"),("muL","muR"),("gL","gR")):y[a],y[b]=x[b],x[a]
        for family,theta in (("linear",[.1,.2,.3,-1.,.2,-.3,.1]),("ucb",[.1,.2,.3,-1.,.7,.1])):
            p=predict(x,theta,family);q=predict(y,theta,family)
            self.assertAlmostEqual(sum(p),1)
            for a,b in zip(p,(q[1],q[0],q[3],q[2])):self.assertAlmostEqual(a,b)
    def test_ridge_convergence_on_invented_training_only(self):
        train,_=outer_fold(self.ds,"1",1);model=fit_ridge(train,1.)
        self.assertTrue(model.fit_trace["converged"])
        self.assertLessEqual(model.fit_trace["final_objective"],model.fit_trace["initial_objective"])
        self.assertLess(mean_nll(model,train),math.log(4))
    def test_ridge_normalization_and_fit_invariant_to_row_order(self):
        train,_=outer_fold(self.ds,"1",1)
        a=fit_ridge(train,1.);b=fit_ridge(tuple(reversed(train)),1.)
        for x,y in zip(a.predict(train[0].observation()),b.predict(train[0].observation())):self.assertAlmostEqual(x,y,places=10)
    def test_ridge_budget_failure_cannot_drop_subject(self):
        train,_=outer_fold(self.ds,"1",1)
        with self.assertRaises(ContractError):fit_ridge(train,1.,max_iter=0)

    def test_complete80fold_absent_class_finite_convergence_and_full_gradient(self):
        import numpy as np
        checked=0;absent_counts=[]
        for subject,held in sorted(GROUPS):
            train,test=outer_fold(self.ds,subject,held)
            y=np.asarray([relative_action(d.action,d.observation()) for d in train])
            absent=set(range(4))-set(map(int,y));self.assertTrue(absent)
            self.assertEqual(len(train),24);self.assertEqual(len(test),8)
            model=fit_ridge(train,1.)
            self.assertEqual(model.weights.shape,(25,4))
            self.assertTrue(np.isfinite(model.weights).all())
            self.assertTrue(model.fit_trace["converged"])
            self.assertEqual(model.fit_trace["training_rows"],24)
            self.assertEqual(model.fit_trace["penalty_scope"],"all coefficients, including four class intercepts")
            raw=np.asarray([design(d.observation()) for d in train],dtype=np.float64)
            x=(raw-model.mean)/model.scale;w=model.weights
            z=x@w;maximum=z.max(axis=1);e=np.exp(z-maximum[:,None]);p=e/e.sum(axis=1)[:,None]
            residual=p.copy();residual[np.arange(len(y)),y]-=1
            # Independent stationarity check includes the intercept row.
            gradient=x.T@residual/len(y)+w
            self.assertLessEqual(float(np.max(np.abs(gradient))),1e-6)
            self.assertGreater(float(np.max(np.abs(w[0]))),0)
            for d in test:
                probs=model.predict(d.observation())
                self.assertEqual(len(probs),4)
                self.assertTrue(all(math.isfinite(v) and 0<v<1 for v in probs))
                self.assertAlmostEqual(math.fsum(probs),1,places=12)
            if checked==0:
                def objective(weight):
                    logits_=x@weight;m=logits_.max(axis=1)
                    return float(np.mean(m+np.log(np.exp(logits_-m[:,None]).sum(axis=1))-logits_[np.arange(len(y)),y])+.5*np.sum(weight**2))
                for col in range(4):
                    high=w.copy();low=w.copy();high[0,col]+=1e-5;low[0,col]-=1e-5
                    finite_difference=(objective(high)-objective(low))/(2e-5)
                    self.assertAlmostEqual(finite_difference,float(gradient[0,col]),delta=1e-7)
            checked+=1;absent_counts.append(len(absent))
        self.assertEqual(checked,80);self.assertTrue(all(v>=1 for v in absent_counts))

    def test_complete_unequal_trial_lengths_distinguish_score_weighting(self):
        # All80 groups remain. Add one two-decision trial to one group, whose
        # existing trial has eight decisions. Only that added trial has lower loss.
        ds=list(self.ds);row=max(d.source_row for d in ds)+1
        first=replace(ds[0],source_row=row,trial=2,action=1)
        x=first.observation();x["t"]=1
        last=replace(first,source_row=row+1,action=3,values=tuple(x[k] for k in FEATURES))
        ds.extend((first,last));preds=[(d.source_row,[.25]*4) for d in self.ds]
        preds.extend((d.source_row,[.5 if k==d.action-1 else 1/6 for k in range(4)]) for d in (first,last))
        result=score_complete(ds,preds,expected_decisions=642,expected_trials=81)
        usual,better=math.log(4),math.log(2)
        self.assertAlmostEqual(result["primary_subject_session_mean_nll"],usual+(better-usual)/400,places=12)
        self.assertAlmostEqual(result["trial_balanced_nll"],usual+(better-usual)/160,places=12)
        self.assertAlmostEqual(result["decision_weighted_nll"],(640*usual+2*better)/642,places=12)
        self.assertNotAlmostEqual(result["primary_subject_session_mean_nll"],result["decision_weighted_nll"],places=8)
        uniform=score_complete(ds,[(d.source_row,[.25]*4) for d in ds],expected_decisions=642,expected_trials=81)
        comparison=paired_comparison(result,uniform,bootstrap_draws=1000)
        self.assertAlmostEqual(comparison["candidate_minus_reference_nll"],(better-usual)/400,places=12)
        low,high=comparison["paired_participant_percentile95"]
        self.assertLessEqual((better-usual)/20,low);self.assertLess(low,0);self.assertLessEqual(high,0)
        self.assertEqual(comparison["participants"],20)

