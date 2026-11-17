"""Trusted full-paper execution; candidate code belongs only in external transport."""
import hashlib
import time
from .validation import need, exact, matrix, vector, digest, encoded
from .artifacts import Collector


def acknowledge(transport, request, operation):
    need(transport.exchange(request) == {'ok': operation}, 'exact worker acknowledgment')


def run_case(case, packet, transport, collector, source_sha256, public_config):
    """No protected target data is accessed here, including in analysis mode."""
    need(packet.case == case, 'bound case/input identity')
    from .bindings import validate_bundle
    validate_bundle(case,packet.index,public_config)
    config_commitment = digest(public_config)
    need(config_commitment == case['config_sha256'], 'immutable public model configuration')
    width = packet.index['output_schema']['width']
    public = {'id': 'case',
              'mode': case['mode'], 'output_width': width}
    # A worker is isolated to this case. A constant token avoids a dictionary
    # attack on a low-entropy count/regime case-name digest; private IDs stay in
    # trusted collection and accounting only.
    initial = transport.exchange({'op': 'begin', 'case': public, 'config': public_config['program']})
    need(initial == {'ok': 'begin', 'source_sha256': source_sha256}, 'source-frozen worker')
    for stream in packet.streams('train'):
        acknowledge(transport, {'op': 'training_start', 'segment': stream['id']}, 'training_start')
        for index, row in enumerate(packet.rows(stream)):
            acknowledge(transport, {'op': 'train', 'index': index, 'observation': row}, 'train')
        acknowledge(transport, {'op': 'training_end'}, 'training_end')
    acknowledge(transport, {'op': 'fit'}, 'fit')
    if packet.index['output_schema']['training_rates_required']:
        for stream in packet.streams('train'):
            for index, row in enumerate(packet.rows(stream)):
                answer = transport.exchange({'op': 'training_rate', 'observation': row})
                exact(answer, ('prediction',), 'full training rate estimate')
                values = vector(answer['prediction'], width)
                need(all(x > 0 for x in values), 'positive training rates')
                collector.row('training:' + stream['id'], index, row['sample_id'], values)
    if case['mode'] == 'behavior_causal':
        need(width is not None and packet.streams('query'), 'behavioral complete query/target shape')
        for stream in packet.streams('query'):
            acknowledge(transport, {'op': 'trial', 'trial': hashlib.sha256(stream['trial'].encode()).hexdigest()}, 'trial')
            histories = [s for s in packet.streams('history') if s['trial'] == stream['trial']]
            for history in histories:
                for index, row in enumerate(packet.rows(history)):
                    acknowledge(transport, {'op': 'history', 'index': index, 'neural': row['neural']}, 'history')
            for index, row in enumerate(packet.rows(stream)):
                answer = transport.exchange({'op': 'predict', 'index': index, 'neural': row['neural']})
                exact(answer, ('prediction',), 'current prediction')
                collector.row(stream['id'], index, row['sample_id'], vector(answer['prediction'], width))
    elif case['mode'] in ('neural_acausal', 'behavior_acausal'):
        need(width is not None and packet.streams('query'), 'NLB complete held-neuron query shape')
        for stream in packet.streams('query'):
            # NLB deliberately allows this epoch, not any other trial or prefix.
            acknowledge(transport, {'op': 'epoch_start', 'rows': stream['rows']}, 'epoch_start')
            row_ids = []
            for index, row in enumerate(packet.rows(stream)):
                row_ids.append(row['sample_id'])
                acknowledge(transport, {'op': 'epoch_row', 'index': index, 'neural': row['neural']}, 'epoch_row')
            acknowledge(transport, {'op': 'epoch_end'}, 'epoch_end')
            for start in range(0, len(row_ids), 16):
                stop = min(start + 16, len(row_ids))
                answer = transport.exchange({'op': 'epoch_result', 'start': start, 'stop': stop})
                exact(answer, ('prediction',), 'acausal rate predictions')
                prediction = matrix(answer['prediction'], stop-start, width)
                for index, values in enumerate(prediction, start):
                    need(case['mode'] != 'neural_acausal' or all(x > 0 for x in values), 'positive rate outputs, native floor bound by recipe')
                    collector.row(stream['id'], index, row_ids[index], values)
    else:
        need(case['mode'] == 'analysis' and packet.streams('analysis'), 'declared scientific analysis inputs')
        for stream in packet.streams('analysis'):
            for index, row in enumerate(packet.rows(stream)):
                # Analysis records are explicitly admitted public observations,
                # never implicitly converted from target streams.
                acknowledge(transport, {'op': 'analysis_row', 'stream': stream['id'],
                                        'index': index, 'observation': row}, 'analysis_row')
        answer = transport.exchange({'op': 'analyze'})
        exact(answer, ('outputs',), 'complete analysis result')
        need(type(answer['outputs']) is dict and set(answer['outputs']) == set(case['outputs']), 'all declared analytic output keys')
        for index, key in enumerate(case['outputs']):
            collector.row('analysis', index, key, answer['outputs'][key])
    acknowledge(transport, {'op': 'finish'}, 'finish')
    need(digest(public_config) == config_commitment, 'configuration unchanged during run')
    return transport.finish()


