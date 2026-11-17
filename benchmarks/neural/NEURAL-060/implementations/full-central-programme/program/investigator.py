"""Actual provider/action/tool/source-seal composition; no finished-result callback."""
from pathlib import Path

from core import capture, encoded, fresh, integer, need, parse, pin, publish
from provider import Provider, request_seed
from engine import native
from authority import method_admission


SYSTEM = '''You are conducting the declared NEURAL-060 benchmark episode.
Return one JSON object only, with action python, submit, or stop. Python actions
have code and rationale strings; submit has source (Python), recipe (object), and
claim (object). Claims have endpoint, estimator, comparator, biological_unit,
uncertainty, leakage_limits, null_interpretation string fields. Stop has reason.
The only numerical tool is the provided offline Python sandbox. Do not seek other
sessions, roles, private targets, graders, outcomes or network access. All tool
responses and source selections are recorded. Source must implement
select_fit(train_rows,val_rows,train_counts,val_counts,recipe,seed) and
predict(state,test_rows,test_counts,recipe). Final fitting is original train/val
only; inference is prediction-only. Carry no fitted numeric state, embeddings,
normalizers or case-indexed predictions in source, recipe or comments. Typed
model-family/hyperparameter decisions may persist with their stated derivation.
Do not detect or undo perturbations; no arm flag is provided. The operator will
replay the identical sealed state and RNG, with source/method review required.
No favorable result or positive neural contribution is required. Reasoning
reports should give concise scientific rationale, not hidden chain-of-thought.
'''


def scaled_episode_limits(base, global_episode):
    result = dict(base)
    if global_episode:
        for key in ('tokens', 'seconds', 'tool_calls', 'tool_cpu_seconds', 'logs_bytes', 'source_revisions',
                    'provider_calls'):
            result[key] = integer(base[key], 1)*29
    # Peak memory/scratch and each request/response byte cap do not multiply.
    return result


