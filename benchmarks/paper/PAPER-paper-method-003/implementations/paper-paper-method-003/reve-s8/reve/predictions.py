"""Whole-case passive prediction joins over actual isolated query processes."""
from .errors import require
from .objects import fields,canonical,digest


def validate_groups(plan):
    groups=plan['prediction_groups'];specs=plan['required_products'];used=set();keys=set()
    require(groups,'complete passive prediction group roster')
    for name,group in groups.items():
        fields(group,('programme','case_id','run','dataset','condition','method','purpose','classes','events','support','members'),('scientific_identity',))
        key=(group['programme'],group['case_id'],group['run'],group['purpose'])
        require(key not in keys,'duplicate case/run/purpose group');keys.add(key)
        require(group['events'] and len(set(group['events']))==len(group['events']) and len(group['classes'])>=2,'group event/class census')
        require(group['members'] and len(group['members'])==len(set(group['members'])),'group members')
        events=[];states=set()
        for member in group['members']:
            require(member in specs and member not in used,'missing or multiply grouped query output');used.add(member)
            s=specs[member];require(s['kind']=='prediction','group contains nonprediction')
            require(all(s[k]==group[k] for k in ('programme','case_id','run','dataset','condition','method','purpose','classes','support')),'query-to-case scientific identity')
            require(s['events'] and len(set(s['events']))==len(s['events']),'query event order')
            fields(s['query_policy'],('kind','request_independence_qualification'))
            q=s['query_policy']
            if q['kind']=='one_epoch':require(len(s['events'])==1 and q['request_independence_qualification'] is None,'one fresh epoch per process')
            elif q['kind']=='ISRUC_20_epoch_sequence':require(group['dataset']=='ISRUC' and len(s['events'])==20 and q['request_independence_qualification'] is None,'one qualified temporal sequence')
            else:require(q['kind']=='independently_qualified_immutable_worker' and q['request_independence_qualification'],'batched inference needs separately selected equivalence qualification')
            events.extend(s['events']);states.add(s['state'])
        require(len(events)==len(set(events)) and set(events)==set(group['events']),'complete nonoverlapping query partition')
        require(len(states)==1,'one frozen selected state per case/run')
    require(used=={k for k,s in specs.items() if s['kind']=='prediction'},'every actual query output has one whole-case group')
    return {'groups':len(groups),'query_products':len(used),'identity':digest(canonical(groups))}
