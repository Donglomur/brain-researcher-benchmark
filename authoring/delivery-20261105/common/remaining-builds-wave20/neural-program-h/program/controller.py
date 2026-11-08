"""Complete NEURAL060 author/reference/candidate producer controller; no gold API."""
from pathlib import Path
import hashlib

from core import capture, encoded, fresh, need, parse, pin, publish
from packet import Packet, prediction
from schedule import full, MODES, REPLICATES, ROLES
from engine import Engine, native
from investigator import execute as author_episode


def numerical_seed(mode, replicate, ordinal, role):
    return int.from_bytes(hashlib.sha256(encoded(['neural060-final-v1', mode, replicate, ordinal, role])).digest()[:4], 'big')


def source_mount(path, body, target, budget):
    pinned = publish(path, body, budget, readonly=True)
    return {'source': str(path), 'target': target, 'pin': pinned, 'cap': len(body)}


def request_mount(directory, request, budget, cap):
    body = encoded(request)
    need(len(body) <= cap, 'full selected request exceeds explicit cap')
    pinned = publish(directory/'REQUEST.json', body, budget, readonly=True)
    return {'source': str(directory/'REQUEST.json'), 'target': '/input/REQUEST.json', 'pin': pinned, 'cap': cap}


def run(authority, source_bodies, source_pins, roster_bytes, runtime_pin, budget, record):
    """Caller has already authenticated all qualifications before these operands."""
    root = fresh(authority['attempt_root'], budget)
    trusted = fresh(root/'trusted', budget)
    worker = source_mount(trusted/'worker.py', source_bodies['worker.py'], '/trusted/worker.py', budget)
    ref_worker = source_mount(trusted/'reference_worker.py', source_bodies['references/worker.py'],
                              '/trusted/reference_worker.py', budget)
    ref_engine = source_mount(trusted/'reference_engine.py', source_bodies['references/engine.py'],
                              '/trusted/reference_engine.py', budget)
    prep = {name: source_pins['preparation/'+name] for name in ('prepare.py', 'native.py', 'projection.py')}
    packet = Packet(authority['packet_root'], authority['projection'], roster_bytes, prep,
                    authority['packet_limits'], budget)
    schedule, schedule_pin = full(packet.body['sessions'])
    publish(root/'SCHEDULE.json', encoded(schedule), budget, readonly=True)
    engine = Engine(authority['engine'], budget, record)
    need(not engine.owned(authority['study_id'], budget.deadline), 'fresh study has no preexisting owned containers')
    authors, fits, ref_fits, candidate_outputs, reference_outputs = {}, {}, {}, [], []
    author_root, reference_root, candidate_root = [fresh(root/name, budget) for name in ('authors', 'references', 'candidates')]
    # All six global data-free sources are sealed before adaptive test exposure.
    for index, episode in enumerate(schedule['author_episodes'], 1):
        current = None if episode[3] == 'global' else packet.body['sessions'][episode[3]-1]
        result = author_episode(authority=authority, episode=episode, session=current, packet=packet,
                                engine=engine, worker_input=worker, docs=authority['candidate_documents'],
                                output_root=author_root/str(index), budget=budget, record=record)
        authors[tuple(episode)] = result
    # One independently frozen reference study; no candidate methods, fitted
    # objects or prediction feedback enter these separate mounts.
    for index, phase in enumerate(schedule['reference_phases'], 1):
        current = packet.body['sessions'][phase['ordinal']-1]
        kind = 'fit' if phase['kind'] == 'reference_fit' else 'infer'
        role = phase['role']; shifted = phase['arm'] == 'joint_test_shift10'
        phase_root = fresh(reference_root/str(index), budget)
        cutoff = min(budget.deadline, budget.tick()+authority['reference_seconds'][kind])
        record({'kind': 'phase_entered', 'actor': 'reference', 'index': index, 'phase': phase, 'cutoff': cutoff})
        view = packet.view(current, role, kind, phase_root, shifted=shifted)
        request = {'schema': 'neural060-reference-request-v1', 'task_id': 'NEURAL-060',
                   'kind': kind, 'role': role, 'session_ordinal': current['ordinal'],
                   'session_id': current['session_id'], 'unit_count': view['unit_count'],
                   'unit_axis_sha256': current['unit_axis_sha256'] if role == 'joint' else None,
                   'engine_source': ref_engine['pin'], 'environment': authority['environment']['versions'],
                   'limits': authority['reference_worker_limits'],
                   'clock': {'original_origin': budget.origin, 'phase_deadline': cutoff,
                             'local_duration_cap': max(0.001, cutoff-budget.tick(cutoff))}, 'files': view['files']}
        mounts = [ref_worker, ref_engine, *view['mounts']]
        if kind == 'infer':
            fitted = ref_fits[(current['ordinal'], role)]
            request['model'] = fitted['pin']
            mounts.append({'source': fitted['path'], 'target': '/model/model.pkl', 'pin': fitted['pin'],
                           'cap': authority['reference_worker_limits']['model_bytes']})
        request_input = request_mount(phase_root, request, budget, authority['resources']['request_bytes'])
        mounts.append(request_input)
        output_caps = dict(authority['reference_output_caps'][kind])
        need(set(output_caps) == ({'model.pkl', 'SELECTION.json', 'WORK.json'} if kind == 'fit'
                                  else {'PREDICTIONS.json', 'WORK.json'}), 'exact reference output inventory')
        limits = dict(authority['reference_native_limits'])
        limits['output_bytes'] = len(output_caps)*max(output_caps.values())
        result = native(engine, run_id=authority['study_id'], phase_id='reference-'+str(index),
                        image=authority['environment']['image'],
                        command=['python', '-I', '-B', '/trusted/reference_worker.py', '--request', '/input/REQUEST.json'],
                        inputs=mounts, output_caps=output_caps, limits=limits, cutoff=cutoff,
                        output_root=phase_root/'output', budget=budget, record=record)
        packet.unchanged(view['provenance'])
        if kind == 'fit':
            fitted = {'path': str(phase_root/'output/model.pkl'), 'pin': result['artifacts']['model.pkl'],
                      'request': request_input['pin'], 'native': result,
                      'selection_path': str(phase_root/'output/SELECTION.json'),
                      'selection': result['artifacts']['SELECTION.json']}
            ref_fits[(current['ordinal'], role)] = fitted
            publish(phase_root/'MODEL_SEAL.json', encoded(fitted), budget, readonly=True)
        else:
            reference_outputs.append({'phase': phase, 'path': str(phase_root/'output/PREDICTIONS.json'),
                                      'prediction': result['artifacts']['PREDICTIONS.json'], 'native': result,
                                      'request': request_input['pin'], 'model': fitted['pin'],
                                      'selection_path': fitted['selection_path'], 'selection': fitted['selection'],
                                      'fit': fitted})
        record({'kind': 'phase_completed', 'actor': 'reference', 'index': index, 'phase': phase,
                'request': request_input['pin'], 'native': result})
    for index, phase in enumerate(schedule['candidate_phases'], 1):
        current = packet.body['sessions'][phase['ordinal']-1]
        kind, role = phase['kind'], phase['role']
        episode = (phase['mode'], phase['replicate'], role,
                   'global' if phase['mode'] == 'frozen_program' else current['ordinal'])
        authored = authors[episode]['final']
        fit_key = (phase['mode'], phase['replicate'], current['ordinal'], role)
        phase_root = fresh(candidate_root/str(index), budget)
        cutoff = min(budget.deadline, budget.tick()+authority['candidate_seconds'][kind])
        record({'kind': 'phase_entered', 'actor': 'candidate', 'index': index, 'phase': phase, 'cutoff': cutoff})
        view = packet.view(current, role, kind, phase_root, shifted=phase['arm'] == 'joint_test_shift10')
        seed = numerical_seed(*fit_key)
        output_caps = dict(authority['candidate_output_caps'][kind])
        need(set(output_caps) == ({'model.pkl', 'WORK.json', 'stdout.log', 'stderr.log'} if kind == 'fit'
                                  else {'PREDICTIONS.json', 'WORK.json', 'stdout.log', 'stderr.log'}),
             'exact candidate fixed output inventory')
        request = {'schema': 'neural060_worker_request_v1', 'kind': kind, 'role': role,
                   'source': authored['source'], 'recipe': authored['recipe'], 'seed': seed,
                   'environment': authority['environment']['versions'], 'files': view['files'],
                   'unit_count': view['unit_count'], 'output_caps': output_caps,
                   'input_cap': authority['packet_limits']['public_file_bytes'],
                   'model_cap': authority['resources']['model_bytes'],
                   'clock': {'original_origin': budget.origin, 'phase_deadline': cutoff,
                             'local_duration_cap': max(0.001, cutoff-budget.tick(cutoff))}}
        mounts = [worker, {'source': authored['path'], 'target': '/trusted/method.py',
                           'pin': authored['source'], 'cap': 131072}, *view['mounts']]
        if kind == 'infer':
            fitted = fits[fit_key]
            need(fitted['source'] == authored['source'] and fitted['seed'] == seed,
                 'same source and RNG for paired replay')
            request['model'] = fitted['pin']
            mounts.append({'source': fitted['path'], 'target': '/model/model.pkl', 'pin': fitted['pin'],
                           'cap': authority['resources']['model_bytes']})
        request_input = request_mount(phase_root, request, budget, authority['resources']['request_bytes'])
        mounts.append(request_input)
        limits = dict(authority['candidate_native_limits'])
        limits['output_bytes'] = len(output_caps)*max(output_caps.values())
        result = native(engine, run_id=authority['study_id'], phase_id='candidate-'+str(index),
                        image=authority['environment']['image'], command=['python', '-I', '-B', '/trusted/worker.py'],
                        inputs=mounts, output_caps=output_caps, limits=limits, cutoff=cutoff,
                        output_root=phase_root/'output', budget=budget, record=record)
        packet.unchanged(view['provenance'])
        work_raw, _ = capture(phase_root/'output/WORK.json', result['artifacts']['WORK.json'], output_caps['WORK.json'],
                              budget, readonly=True)
        work = parse(work_raw)
        need(work.get('request') == request_input['pin'] and work.get('completed') is True
             and work.get('error_type') is None, 'requested worker completion')
        if kind == 'fit':
            fitted = {'path': str(phase_root/'output/model.pkl'), 'pin': result['artifacts']['model.pkl'],
                      'source': authored['source'], 'seed': seed, 'request': request_input['pin'],
                      'native': result, 'episode': list(episode), 'method_admission': authored['method_admission']}
            fits[fit_key] = fitted
            publish(phase_root/'MODEL_SEAL.json', encoded(fitted), budget, readonly=True)
        else:
            raw, _ = capture(phase_root/'output/PREDICTIONS.json', result['artifacts']['PREDICTIONS.json'],
                             output_caps['PREDICTIONS.json'], budget, readonly=True)
            parsed = parse(raw)
            prediction(parsed, current['splits']['test']['case_ids'], authored['source'], fitted['pin'])
            need(parsed['request'] == request_input['pin'], 'exact candidate request/output join')
            candidate_outputs.append({'phase': phase, 'path': str(phase_root/'output/PREDICTIONS.json'),
                                      'prediction': result['artifacts']['PREDICTIONS.json'], 'native': result,
                                      'request': request_input['pin'], 'model': fitted['pin'],
                                      'source': authored['source'], 'episode': list(episode),
                                      'method_admission': authored['method_admission'], 'fit': fitted})
        record({'kind': 'phase_completed', 'actor': 'candidate', 'index': index, 'phase': phase,
                'request': request_input['pin'], 'native': result})
    need(len(candidate_outputs) == 522 and len(reference_outputs) == 87 and len(authors) == 180,
         'all complete panels; no omitted roles/cases/replications')
    need(not engine.owned(authority['study_id'], budget.deadline), 'all owned native containers retired')
    result = {'schema': 'neural060_producer_complete_v1', 'task_id': 'NEURAL-060',
              'runtime_source': runtime_pin, 'projection': packet.projection_pin,
              'study_id': authority['study_id'], 'schedule': schedule_pin,
              'authors': [{'episode': list(k), 'record': v} for k, v in authors.items()],
              'candidate_outputs': candidate_outputs, 'reference_outputs': reference_outputs,
              'candidate_fit_count': len(fits), 'reference_fit_process_count': len(ref_fits),
              'reference_constituent_fits': 928, 'reference_family_inferences': 261,
              'original_origin': budget.origin, 'original_deadline': budget.deadline,
              'prepublication_resource_snapshot': budget.record(),
              'private_targets_opened': False, 'qualified_neural_contribution': None}
    result_pin = publish(root/'PRODUCER.json', encoded(result), budget, readonly=True)
    record({'kind': 'producer_completed', 'producer': result_pin, 'path': str(root/'PRODUCER.json')})
    return result_pin
