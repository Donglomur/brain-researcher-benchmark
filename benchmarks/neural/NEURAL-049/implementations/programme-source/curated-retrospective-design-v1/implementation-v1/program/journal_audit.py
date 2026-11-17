"""Independent exact full schedule, source, CPU/GPU and immutable-container closure."""
import math
from core import need, integer, finite, encoded, pin, parse
from journal import decode
from schedule import graph


def audit(raw, producer, a, records):
    events, chain = decode(raw); planned = list(graph(producer['table'],a['modules'],a['cache']))
    expected = [j['id'] for j in planned]; need(len(expected) == len(set(expected)), 'unique full scheduled phases')
    entered = {}; completed = {}; order = []; native = {}; providers = {}; scopes = {}; closed = {}; observed = {}
    operations = {}; episodes = set()
    for e in events:
        k = e['kind']
        if k == 'phase_entered':
            key = e['identity']; need(key not in entered, 'one phase entry'); entered[key] = e; order.append(key)
            need(a['clock']['origin'] <= e['entered_at'] < e['cutoff'] <= a['clock']['production_end'], 'phase original clock')
        elif k == 'phase_completed':
            key = e['identity']; need(key in entered and key not in completed, 'one completion after entry'); completed[key] = e
        elif k == 'episode_completed':
            need(e['identity'] not in episodes, 'one episode completion'); episodes.add(e['identity'])
        elif k == 'scope_started':
            key = e['identity']; need(key not in scopes, 'one resource scope'); scopes[key] = e
        elif k == 'scope_completed':
            key = e['identity']; need(key in scopes and key not in closed, 'same exact scope closure'); closed[key] = e
        elif k == 'native_intent':
            key = e['operation']; need(key not in native and e['candidate_scope'] in entered, 'native belongs to exact entered phase')
            native[key] = {'intent':e}
        elif k in ('native_created','native_started','native_completed'):
            key = e['operation']; need(key in native, 'native event after intent'); row = native[key]; name = k[7:]
            need(name not in row and e['config'] == row['intent']['config'], 'one exact native configuration chain')
            if name != 'created': need('created' in row and e['container'] == row['created']['container'], 'same immutable container')
            if name == 'completed': need('started' in row, 'native started before complete')
            row[name] = e
        elif k == 'native_cpu':
            key = e['operation']; need(key in native and e['container'] == native[key]['created']['container'], 'CPU immutable identity')
            need(observed.get(key,0) <= integer(e['cpu_ns']) <= native[key]['intent']['limits']['cpu_ns'], 'monotone bounded CPU telemetry')
            observed[key] = e['cpu_ns']
        elif k == 'operation_completed':
            key = e['operation']; need(key not in operations, 'one actual operation record'); operations[key] = e['record']
        elif k == 'provider_attempted':
            key = (tuple(e['episode']),e['ordinal']); need(key not in providers, 'unique provider request')
            providers[key] = {'attempt':e}
        elif k in ('provider_usage_observed','provider_completed'):
            key = (tuple(e['episode']),e['ordinal']); need(key in providers, 'provider response after exact attempt')
            name = 'usage' if k == 'provider_usage_observed' else 'complete'
            need(name not in providers[key], 'one usage/complete body'); providers[key][name] = e
        elif k.endswith('_failed') or k == 'study_failed': raise ValueError('failed/unknown journal cannot pass complete admission')
    need(order == expected and set(completed) == set(expected) == set(scopes) == set(closed), 'complete exact ordered phase and resource membership')
    need(episodes == {j['id'] for j in planned if j['kind'] in ('global_author','actor_case')}, 'complete exact actor contexts')
    need(set(operations) == set(native) == set(producer['operations']), 'every native intent completed and retained')
    role_cpu = {'public':0,'private':0}; role_gpu = {'public':0.,'private':0.}; phase_cpu = {x:0 for x in expected}; phase_gpu = {x:0. for x in expected}
    containers = set()
    for op, row in native.items():
        need(set(row) == {'intent','created','started','completed'}, 'complete native chain')
        i,c = row['intent'],row['completed']; p = records['operations'][op]
        need(p == operations[op] and p['native'] == c and p['request']['pin'] == pin(encoded(p['request_value'])), 'actual producer/native/request joins')
        scope = i['candidate_scope']; profile = a['profiles'][p['profile']]
        need(i['limits'] == profile and i['source'] == a['source_manifest'] == c['source']
             and i['output'] == p['output'] == c['output'] and i['cutoff'] == c['cutoff'] <= scopes[scope]['cutoff']
             and i['original_origin'] == c['original_origin'] == a['clock']['origin'], 'exact original native source/profile/cutoff')
        need(c['container'] not in containers, 'no resource reuse across operations'); containers.add(c['container'])
        need(c['natural_exit'] is True and type(c['exit_code']) is int and c['exit_code'] == 0
             and observed.get(op,0) <= integer(c['cpu_ns']) <= profile['cpu_ns'], 'natural complete CPU evidence')
        state = c['last_state']
        need(state['Status'] == 'exited' and state['Running'] is False and type(state['Pid']) is int and state['Pid'] == 0
             and type(state['ExitCode']) is int and state['ExitCode'] == 0 and state['OOMKilled'] is False and state.get('Error','') == '', 'actual exited state')
        retirement = c['retirement']; end = min(a['clock']['production_end'],i['cutoff']+profile['retirement_seconds'])
        need(retirement['cutoff'] == end and retirement.get('removed') is True and retirement.get('absence_confirmed') is True
             and retirement.get('successful_clock_custody') is True and retirement.get('unknown_state',False) is False
             and i['started'] <= c['observed_end'] < i['cutoff'] and c['observed_end'] <= c['retired_at'] < end,
             'successful exact bounded retirement, not facts with failed clock custody')
        required = i['expected_artifacts']; allowed = {**required,**i.get('optional_artifacts',{})}
        need(set(required) <= set(c['artifacts']) <= set(allowed), 'complete required and actual optional artifacts')
        role = 'private' if p['role'] in ('reference','selection') else 'public'
        cpu = profile['cpu_ns']+math.ceil(profile['cpu_rate_ns']*profile['qualified_enforcement_lag_seconds'])
        gpu = len(a['native_'+role]['gpu_ids'])*(i['cutoff']-i['started']+profile['qualified_enforcement_lag_seconds'])
        need(i['cpu_reservation_including_enforcement_lag_ns'] == cpu and i['gpu_device_seconds_reservation'] == gpu,
             'prospective exact CPU/GPU reservation')
        role_cpu[role] += cpu; role_gpu[role] += gpu; phase_cpu[scope] += cpu; phase_gpu[scope] += gpu
    for phase in expected:
        x,y = scopes[phase],closed[phase]
        need(x['original_origin'] == a['clock']['origin'] and x['cutoff'] == entered[phase]['cutoff']
             and y['cpu_reserved'] == phase_cpu[phase] <= x['cpu_cap']
             and y['gpu_reserved'] == phase_gpu[phase] <= x['gpu_cap'] and y['observed_end'] < x['cutoff'], 'whole phase native limits')
        need(completed[phase]['record'] == producer['phases'][phase], 'phase result exact durable descriptor')
    for role in role_cpu:
        need(role_cpu[role] <= a['native_'+role]['whole_cpu_ns'] and role_gpu[role] <= a['native_'+role]['whole_gpu_device_seconds'], 'whole role resources')
    phase_provider = {}; total_calls = total_tokens = total_reserved = 0; total_money = 0.
    for (episode,ordinal),row in providers.items():
        need(set(row) == {'attempt','usage','complete'} and row['usage']['response'] == row['complete']['response'], 'complete provider response/usage')
        need(episode and episode[0] in entered, 'provider exact enclosing phase')
        phase = episode[0]; p = phase_provider.setdefault(phase, {'calls':0,'tokens':0,'money':0.})
        p['calls'] += 1; need(type(ordinal) is int and ordinal == p['calls'], 'whole-context provider call ordinal')
        i,u = row['attempt'],row['usage']; n = integer(u['prompt_tokens'])+integer(u['completion_tokens']); p['tokens'] += n
        need(pin(encoded(i['request_body'])) == i['request']
             and pin(row['complete']['response_utf8'].encode('utf-8')) == row['complete']['response'],
             'retained original complete provider request/response bytes')
        p['money'] += finite(i['money_reserved'])
        need(u['cumulative_tokens'] == p['tokens'] and u['prompt_tokens'] <= i['prompt_upper_bound']
             and u['completion_tokens'] <= i['output_token_ceiling'] and i['original_origin'] == a['clock']['origin']
             and entered[phase]['entered_at'] <= i['observed_start'] < i['cutoff'] <= scopes[phase]['cutoff'], 'actual original provider clock/token closure')
        kind = entered[phase]['job']['kind']; need(kind in ('global_author','actor_case'), 'no provider in private reference')
        lim = a['provider_profiles']['global_author' if kind == 'global_author' else 'case']
        from provider import action, request_seed
        job = entered[phase]['job']
        seed_identity = [job['policy'],'source-only','author-01'] if kind == 'global_author' else [job['cell']['policy'],job['case_id'],'author-01']
        expected_seed = request_seed(seed_identity,ordinal) if a['provider']['seed_supported'] else None
        need(i['request_seed'] == expected_seed and i['seed_supported'] is a['provider']['seed_supported'], 'same declared paired provider seed contract')
        payload = i['request_body']; response = parse(row['complete']['response_utf8'].encode())
        need(payload['model'] == a['provider']['model'] and payload['temperature'] == a['provider']['temperature']
             and payload['stream'] is False and payload['max_tokens'] == i['output_token_ceiling']
             and payload.get('seed') == expected_seed and response['model'] == a['provider']['response_model'], 'actual selected provider wire identity')
        need(len(response['choices']) == 1 and response['choices'][0]['finish_reason'] == 'stop', 'complete original provider response')
        mode = 'fixed_numeric' if len(episode)>1 and episode[1] == 'fixed' else 'author'
        derived = action(response['choices'][0]['message']['content'].encode(),mode,numeric_cap=lim['numeric_values'])
        need(derived == row['complete']['action'] and response['usage']['prompt_tokens'] == u['prompt_tokens']
             and response['usage']['completion_tokens'] == u['completion_tokens'], 'actual original response-to-action/usage join')
        need(p['calls'] <= lim['provider_calls'] and p['tokens'] <= lim['tokens'] and p['money'] <= lim['money'], 'full case provider cap')
        total_calls += 1; total_tokens += n; total_reserved += i['prompt_upper_bound']+i['output_token_ceiling']; total_money += i['money_reserved']
    expected_cost = {'limits':a['provider_total'],'calls_reserved':total_calls,'tokens_reserved':total_reserved,
                     'money_reserved':total_money,'tokens_observed':total_tokens,'unknown_failed_request_usage_not_zero':True}
    need(producer['provider_costs'] == expected_cost, 'whole actual provider ledger')
    need(total_calls <= a['provider_total']['calls'] and total_reserved <= a['provider_total']['tokens']
         and total_money <= a['provider_total']['money'], 'independent complete prospective provider ceilings')
    return {'phase_count':len(expected),'native_count':len(native),'provider_count':len(providers),
            'cpu_reserved':role_cpu,'gpu_reserved':role_gpu,'chain':chain,'native':native,'phases':entered,'providers':providers}
