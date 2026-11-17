"""Allowlist projection: no source container, alias, hidden target or original ID."""
import hashlib
import hmac
from .common import (PEOPLE,CHANNELS,VIEWS,need,fields,integer,finite,probability,
    pin,check_pin,encode,same_roster,unique)

PRIVATE_FIELDS=('person','epoch','rt','instruction','samples','waveform','contrast','source_row')
def validate_rows(rows):
    need(type(rows) is list and rows,'complete admitted private rows');seen=set();people=set()
    for row in rows:
        fields(row,PRIVATE_FIELDS);pid=row['person'];need(pid in PEOPLE,'original person')
        integer(row['epoch']);key=(pid,row['epoch']);need(key not in seen,'unique original trial');seen.add(key);people.add(pid)
        r=finite(row['rt']);need(r>=.1 and row['instruction'] in (0,1),'legal behavior')
        n=integer(row['samples'],8);need(n==round(r*512)+round(.01*512),'exact source sample crop')
        y=finite(row['contrast']);need(.025<y<1,'exact logged contrast domain')
        check_pin(row['source_row'])
        x=row['waveform'];need(len(x)==32 and all(len(ch)==n for ch in x),'all32 complete waveform channels')
        for ch in x:
            for value in ch:finite(value)
    need(people==set(PEOPLE),'all26 original people');return rows

def opaque(seed,context,kind,identity):
    need(type(seed) is bytes and len(seed)>=32,'operator-created target-independent opaque seed')
    message=encode([context,kind,identity],4096)
    return hmac.new(seed,message,hashlib.sha256).hexdigest()

def make_view(rows,held,mode,view,seed,context,admission_pin,limits,*,hmp_tool=None):
    need(held in PEOPLE and mode in ('P','I') and view in VIEWS,'selected context')
    check_pin(admission_pin);need(type(context) is str and context,'opaque context')
    integer(limits['view_bytes'],1);integer(limits['live_scalar_slots'],1)
    validate_rows(rows)
    need(sum(32*r['samples'] for r in rows)<=limits['live_scalar_slots'],'complete waveform view live bound; no omitted rows')
    ids={};training=[];query=[];answers=[]
    for r in rows:
        key=(r['person'],r['epoch']);tid=opaque(seed,context,'trial',list(key));pid=opaque(seed,context,'person',r['person'])
        need(tid not in ids,'opaque identity collision');ids[tid]=key
        out={'id':tid,'person':pid,'rt':r['rt'],'instruction':r['instruction'],'samples':r['samples']}
        if view in ('E','EH'):out['waveform']=[list(c) for c in r['waveform']]
        if r['person']==held:
            query.append(out);answers.append({'id':tid,'value':r['contrast']})
        else:out['contrast']=r['contrast'];training.append(out)
    # HMAC identity order is fixed independently of the target values.
    training.sort(key=lambda r:r['id']);query.sort(key=lambda r:r['id']);answers.sort(key=lambda r:r['id'])
    tool=None
    if view in ('H','EH'):
        need(hmp_tool is not None,'complete mandatory HMP tool')
        tool=project_hmp_tool(hmp_tool,ids,seed,context,held)
    else:need(hmp_tool is None,'no supplied HMP tool in B/E')
    common={'schema':'neural004_actor_view_v1','context':context,'mode':mode,'view':view,
        'sampling_hz':512,'channel_order':list(CHANNELS) if view in ('E','EH') else None,
        'waveform_units':'volt' if view in ('E','EH') else None,'retrospective':True,
        'paper_informed':True,'crop_rule':'rint(rt_seconds*512)+rint(.01*512)'}
    train={**common,'support':'training','rows':training,'hmp':None if tool is None else tool['training']}
    held_view={**common,'support':'held','rows':query,'hmp':None if tool is None else tool['held']}
    train_body=encode(train,limits['view_bytes']);held_body=encode(held_view,limits['view_bytes'])
    # Answer and identity bodies are private; no answer hash enters public view.
    return {'training_body':train_body,'held_body':held_body,'private_answers':answers,'private_ids':ids,
        'private_context':{'context':context,'held':held,'mode':mode,'view':view,'admission_pin':admission_pin,
            'training_pin':pin(train,limits['view_bytes']),'held_pin':pin(held_view,limits['view_bytes']),
            'training_ids':[r['id'] for r in training],'held_ids':[r['id'] for r in query]}}

def project_hmp_tool(tool,ids,seed,context,held):
    """Only exact source-defined safe tool schema; complete membership mandatory."""
    fields(tool,('schema','models','evaluations'));need(tool['schema']=='neural004_private_hmp_tool_v1','source HMP schema')
    need(len(tool['models'])==3 and len(tool['evaluations'])==12,'three counts, both supports, both gains')
    reverse={value:key for key,value in ids.items()};out={support:{'models':[],'evaluations':[]} for support in ('training','held')}
    model_keys=('events','state_pin','pca','normalization','channel_parameters','duration_parameters','grouping','template','em_trace','stop','source_pin','training_people','status','failure')
    for model in tool['models']:
        fields(model,model_keys);need(model['events'] in (4,5,6),'all fixed event counts')
        same_roster(model['training_people'],[p for p in PEOPLE if p!=held])
        safe={k:v for k,v in model.items() if k!='training_people'}
        # No unrestricted xarray attributes or source paths are included. The
        # helper schema stores numeric arrays/named axes in these exact fields.
        safe['training_people']=sorted(opaque(seed,context,'person',p) for p in model['training_people'])
        for support in out:out[support]['models'].append(safe)
    need({m['events'] for m in tool['models']}=={4,5,6},'unique complete model set')
    expected={(k,s,g) for k in (4,5,6) for s in out for g in ('ordinary','zero')};seen=set()
    for evaluation in tool['evaluations']:
        fields(evaluation,('events','support','gain','state_pin','groups','rows','normalization_state','source_pin','status','failure'))
        key=(evaluation['events'],evaluation['support'],evaluation['gain']);need(key in expected and key not in seen,'complete evaluation identity');seen.add(key)
        support=evaluation['support'];expected_rows={k for k in reverse if (k[0]==held)==(support=='held')}
        parsed=[];actual=set()
        for row in evaluation['rows']:
            fields(row,('person','epoch','samples','marginals','times_ms','intervals_ms','sums_ms','endpoint_ms','log_mass','log_mass_delta_ordinary_minus_zero','event_normalizers','normalization','group','normalizer_status','status','failure'))
            original=(row['person'],row['epoch']);need(original in expected_rows and original not in actual,'same complete HMP trial support');actual.add(original)
            parsed.append({**{k:v for k,v in row.items() if k not in ('person','epoch')},'id':reverse[original]})
        need(actual==expected_rows,'no missing HMP rows')
        safe_groups=[]
        for group in evaluation['groups']:
            fields(group,('id','M','location','members','scalar_total','pmf_normalizers','status'))
            need(group['location'] is False,'transform location=False')
            safe_groups.append({**group,'members':sorted(reverse[(p,e)] for p,e in group['members'])})
        out[support]['evaluations'].append({**{k:v for k,v in evaluation.items() if k not in ('rows','groups')},'rows':sorted(parsed,key=lambda r:r['id']),'groups':safe_groups})
    need(seen==expected,'uniform complete H/EH schema')
    return out