def valid_lifecycle(record):
    need(type(record) is dict and record.get('exit_code') == 0, 'zero worker exit')
    for field in ('natural_exit', 'streams_closed', 'container_absent',
                  'client_group_absent', 'stdout_eof', 'stderr_eof'):
        need(record.get(field) is True, 'observed successful lifecycle: ' + field)


def execute(admission, role, packet_factory, transport_factory, config_factory,
            source_sha256, output_root, journal, observer, *, origin, normal_end, budget=None):
    """Concrete all-case loop; factory/observer implementations are trusted custody.

    Authenticated execution requires a separately root-selected admission. The
    source-phase authority cannot satisfy it. No candidate function runs in host.
    """
    admission.recheck()
    need(role in ('candidate_A', 'candidate_B', 'reference'), 'trusted role')
    need(origin <= time.monotonic() < normal_end, 'original whole-session deadline')
    need(len(admission.plan['cases']) <= admission.value['limits']['attempts'], 'whole attempted case budget')
    outputs, failures, remaining_output = [], [], admission.value['limits']['output_bytes']
    for ordinal, case in enumerate(admission.plan['cases']):
        admission.recheck()
        if role == 'reference':
            need(source_sha256 == case['reference_source_sha256'], 'independently frozen reference source, not candidate nomination')
        attempt_id = f'{role}:{ordinal}'
        started, sink, transport, artifact, lifecycle = time.monotonic(), None, None, None, None
        error, status, observer_started = None, 'not_started', False
        try:
            need(started < normal_end, 'no case starts after original deadline')
            observer.begin(attempt_id, origin, normal_end)
            observer_started = True
            packet = packet_factory(case)
            need(remaining_output > 0, 'whole-role output budget exhausted')
            sink = Collector(output_root, f'{role}-{ordinal}.jsonl', case['id'], remaining_output,budget=budget)
            transport=transport_factory(case, source_sha256, origin, normal_end)
            with transport:
                lifecycle = run_case(case, packet, transport, sink, source_sha256, config_factory(case))
            valid_lifecycle(lifecycle)
            need(time.monotonic() < normal_end, 'completion within original deadline')
            artifact, status = sink.close(True), 'success'
        except Exception as failure:
            error, status = type(failure).__name__ + ': ' + str(failure)[:300], 'failure'
            if sink is not None and not sink.finished:
                artifact = sink.close(False, error)
            lifecycle = getattr(transport, 'record', lifecycle)
            failures.append({'case': case['id'], 'error': error, 'artifact': artifact})
        finally:
            # External observer is mandatory; guessed zero GPU/RSS/token charges
            # are not substituted for unavailable resource observations.
            resource_error = None
            try:
                need(observer_started, 'observer did not start; no resource estimate invented')
                measured = observer.finish(attempt_id)
            except Exception as measurement_failure:
                measured = {k: None for k in ('wall_seconds', 'cpu_seconds', 'gpu_seconds', 'token_count', 'bytes_written', 'peak_rss_bytes')}
                resource_error = type(measurement_failure).__name__ + ': ' + str(measurement_failure)[:300]
                if status == 'success':
                    status = 'failure'
                    failures.append({'case': case['id'], 'error': resource_error, 'artifact': artifact})
            if artifact is not None:
                remaining_output -= artifact['bytes']
            if status == 'success':
                outputs.append({'case': case['id'], 'artifact': artifact})
            journal.append({'id': attempt_id, 'case': case['id'], 'role': role, 'status': status,
                            'wall_seconds': measured['wall_seconds'], 'cpu_seconds': measured['cpu_seconds'],
                            'gpu_seconds': measured['gpu_seconds'], 'token_count': measured['token_count'],
                            'bytes_written': measured['bytes_written'], 'peak_rss_bytes': measured['peak_rss_bytes'],
                            'source_sha256': source_sha256, 'output': artifact, 'lifecycle': lifecycle, 'error': error,
                            'resource_error': resource_error})
    admission.recheck()
    return {'schema': 'motormint_execution_result_v1', 'role': role,
            'admission_sha256': admission.commitment, 'plan_sha256': admission.plan_commitment,
            'outputs': outputs, 'failures': failures, 'complete': not failures,
            'evidence': admission.evidence_label(), 'scientifically_qualified': False}
