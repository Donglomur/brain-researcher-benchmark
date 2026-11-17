"""Owner-only post-closure assessment; no intermediate candidate feedback."""
from fractions import Fraction
import math
from pathlib import Path
import struct
from common import need,read,write,pin,encode,admit_pin
from docker_owner import require_closed
from runtime import capture_selected_authentic

def body_of(closed, *, modules,budget):
    require_closed(closed)
    entry=closed.submission
    budget.charge_read(entry['bytes'])
    body=modules['controller_interface'].capture_closed_file(entry['path'])
    need(pin(body)=={k:entry[k] for k in ('bytes','sha256')},'closed_submission_identity')
    budget.check()
    return body

def ingestion(body,ordinal):
    return {'schema':'tms_closed_submission_ingestion_v1','ordinal':ordinal,
            'bytes':len(body),'sha256':pin(body)['sha256'],'closed':True}

def score_authentic(closed_runs, *, modules,selection,root,budget):
    need(type(closed_runs) is list and 1<=len(closed_runs)<=6,'bounded_closed_assessment_set')
    for value in closed_runs:
        require_closed(value)
    # This exact call is absent from inert control execution. Its independent
    # root selection must newly authorize this use; P15 authority is not reused.
    reference=capture_selected_authentic(modules,selection=selection,
                                        all_candidates_closed=True,budget=budget)
    root=Path(root);root.mkdir(mode=0o700)
    def private_writer(name,body):
        return write(root/name,body,budget)
    interface=modules['controller_interface'].ControllerInterface(
        operator_reference=reference,private_writer=private_writer,max_submissions=6)
    receipts=[]
    for closed in closed_runs:
        body=body_of(closed,modules=modules,budget=budget)
        receipts.append(interface.submit_closed_bytes(body))
    # Owner return only. No reference-derived score/status is sent to candidates.
    return receipts

def rational(value):
    need(type(value) is dict and set(value)=={'numerator','denominator'},'score_rational_schema')
    n,d=value['numerator'],value['denominator']
    need(type(n) is type(d) is str and n==str(int(n)) and d==str(int(d)) and int(d)>0,'canonical_rational')
    r=Fraction(int(n),int(d))
    need(str(r.numerator)==n and str(r.denominator)==d,'reduced_score_rational')
    return r

def independent_metrics(errors):
    finite=[row for row in errors if row is not None]
    if not finite:
        return {'finite_slots':0,'MAE':None,'Linf':None}
    return {'finite_slots':len(finite),
            'MAE':(sum(x[0] for x in finite)/len(finite),sum(x[1] for x in finite)/len(finite)),
            'Linf':(max(x[0] for x in finite),max(x[1] for x in finite))}

def check_metrics(observed,expected):
    need(type(observed) is dict and set(observed)=={'finite_slots','MAE','Linf'} and
         type(observed['finite_slots']) is int and observed['finite_slots']==expected['finite_slots'],
         'complete_metric_support')
    for key in ('MAE','Linf'):
        if expected[key] is None:
            need(observed[key] is None,'empty_metric_null')
        else:
            v=observed[key];need(type(v) is dict and set(v)=={'lower','upper'},'metric_interval')
            need((rational(v['lower']),rational(v['upper']))==expected[key],'independent_fraction_metric')