def execute(*, authority, episode, session, packet, engine, worker_input, docs,
            output_root, budget, record):
    mode, replicate, role, slot = episode
    global_episode = slot == 'global'
    need(global_episode == (mode == 'frozen_program'), 'correct global/data-visible mode')
    need(session is None if global_episode else session['ordinal'] == slot, 'current session only')
    start = budget.tick()
    limits = scaled_episode_limits(authority['authoring_limits'], global_episode)
    cutoff = min(budget.deadline, start+limits['seconds'])
    root = fresh(output_root, budget)
    publisher = lambda value: record({'episode': list(episode), **value})
    client = Provider(authority['provider'], budget, publisher, limits)
    description = {'episode': list(episode), 'mode': mode, 'information_role': role,
                   'numeric_exposure': 'none' if global_episode else 'original_current_session_trainval_and_unlabeled_test',
                   'tool_paths': ['/input/train/context.json', '/input/val/context.json', '/input/test/context.json']
                   if not global_episode else [], 'task_documents': docs,
                   'limits': limits, 'scratch_policy': 'fresh per Python call; no filesystem state crosses calls',
                   'submission_source_revisions': 'one final submission; exploratory scripts consume tool allowance'}
    if not global_episode and role == 'joint':
        description['tool_paths'] += ['/input/'+split+'/neural.h5' for split in ('train', 'val', 'test')]
    messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': encoded(description).decode()}]
    tool_calls = logs_bytes = tool_cpu_ns = 0
    final = None
    episode_state = {'schema': 'neural060_author_episode_v1', 'episode': list(episode),
                     'entered': True, 'completed': False, 'source_sealed': False,
                     'observed_start': start, 'cutoff': cutoff}
    publisher({'kind': 'episode_entered', 'state': episode_state})
    try:
        while True:
            budget.tick(cutoff)
            chosen, response_text, raw_response = client.complete(messages, episode, cutoff)
            response_name = 'provider-'+str(client.calls)+'.json'
            publish(root/response_name, raw_response, budget, readonly=True)
            messages.append({'role': 'assistant', 'content': response_text})
            if chosen['action'] == 'stop':
                raise ValueError('agent declared episode failure:'+chosen['reason'])
            if chosen['action'] == 'submit':
                # Actual source and recipe are available for the independent
                # protected reviewer before method_admission waits on its receipt.
                source_pin = publish(root/'method.py', chosen['source'].encode(), budget, readonly=True)
                recipe_pin = publish(root/'RECIPE.json', encoded(chosen['recipe']), budget, readonly=True)
                claim_pin = publish(root/'CLAIM.json', encoded(chosen['claim']), budget, readonly=True)
                publish(root/'TRANSCRIPT.json', encoded(messages), budget, readonly=True)
                publisher({'kind': 'source_submitted', 'source': source_pin, 'recipe': recipe_pin,
                           'claim': claim_pin, 'source_path': str(root/'method.py')})
                admission = method_admission(authority, episode, source_pin, recipe_pin, claim_pin,
                                             budget, cutoff)
                final = {'source': source_pin, 'recipe_pin': recipe_pin, 'claim_pin': claim_pin,
                         'method_admission': admission, 'path': str(root/'method.py'),
                         'recipe': chosen['recipe'], 'claim': chosen['claim']}
                break
            tool_calls += 1
            need(tool_calls <= limits['tool_calls'], 'episode tool-call limit')
            call_root = fresh(root/('tool-'+str(tool_calls)), budget)
            code_pin = publish(call_root/'analysis.py', chosen['code'].encode(), budget, readonly=True)
            view = {'mounts': [], 'files': {}, 'provenance': [], 'unit_count': 0}
            if not global_episode:
                view = packet.view(session, role, 'investigate', call_root)
            output_caps = {'WORK.json': 65536, 'stdout.log': limits['tool_result_bytes'],
                           'stderr.log': limits['tool_result_bytes']}
            request = {'schema': 'neural060_worker_request_v1', 'kind': 'python', 'source': code_pin,
                       'seed': request_seed(episode, client.calls), 'output_caps': output_caps,
                       'environment': authority['environment']['versions'],
                       'clock': {'original_origin': budget.origin, 'phase_deadline': cutoff,
                                 'local_duration_cap': max(0.001, cutoff-budget.tick(cutoff))}}
            request_pin = publish(call_root/'REQUEST.json', encoded(request), budget, readonly=True)
            inputs = list(view['mounts']) + [worker_input,
                      {'source': str(call_root/'analysis.py'), 'target': '/input/analysis.py', 'pin': code_pin, 'cap': 131072},
                      {'source': str(call_root/'REQUEST.json'), 'target': '/input/REQUEST.json',
                       'pin': request_pin, 'cap': authority['resources']['request_bytes']}]
            native_limits = dict(authority['tool_native_limits'])
            remaining_cpu_ns = limits['tool_cpu_seconds']*1000000000-tool_cpu_ns
            need(remaining_cpu_ns >= 1000000000, 'no sufficient episode CPU allowance remains')
            native_limits['cpu_seconds'] = remaining_cpu_ns//1000000000
            native_limits['output_bytes'] = len(output_caps)*max(output_caps.values())
            result = native(engine, run_id=authority['study_id'], phase_id='author-'+str(episode)+'-'+str(tool_calls),
                            image=authority['environment']['image'], command=['python', '-I', '-B', '/trusted/worker.py'],
                            inputs=inputs, output_caps=output_caps, limits=native_limits, cutoff=cutoff,
                            output_root=call_root/'output', budget=budget, record=publisher)
            tool_cpu_ns += result['cpu_nanoseconds']
            need(tool_cpu_ns <= limits['tool_cpu_seconds']*1000000000, 'aggregate measured tool CPU ceiling')
            tool_output = {}
            for name in ('stdout.log', 'stderr.log'):
                body, _ = capture(call_root/'output'/name, result['artifacts'][name],
                                  limits['tool_result_bytes'], budget, readonly=True)
                logs_bytes += len(body)
                tool_output[name] = body.decode('utf-8')
            need(logs_bytes <= limits['logs_bytes'], 'complete retained tool-result limit; no silent truncation')
            work_raw, _ = capture(call_root/'output/WORK.json', result['artifacts']['WORK.json'], 65536,
                                  budget, readonly=True)
            work = parse(work_raw)
            need(work.get('request') == request_pin and work.get('completed') is True
                 and work.get('error_type') is None, 'naturally completed requested Python action')
            packet.unchanged(view['provenance'])
            messages.append({'role': 'user', 'content': encoded({'tool_call': tool_calls,
                            'result': tool_output, 'usage': {'cpu_ns': result['cpu_nanoseconds'],
                            'peak_memory_bytes': result['peak_memory_bytes']}}).decode()})
        episode_state.update(completed=True, source_sealed=True, final=final,
                             observed_end=budget.tick(cutoff), tool_calls=tool_calls, tool_cpu_ns=tool_cpu_ns,
                             provider_calls=client.calls, provider_observed_tokens=client.tokens,
                             retained_tool_bytes=logs_bytes, independent_method_reviewed=True)
        publish(root/'EPISODE.json', encoded(episode_state), budget, readonly=True)
        publisher({'kind': 'episode_completed', 'state': episode_state})
        return episode_state
    except BaseException as error:
        episode_state.update(error_type=type(error).__name__, error=str(error), tool_calls=tool_calls,
                             tool_cpu_ns=tool_cpu_ns, provider_calls=client.calls,
                             provider_observed_tokens=client.tokens, resource_usage_may_be_incomplete=True)
        # Root journal retains the failure even if the original clock leaves no
        # time for a new file; it cannot claim completion or reset the allowance.
        publisher({'kind': 'episode_failed', 'state': episode_state})
        raise
