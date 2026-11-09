"""Sandbox-only agent program host. Python is not the isolation boundary."""
import hashlib
import json
import math
import sys
import types
from contextlib import redirect_stdout

CAP = 2097152


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(stream):
    raw = stream.readline(CAP + 1)
    require(0 < len(raw) <= CAP and raw.endswith(b'\n'), 'bounded complete frame')
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, 'duplicate frame key'); out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite frame')))


def write(stream, value):
    raw = json.dumps(value, allow_nan=False, separators=(',', ':')).encode() + b'\n'
    require(len(raw) <= CAP, 'response bound')
    stream.write(raw); stream.flush()


def serve(source, expected_sha, input_stream, output_stream):
    require(len(source) <= 262144 and hashlib.sha256(source).hexdigest() == expected_sha, 'source commitment')
    module = types.ModuleType('frozen_motormint_candidate')
    with redirect_stdout(sys.stderr):
        exec(compile(source, '<frozen-program>', 'exec'), module.__dict__)
    frame = read(input_stream)
    require(set(frame) == {'op', 'case', 'config'} and frame['op'] == 'begin', 'begin once')
    case = frame['case']
    require(set(case) == {'id', 'mode', 'output_width'} and case['mode'] in ('behavior_causal', 'behavior_acausal', 'neural_acausal', 'analysis'), 'public case')
    with redirect_stdout(sys.stderr):
        program = module.create(case, frame['config'])
    write(output_stream, {'ok': 'begin', 'source_sha256': expected_sha})
    fitted, segment, count, trial, predicted, history, analyzed = False, None, 0, None, 0, 0, False
    epoch, epoch_prediction, epoch_count, epoch_output = None, None, 0, 0
    while True:
        frame = read(input_stream); op = frame.get('op')
        with redirect_stdout(sys.stderr):
            if op == 'training_start':
                require(not fitted and segment is None and set(frame) == {'op', 'segment'}, 'training segment order')
                segment, count = frame['segment'], 0; program.training_start(segment); answer = {'ok': op}
            elif op == 'train':
                require(not fitted and segment is not None and set(frame) == {'op', 'index', 'observation'} and frame['index'] == count, 'ordered training')
                program.train(frame['observation']); count += 1; answer = {'ok': op}
            elif op == 'training_end':
                require(not fitted and segment is not None and count > 0 and set(frame) == {'op'}, 'complete training segment')
                program.training_end(); segment = None; answer = {'ok': op}
            elif op == 'fit':
                require(not fitted and segment is None and set(frame) == {'op'}, 'fit once')
                program.fit(); fitted = True; answer = {'ok': op}
            elif op == 'trial':
                require(fitted and case['mode'] == 'behavior_causal' and set(frame) == {'op', 'trial'}, 'causal trial only')
                trial, predicted, history = frame['trial'], 0, 0; program.start_trial(trial); answer = {'ok': op}
            elif op == 'history':
                require(trial is not None and predicted == 0 and set(frame) == {'op', 'index', 'neural'} and frame['index'] == history, 'past prefix order')
                program.history(frame['neural']); history += 1; answer = {'ok': op}
            elif op == 'predict':
                require(trial is not None and set(frame) == {'op', 'index', 'neural'} and frame['index'] == predicted, 'one current row in order')
                value = program.predict(frame['neural']); predicted += 1
                require(type(value) is list and len(value) == case['output_width'] and all(type(x) in (int, float) and math.isfinite(x) for x in value), 'finite exact output width')
                answer = {'prediction': value}
            elif op == 'epoch_start':
                require(fitted and epoch is None and case['mode'] in ('neural_acausal', 'behavior_acausal') and set(frame) == {'op', 'rows'}, 'acausal epoch only')
                require(type(frame['rows']) is int and 1 <= frame['rows'] <= 10000000, 'explicit bounded epoch rows')
                epoch, epoch_count, epoch_output, epoch_prediction = [], frame['rows'], 0, None
                answer = {'ok': op}
            elif op == 'epoch_row':
                require(epoch is not None and epoch_prediction is None and set(frame) == {'op', 'index', 'neural'} and frame['index'] == len(epoch) < epoch_count, 'epoch neural stream order')
                epoch.append(frame['neural']); answer = {'ok': op}
            elif op == 'epoch_end':
                require(epoch is not None and epoch_prediction is None and len(epoch) == epoch_count and set(frame) == {'op'}, 'complete epoch before estimation')
                epoch_prediction = program.epoch(epoch)
                require(type(epoch_prediction) is list and len(epoch_prediction) == epoch_count, 'complete epoch output rows')
                answer = {'ok': op}
            elif op == 'epoch_result':
                require(epoch_prediction is not None and set(frame) == {'op', 'start', 'stop'} and frame['start'] == epoch_output and type(frame['stop']) is int and epoch_output < frame['stop'] <= min(epoch_output+16, epoch_count), 'bounded ordered result chunks')
                answer = {'prediction': epoch_prediction[epoch_output:frame['stop']]}
                epoch_output = frame['stop']
                if epoch_output == epoch_count:
                    epoch, epoch_prediction = None, None
            elif op == 'training_rate':
                require(fitted and case['mode'] == 'neural_acausal' and set(frame) == {'op', 'observation'}, 'NLB training rate only')
                answer = {'prediction': program.training_rate(frame['observation'])}
            elif op == 'analysis_row':
                require(fitted and not analyzed and case['mode'] == 'analysis' and set(frame) == {'op', 'stream', 'index', 'observation'}, 'analysis input phase')
                program.analysis_row(frame['stream'], frame['index'], frame['observation']); answer = {'ok': op}
            elif op == 'analyze':
                require(fitted and not analyzed and case['mode'] == 'analysis' and set(frame) == {'op'}, 'analysis result once')
                answer = {'outputs': program.analyze()}; analyzed = True
            elif op == 'finish':
                require(fitted and segment is None and epoch is None and set(frame) == {'op'}, 'finish after fit and complete epoch')
                require(case['mode'] != 'analysis' or analyzed, 'analysis result required')
                if hasattr(program, 'close'):
                    program.close()
                write(output_stream, {'ok': op}); return
            else:
                raise ValueError('unknown or out-of-phase operation')
        write(output_stream, answer)


if __name__ == '__main__':
    require(len(sys.argv) == 3, 'source path and commitment')
    with open(sys.argv[1], 'rb') as handle:
        body = handle.read(262145)
    serve(body, sys.argv[2], sys.stdin.buffer, sys.stdout.buffer)
