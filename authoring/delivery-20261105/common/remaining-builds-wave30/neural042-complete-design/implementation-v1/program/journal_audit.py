"""Independent complete identity/resource/retirement audit; counts are insufficient."""
import math
from core import need,integer,finite,encoded,pin
from journal import decode,closure
from schedule import schedule,disposition

def audit(raw,producer,a):
    events,chain=decode(raw);planned=schedule(producer['people']);ids=[x['identity']for x in planned]
    episodes=[x['identity']for x in planned if x['kind']=='author'or(x['kind']=='case'and x['cell'][0]=='I')]
    joined=closure(events,episodes,ids,a['clock']['origin'],a['clock']['production_end'])
    need(producer['disposition']==disposition(planned,events)and producer['disposition']['counts']['completed']==len(planned),'full exact successful schedule')
    started={};done={};consumed={};telemetry={};entry={};finished={};phase_order=[]
    for e in events:
        k=e['kind']
        if k=='phase_entered':
            phase_order.append(e['identity']);entry[e['identity']]=e
            need(e['entered_at']>=a['clock']['origin']and e['entered_at']<e['cutoff']<=a['clock']['production_end'],'original phase clock')
        elif k=='phase_completed':finished[e['identity']]=e
        elif k=='scope_started':need(e['identity']not in started,'unique scope');started[e['identity']]=e
        elif k=='scope_completed':need(e['identity']not in done,'unique scope closure');done[e['identity']]=e
        elif k=='scope_failed':raise ValueError('failed scope')
        elif k=='native_cpu':
            need(e['operation']in joined['native'],'CPU belongs to native intent');row=joined['native'][e['operation']]
            need(e['container']==row['created']['container'],'CPU immutable container')
            prev=telemetry.get(e['operation'],0);need(prev<=integer(e['cpu_ns'])<=row['intent']['limits']['cpu_ns'],'bounded monotone CPU');telemetry[e['operation']]=e['cpu_ns']
        elif k=='operation_consumed':need(e['operation']not in consumed,'one exact operation consumer');consumed[e['operation']]=e
    need(phase_order==ids and set(started)==set(done)==set(ids),'one exact ordered complete phase and resource scope')
    opmap={x['operation']:x for x in producer['operations']};need(len(opmap)==len(producer['operations'])and set(opmap)==set(joined['native'])==set(consumed),'every actual native operation consumed')
    need(len(opmap)<=a['resources']['native_operations'],'whole study operation cap')
    for role in('public','private'):need(sum(x['role']==role for x in opmap.values())<=a['native_'+role]['operations'],'exact role operation cap')
    reserved_by_role={'public':0,'private':0};reserved_by_phase={x:0 for x in ids};observed=0
    for op,row in joined['native'].items():
        i=row['intent'];c=row['completed'];p=opmap[op];phase=i['candidate_scope']
        need(phase in ids and p['native']==c and p['source']==i['source']and consumed[op]['descriptor']==p['descriptor'],'producer/native/consumer exact joins')
        need(i['limits']==a['phase_limits'][entry[phase]['profile']]and i['cutoff']<=entry[phase]['cutoff'],'selected native profile and phase')
        need(telemetry.get(op,0)<=integer(c['cpu_ns'])<=i['limits']['cpu_ns'],'final CPU includes last telemetry')
        reserve=i['limits']['cpu_ns']+math.ceil(i['limits']['cpu_rate_ns']*i['limits']['qualified_enforcement_lag_seconds'])
        need(i['cpu_reservation_including_enforcement_lag_ns']==reserve and i['gpu_device_seconds_reservation']==0,'exact conservative prospective native reservation')
        retirement=c['retirement'];cutoff=min(a['clock']['production_end'],i['cutoff']+i['limits']['retirement_seconds'])
        need(retirement['cutoff']==cutoff and retirement.get('removed')is True and retirement.get('absence_confirmed')is True
             and retirement.get('successful_clock_custody')is True and retirement.get('unknown_state',False)is False
             and c['observed_end']<=c['retired_at']<cutoff,'exact successful bounded retirement')
        state=c['last_state'];need(state['Status']=='exited'and state['Running']is False and type(state['Pid'])is int and state['Pid']==0
            and type(state['ExitCode'])is int and state['ExitCode']==0 and state['OOMKilled']is False and state.get('Error','')=='','actual natural state fields')
        reserved_by_role[p['role']]+=reserve;reserved_by_phase[phase]+=reserve;observed+=c['cpu_ns']
    for identity in ids:
        x=started[identity];y=done[identity];need(x['original_origin']==a['clock']['origin']and x['cutoff']==entry[identity]['cutoff'],'scope original identity')
        need(y['cpu_reserved']==reserved_by_phase[identity]<=x['cpu_cap']and y['gpu_reserved']==0 and y['observed_end']<x['cutoff'],'whole episode native resource closure')
        need(producer['phases'][identity]==finished[identity]['result']and producer['phases'][identity]['scope']=={k:v for k,v in y.items()if k not in('kind','observed_end')},'phase result/scope joins')
        expected=[p['operation']for p in producer['operations']if joined['native'][p['operation']]['intent']['candidate_scope']==identity]
        need(producer['phases'][identity]['operations']==expected,'exact phase child operation order')
    for role in reserved_by_role:need(reserved_by_role[role]<=a['native_'+role]['whole_cpu_ns'],'whole role CPU bound')
    provider_totals=provider_summary(joined['providers'],entry,a)
    costs=producer['provider_costs'];need(costs=={**provider_totals,'unknown_failed_request_usage_not_zero':True},'complete actual selected provider budget/observed usage')
    return {'chain':chain,'phase_count':len(ids),'native_count':len(opmap),'provider_count':len(joined['providers']),
            'cpu_reserved':reserved_by_role,'cpu_observed':observed,'events':joined,'disposition':producer['disposition']}


