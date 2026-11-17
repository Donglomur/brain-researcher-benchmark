"""Matched multi-round tools and final candidate claims; evaluator outcomes never enter replies."""
import math
from protocol import TARGETS, FEATURES, ARMS, canonical, digest, exact_keys, finite, need

class Investigation:
    def __init__(self,case,reference,cap,training_context=None):
        self.case=case;self.reference=reference;self.cap=cap;self.calls=0;self.history=[]
        self.training_context=training_context or case
        self.finished=False

    def request(self,message):
        need(not self.finished,'after_final_submission')
        exact_keys(message,('tool','arguments'),'tool_request_fields')
        self.calls+=1;need(self.calls<=self.cap,'tool_call_cap')
        name=message['tool'];arguments=message['arguments']
        if name=='training_summary':
            exact_keys(arguments,(),'summary_arguments')
            # Each source bootstrap copy is a fit cluster; no held target or held missingness is present.
            train=self.training_context['training']
            reply={'training_rows':len(train),'training_clusters':len(self.training_context['clusters']),
                'features':{key:{'mean':math.fsum(row[key] for row in train)/len(train),
                    'minimum':min(row[key] for row in train),
                    'maximum':max(row[key] for row in train)} for key in FEATURES}}
        elif name=='reference_prediction':
            exact_keys(arguments,('arm',),'reference_arguments');arm=arguments['arm'];need(arm in ARMS,'reference_arm')
            reply={'arm':arm,'source_rows':self.reference['source_rows'],
                'components':{target:self.reference['results'][target]['arms'][arm] for target in TARGETS},
                'training_only_fitted':True,'cost':'reference preparation charged once; tool read charged in each mode'}
        elif name=='predictive_coefficients':
            exact_keys(arguments,(),'coefficient_arguments')
            reply={'contrasts':self.reference['predictive_coefficient_contrasts'],
                'scope':'Predictive J ML/random-intercept, not original paper REML/random-slope reconstruction.'}
        else:
            raise ValueError('unknown_tool')
        record={'request':message,'response':reply,'response_sha256':digest(reply)}
        self.history.append(record)
        return {'sequence':self.calls,'response':reply,'response_sha256':record['response_sha256']}

    def finish(self,message):
        exact_keys(message,('submit',),'submission_envelope')
        value=message['submit']
        exact_keys(value,('status','predictions','investigation'),'submission_fields')
        report=value['investigation']
        exact_keys(report,('estimand','limitations','alternative_explanations','claims'),'investigation_fields')
        for field in ('estimand','limitations','alternative_explanations'):
            need(type(report[field]) is str and 0<len(report[field].encode())<=4096,'bounded_report_text')
        need(type(report['claims']) is list and len(report['claims'])<=64,'bounded_claims')
        for claim in report['claims']:
            exact_keys(claim,('evidence_sequence','response_sha256','path','value'),'claim_fields')
            seq=claim['evidence_sequence'];need(type(seq) is int and 1<=seq<=len(self.history),'claim_evidence')
            record=self.history[seq-1];need(claim['response_sha256']==record['response_sha256'],'claim_pin')
            expected=record['response'];path=claim['path']
            need(type(path) is list and 1<=len(path)<=16,'claim_path')
            for part in path:
                need((type(expected) is dict and type(part) is str and part in expected) or
                     (type(expected) is list and type(part) is int and 0<=part<len(expected)),'claim_lookup')
                expected=expected[part]
            actual=claim['value']
            if finite(expected):
                need(finite(actual) and abs(actual-expected)<=1e-8+1e-9*abs(expected),'numeric_claim_disagreement')
            else:
                need(type(expected) in (str,bool,type(None)) and actual==expected and type(actual)==type(expected),'claim_disagreement')
        self.finished=True
        return {'status':value['status'],'predictions':value['predictions']},report
