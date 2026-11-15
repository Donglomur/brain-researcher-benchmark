"""Continuous candidate-byte scoring against a separately captured owned reference.

No candidate execution or reference creation occurs here. Caller must keep the
trusted capture/configuration path outside any candidate-controlled process.
"""
from kernel import RAW_UNIT, P, add, mul, exact_float, require
from scorer import decode_candidate, rational, metrics
from authentic import MAPS
from custody import require_operator_reference


def score(candidate_body, *, operator_reference):
    reference=require_operator_reference(operator_reference)
    values,flags=decode_candidate(candidate_body)
    require(all(flag==(slot.interval is None) for flag,slot in zip(flags,reference.slots)),'complete source category agreement; no filtering')
    scale=1<<(1074-P);errors=[];details=[];outside=0
    for i,(value,flag,slot) in enumerate(zip(values,flags,reference.slots)):
        if flag:
            errors.append(None);details.append({'index':i,'category':'source_undefined','signed':None,'absolute':None});continue
        z=exact_float(value);coordinate=mul(z.n,RAW_UNIT//z.d)
        lo=add(coordinate,-mul(slot.interval.hi,scale));hi=add(coordinate,-mul(slot.interval.lo,scale))
        low_abs=0 if lo<=0<=hi else min(abs(lo),abs(hi));high_abs=max(abs(lo),abs(hi))
        errors.append((low_abs,high_abs));outside+=int(abs(value)>1.0)
        details.append({'index':i,'category':'finite','signed':{'lower':rational(lo,RAW_UNIT),'upper':rational(hi,RAW_UNIT)},
                        'absolute':{'lower':rational(low_abs,RAW_UNIT),'upper':rational(high_abs,RAW_UNIT)}})
    return {'schema':'tms_exact_real_owned_continuous_score_v1','reference_pin':reference.certificate_pin,
            'support_pin':reference.support_pin,'owner_descriptor_pin':operator_reference.owner_descriptor_pin,
            'all248_categories_match':True,'undefined_slots':sum(flags),'finite_slots':248-sum(flags),
            'informative':not all(flags),'out_of_proved_range_candidate_values':outside,
            'pooled':metrics(errors),'maps':{name:metrics(errors[i*62:(i+1)*62]) for i,name in enumerate(MAPS)},
            'slots':details,'binary_threshold':None,'scientific_tolerance':None,
            'native_parity_claimed':False,'paper_only_validity_claimed':False}
