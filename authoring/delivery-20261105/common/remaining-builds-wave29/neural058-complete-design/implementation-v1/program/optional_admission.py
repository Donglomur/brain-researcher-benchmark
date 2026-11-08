"""Complete optional-stage treatment and provider-value lineage admission."""
from core import need,pin,encoded,parse
from ordering import sessions
from provider import action


def treatment(request,panel,animal):
    mode,role,tool,_=panel.split('/')
    need(request['panel']==panel and request['mode']==mode and request['role']==role
         and request['tool']==tool and request['animal']==animal,'exact optional-stage treatment and animal')
    return True


def analysis(request,spec,roster):
    treatment(request,spec['panel'],spec['animal'])
    need(request['stage']=='analysis' and request['recipe']=={'numeric_slots':[]},'analysis has no frozen inference slots')
    need([x['session'] for x in request['training']]==sessions(roster,'source'),'complete optional source training')
    expected=[] if spec['animal']=='global' else sessions(roster,'evaluation',spec['animal'])
    need([x['session'] for x in request['evaluation']]==expected
         and request['animal_sessions']==expected,'all and only own author context views')
    return True


def features(request,spec,roster,method,fit):
    treatment(request,spec['panel'],spec['animal'])
    expected=sessions(roster,'evaluation',spec['animal'])
    need(request['stage']=='numeric_features' and request['current_session']==spec['session']
         and not request['training'] and request['animal_sessions']==expected
         and [x['session'] for x in request['evaluation']]==expected,'exact frozen current-animal feature views')
    need(request['recipe']==method['recipe'] and request['recipe']['numeric_slots']
         and request['program']['pin']==method['program']['pin'] and request['state']==fit['result']['state']
         and request['provider_values']==[],'exact own sealed feature method/state/recipe')
    return True


def numeric_bridge(operation,product,following,rows,method,provider_events,selection):
    features=product['result']['features'];slots=method['recipe']['numeric_slots']
    need(len(features)==len(slots)==len(rows),'every declared numeric feature/provider slot')
    values=[];keys=[]
    for i,(numbers,slot,row) in enumerate(zip(features,slots,rows,strict=True)):
        episode=[following['panel'],following['animal']]
        need(row['operation']==operation and row['slot']==i and row['episode']==episode
             and row['feature_result']==product['result_pin'],'exact numeric feature producer/slot/consumer')
        key=(tuple(episode),row['ordinal']);need(key in provider_events,'actual provider request for this panel/animal/ordinal')
        evidence=provider_events[key];attempt=evidence['attempt'];done=evidence['complete']
        messages=[{'role':'system','content':'Return exactly JSON {"values": [finite numbers]}. '+slot['prompt']},
                  {'role':'user','content':encoded(numbers).decode()}]
        payload={'model':selection['provider']['model'],'messages':messages,'stream':False,
                 'max_tokens':attempt['output_token_ceiling'],'temperature':selection['provider']['temperature']}
        if selection['provider']['seed_supported']:payload['seed']=attempt['request_seed']
        need(attempt['request']==row['request']==pin(encoded(payload)),'exact fixed prompt and feature request bytes')
        raw=row['response_text'].encode('utf8');need(pin(raw)==row['response']==done['response'],'actual numeric response body pin')
        body=parse(raw);choices=body['choices'];need(len(choices)==1 and choices[0]['finish_reason']=='stop'
            and choices[0]['message']['role']=='assistant' and not choices[0]['message'].get('tool_calls')
            and body['model']==selection['provider']['response_model'],'one complete exact model numeric reply')
        selected=action(choices[0]['message']['content'].encode(),'fixed_numeric')
        need(selected==done['action'] and selected['values']==row['values'],'actual typed provider values')
        values.append(row['values']);keys.append(key)
    need(following['provider_values']==values,'the exact numeric replies enter only the following inference')
    return keys
