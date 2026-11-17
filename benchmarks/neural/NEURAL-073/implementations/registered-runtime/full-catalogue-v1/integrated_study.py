"""Selected additive key-serialization repair; no scientific body changes.

Parent FullStudy.__init__ and execute are inherited unchanged. evaluate is AST
identical except the single flatten expression. Full execution remains selected
and qualified independently; importing this module invokes no study or NumPy.
"""
from .runtime.runner.study import FullStudy
from .runtime.core.custody import CustodyError,digest
from .runtime.core.plan import CONDITIONS,ARMS,REPETITIONS,FAMILIES
from .runtime import scoring


def serialize_panel_key(parts):
    """Closed fixed-key serializer: repetition integers become decimal text."""
    if type(parts) is not tuple or not parts:
        raise CustodyError('nonempty fixed panel tuple required')
    result=[]
    for part in parts:
        if type(part) is str and part and '|' not in part:
            result.append(part)
        elif type(part) is int and part in (0,1,2):
            result.append(format(part,'d'))
        else:
            raise CustodyError('unsupported fixed panel key component')
    return '|'.join(result)


class IntegratedFullStudy(FullStudy):
    """Only this fixed integrated constructor is selected by the task loader."""
    def evaluate(self,closure,reference_receipt):
            if not self.feedback_open:raise CustodyError('feedback requires all234 closed original contexts')
            if closure!=self.plan.assert_complete_closure({k:v['closure_digest'] for k,v in self.results.items()}):
                raise CustodyError('complete closure mismatch')
            records=self.data.score_records(tuple(r.case_id for r in self.plan.records))
            constructions={r.case_id:r.construction for r in self.plan.records}
            bindings={'records_digest':scoring.records_digest(records),'closure_digest':closure,'construction_digest':digest(constructions)}
            authority=self.issuer.capability('score','full_locked_scoring',bindings)
            def panel(values):
                return scoring.score_panel(records,values,authority=authority,closure_digest=closure,construction_by_case=constructions)
            candidate={};reference={};summaries={};comparisons={}
            for condition in CONDITIONS:
                for arm in ARMS:
                    panels=[]
                    for repetition in REPETITIONS:
                        values={}
                        for c in self.contexts:
                            if (c.condition,c.arm,c.repetition)==(condition,arm,repetition):
                                part=self.results[c.context_id]['submission']['probabilities']
                                if set(values)&set(part):raise CustodyError('overlapping held-person predictions')
                                values.update(part)
                        if set(values)!={r.case_id for r in records}:raise CustodyError('full9532-case panel including failures required')
                        p=panel(values);candidate[(condition,arm,repetition)]=p;panels.append(p)
                    summaries[(condition,arm)]=scoring.aggregate_repetitions(panels)
                comparisons[(condition,'I_minus_F')]=scoring.paired_comparison(
                    [candidate[(condition,'F',r)] for r in REPETITIONS],
                    [candidate[(condition,'I',r)] for r in REPETITIONS])
                views=('C',) if condition=='C_only' else ('N','C','NC')
                for view in views:
                    for family in FAMILIES+('training_selected_family',):
                        values={}
                        for person in self.plan.people:
                            actual=family
                            if family=='training_selected_family':actual=self.reference.best_families[(person,condition,view)]['family']
                            values.update(self.reference.results[(person,condition,view,actual)].query_probabilities)
                        rp=panel(values);reference[(condition,view,family)]=rp
                        for arm in ARMS:
                            comparisons[(condition,arm,view,family)]=scoring.compare_reference([candidate[(condition,arm,r)] for r in REPETITIONS],rp)
                for baseline in ('uniform','weighted_prior'):
                    values={}
                    for person in self.plan.people:
                        vector=[1/25]*25 if baseline=='uniform' else self.reference.priors[(person,condition)]['probabilities']
                        vector=scoring.probability_vector(vector)
                        values.update({rid:vector for rid in self.plan.fold(person).query_ids})
                    reference[(condition,baseline)]=panel(values)
            # Prespecified original-vs-control paired contrasts, averaged over exactly
            #3 repetitions within each person. Persons, not records/repetitions, are n.
            for arm in ARMS:
                for control in ('spatial_scrambled','C_only'):
                    base=summaries[('original',arm)];other=summaries[(control,arm)]
                    acc={p:base['people'][p]['accuracy']-other['people'][p]['accuracy'] for p in self.plan.people}
                    bri={p:other['people'][p]['brier_with_failure_penalty']-base['people'][p]['brier_with_failure_penalty'] for p in self.plan.people}
                    comparisons[(arm,'original_minus_'+control)]={'accuracy':scoring.person_uncertainty(acc),'brier':scoring.person_uncertainty(bri),
                        'interpretation':'conditional declared-label comparison; C is nuisance-enriched and supports may fingerprint acquisition'}
            flatten=lambda d:{serialize_panel_key(k):v for k,v in d.items()}
            final={'schema':'n073_full_declared_label_study_v1','scope':{'records':9532,'people':13,'protocols':25,'cells':300,'contexts':234},
                'closure_digest':closure,'reference_receipt':reference_receipt,'candidate_panels':flatten(candidate),
                'reference_panels':flatten(reference),'three_repetition_summaries':flatten(summaries),'paired_comparisons':flatten(comparisons),
                'claim_limit':'Declared-catalogue label recovery under documented whole-support controls; no causal/native-neural-understanding/population-validity or SOTA inference.'}
            self.store.put_json('full_study_results',final)
            return final
