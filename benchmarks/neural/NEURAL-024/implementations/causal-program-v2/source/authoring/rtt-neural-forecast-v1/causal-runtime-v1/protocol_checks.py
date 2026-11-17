"""Invented stdlib protocol guards; no recording reads, model fits or subprocesses."""
import copy
import hashlib
from protocol import PROTOCOL,ROUNDS,WARMUP,Gate,answer,wire,wrapped


def run_checks():
    from rtt_profile import returned_identity,agree_identities
    names=[]
    intervals=[[60+i*.02,60+(i+1)*.02] for i in range(ROUNDS)]
    def check(name,value):
        if value is not True:raise AssertionError(name)
        names.append(name)
    def rejects(call):
        try:call()
        except (ValueError,TypeError,OverflowError):return True
        return False
    def started():
        g=Gate(intervals);r=g.reveal('a'*32);return g,r
    def response(r):return {'sequence':r['sequence'],'nonce':r['nonce'],'mean_counts':[.5]*96}
    def committed(g,r):
        a=answer(wire(response(r)),r)
        record={'sequence':r['sequence'],'target_bin':r['target_bin'],'scored':r['scored'],'nonce':r['nonce'],
                'request_sha256':hashlib.sha256(wire(r)).hexdigest(),'mean_counts':a['mean_counts'],
                'previous_commit':g.previous,'revealed':1.,'received':2.}
        raw=wire(record);p={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        return a,raw,p
    g,r=started();a,raw,p=committed(g,r)
    check('exact96_positive_means_and_first_unscored_bin',a['mean_counts']==[.5]*96 and r['target_bin']==3000 and r['scored'] is False)
    check('feedback_forbidden_before_durable_prediction',rejects(lambda:g.feedback(0)))
    check('second_prediction_forbidden_while_pending',rejects(lambda:g.reveal('b'*32)))
    check('unfsynced_acknowledgement_cannot_commit',rejects(lambda:g.commit(a,raw,p,False)))
    wrong=dict(p,bytes=float(p['bytes']))
    check('float_byte_counter_is_not_an_exact_pin',rejects(lambda:g.commit(a,raw,wrong,True)))
    g.commit(a,raw,p,True)
    check('commit_alone_cannot_skip_feedback_authorization',rejects(lambda:g.reveal('b'*32)))
    g.feedback(0)
    check('nonce_reuse_rejected',rejects(lambda:g.reveal('a'*32)))
    r=g.reveal('b'*32)
    observation=wire({'target_bin':3000,'counts':[0]*96})
    expected=dict(r,observation={'target_bin':3000,'counts':[0]*96})
    check('opaque_prior_row_wrapper_matches_canonical_request',wrapped(r,observation)==wire(expected))
    for name,value in [('zero',0.),('negative',-1.),('boolean',True)]:
        body=response(r);body['mean_counts'][3]=value
        check(name+'_mean_rejected',rejects(lambda body=body:answer(wire(body),r)))
    body=response(r);body['mean_counts'].pop()
    check('partial95_channel_vector_rejected',rejects(lambda:answer(wire(body),r)))
    body=response(r);body['sequence']=True
    check('boolean_sequence_rejected',rejects(lambda:answer(wire(body),r)))
    body=response(r);body['nonce']='c'*32
    check('wrong_current_nonce_rejected',rejects(lambda:answer(wire(body),r)))
    body=wire(response(r)).replace(b'0.5',b'1e-999',1)
    check('nonzero_underflow_literal_rejected',rejects(lambda:answer(body,r)))
    body=wire(response(r)).replace(b'0.5',b'1e999',1)
    check('overflow_literal_rejected',rejects(lambda:answer(body,r)))
    body=wire(response(r)).replace(b'"sequence":1',b'"sequence":1,"sequence":1')
    check('duplicate_response_key_rejected',rejects(lambda:answer(body,r)))
    g=Gate(intervals);flags=[]
    for i in range(11):
        r=g.reveal(f'{i:032x}');flags.append(r['scored']);a,raw,p=committed(g,r);g.commit(a,raw,p,True);g.feedback(i)
    check('exact_ten_warmup_then_scored_boundary',flags==[False]*10+[True] and g.position==11)
    check('missing_protocol_interval_rejected',rejects(lambda:Gate(intervals[:-1])))
    create={'name':'invented','argv':['create'],'returncode':0,'stdout':'a'*64+'\n','stderr':''}
    created=returned_identity(create,'invented',['create'])
    check('returned_and_inspected_same_id_agree',agree_identities(created,['a'*64])=={'a'*64})
    check('returned_and_inspected_different_id_rejected',rejects(lambda:agree_identities(created,['b'*64])))
    check('missing_return_and_no_inspection_has_no_identity',agree_identities(None,[])==set())
    if len(names)!=len(set(names)):raise AssertionError('Unique generated protocol roster')
    return {'status':'rtt_causal_protocol_generated_checks_passed','checks':len(names),'names':names,
            'recording_reads':0,'model_fits':0,'candidate_processes':0,
            'scope':'Invented gate/parser state only; not a filesystem fsync or OS isolation experiment.'}