def provider_summary(providers,entries,a):
    reserved=usage=calls=0;money=0.;per_phase={}
    for key,row in providers.items():
        attempt=row['attempt'];u=row['usage'];episode=key[0]
        need(type(episode)is tuple and 1<=len(episode)<=2 and episode[0]in entries,'provider belongs to one selected phase')
        identity=episode[0];entry=entries[identity];need(entry['phase_kind']in('author','case'),'no provider in private reference/group')
        profile=a['phase_limits'][entry['profile']];p=per_phase.setdefault(identity,{'calls':0,'tokens':0,'money':0.})
        p['calls']+=1;need(type(attempt['ordinal'])is int and attempt['ordinal']==p['calls'],'one monotone provider across whole case/author scope')
        n=integer(u['prompt_tokens'])+integer(u['completion_tokens']);p['tokens']+=n;p['money']+=finite(attempt['money_reserved'])
        need(u['cumulative_tokens']==p['tokens']and type(u['cumulative_tokens'])is int,'complete actual local token counter')
        need(entry['entered_at']<=attempt['observed_start']<attempt['cutoff']<=entry['cutoff'],'provider retains complete original phase clock')
        need(u['prompt_tokens']<=attempt['prompt_upper_bound']and u['completion_tokens']<=attempt['output_token_ceiling'],'actual usage below selected per-request bound')
        need(p['calls']<=profile['provider_calls']and p['tokens']<=profile['tokens']and 0<=p['money']<=profile['money'],'whole phase provider resource cap')
        reserved+=integer(attempt['prompt_upper_bound'])+integer(attempt['output_token_ceiling']);usage+=n;calls+=1;money+=attempt['money_reserved']
    r=a['resources'];limits={'calls':r['whole_provider_calls'],'tokens':r['whole_provider_tokens'],'money':r['whole_provider_money']}
    need(calls<=limits['calls']and usage<=reserved<=limits['tokens']and 0<=money<=limits['money'],'whole study provider cap')
    return {'limits':limits,'calls_reserved':calls,'tokens_reserved':reserved,'money_reserved':money,'tokens_observed':usage}