def score_inert(closed_runs, *, modules,fixture,root,budget):
    """Explicit inert-only route; unchanged authentic ControllerInterface is not patched."""
    need(type(closed_runs) is list and len(closed_runs)==4 and fixture['authentic_source'] is False,
         'four_inert_closed_runs')
    for value in closed_runs:
        require_closed(value)
    cert=modules['certificate'];scorer=modules['scorer'];kernel=modules['kernel']
    admitted=cert.admit_fixture_reference(fixture['reference'],fixture['reference_pin'],fixture['context'])
    try:
        modules['custody'].require_operator_reference(admitted)
    except kernel.Refusal as error:
        need(str(error)=='trusted post-review capture required','exact_fixture_production_refusal')
    else:
        raise AssertionError('fixture became an authentic operator reference')
    root=Path(root);root.mkdir(mode=0o700)
    write(root/'REFERENCE.fixture.private.json',fixture['reference'],budget)
    outcomes=[]
    for ordinal,closed in enumerate(closed_runs,1):
        body=body_of(closed,modules=modules,budget=budget)
        shift=0 if ordinal<=2 else 2
        expected_values=[float('nan') if x is None else float(x)+shift for x in fixture['targets']]
        expected_body=struct.pack('<248d',*expected_values)+bytes(int(math.isnan(x)) for x in expected_values)
        need(body==expected_body,'complete_positive_or_wrong_serialization')
        score=scorer.score_fixture(candidate_body=body,reference_body=fixture['reference'],
            reference_pin=fixture['reference_pin'],context=fixture['context'])
        expected_keys={'schema','authentic_source','reference_pin','all248_categories_match','undefined_slots',
            'finite_slots','informative','out_of_proved_range_candidate_values','pooled','maps','slots',
            'binary_threshold','scientific_tolerance','native_parity_claimed','production_authority_claimed'}
        admit_pin(score['reference_pin'],262144)
        need(type(score) is dict and set(score)==expected_keys and
             score['schema']=='tms_real_interval_248_inert_score_v1' and score['authentic_source'] is False and
             score['reference_pin']==fixture['reference_pin'] and score['all248_categories_match'] is True and
             score['binary_threshold'] is None and score['scientific_tolerance'] is None and
             score['native_parity_claimed'] is False and score['production_authority_claimed'] is False,
             'complete_inert_score_scope')
        values=struct.unpack('<248d',body[:1984])
        for key,expected in [('undefined_slots',sum(math.isnan(x) for x in values)),
                             ('finite_slots',sum(not math.isnan(x) for x in values)),
                             ('out_of_proved_range_candidate_values',sum(not math.isnan(x) and abs(x)>1 for x in values))]:
            need(type(score[key]) is int and score[key]==expected,'strict_score_counts')
        need(score['informative'] is any(not math.isnan(x) for x in values),'strict_informative_flag')
        errors=[]
        need(type(score['slots']) is list and len(score['slots'])==248,'full_score_slots')
        for i,(target,slot,value,detail) in enumerate(zip(fixture['targets'],admitted.slots,values,score['slots'])):
            need(type(detail) is dict and set(detail)=={'index','category','signed','absolute'},'closed_slot_schema')
            need(type(detail['index']) is int and detail['index']==i,'score_slot_order')
            if target is None:
                need(detail['category']=='source_undefined' and detail['signed'] is None and
                     detail['absolute'] is None and slot.interval is None and math.isnan(value),
                     'preserved_undefined_slot')
                errors.append(None);continue
            z=Fraction.from_float(value)
            need(type(detail['signed']) is dict and set(detail['signed'])=={'lower','upper'} and
                 type(detail['absolute']) is dict and set(detail['absolute'])=={'lower','upper'},
                 'closed_residual_intervals')
            scaled=target*kernel.D
            need(slot.interval.lo==scaled.numerator//scaled.denominator and
                 slot.interval.hi==-((-scaled.numerator)//scaled.denominator),
                 'independent_exact_directed_fixture_certificate')
            lo=z-Fraction(slot.interval.hi,kernel.D)
            hi=z-Fraction(slot.interval.lo,kernel.D)
            expected_abs=(Fraction(0) if lo<=0<=hi else min(abs(lo),abs(hi)),max(abs(lo),abs(hi)))
            need(detail['category']=='finite' and
                 (rational(detail['signed']['lower']),rational(detail['signed']['upper']))==(lo,hi) and
                 (rational(detail['absolute']['lower']),rational(detail['absolute']['upper']))==expected_abs,
                 'independent_complete_fraction_residuals')
            if shift==2:
                need(expected_abs[0]>1,'deliberately_wrong_numeric_output')
            errors.append(expected_abs)
        check_metrics(score['pooled'],independent_metrics(errors))
        need(set(score['maps'])==set(cert.MAPS),'all_four_metric_maps')
        for index,name in enumerate(cert.MAPS):
            check_metrics(score['maps'][name],independent_metrics(errors[index*62:(index+1)*62]))
        receipt=ingestion(body,ordinal)
        need(set(receipt)=={'schema','ordinal','bytes','sha256','closed'},'ingestion_only_receipt')
        write(root/f'{ordinal:02d}.score.private.json',encode(score),budget)
        write(root/f'{ordinal:02d}.receipt.private.json',encode(receipt),budget)
        outcomes.append({'ordinal':ordinal,'positive':shift==0,'complete_engineering_check':True})
    return {'fixture_production_refused':True,'four_complete_outputs_checked':True,
            'independent_fraction_oracle_passed':True,'outcomes':outcomes,
            'authentic_reference_access':False,'scientific_qualification':False}

