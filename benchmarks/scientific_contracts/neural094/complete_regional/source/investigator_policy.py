"""Concrete prospective global investigator policy, container only.

Prompt and action limits are required captured capsule operands. Arbitrary
Python below executes inside this fresh isolated bundle stage, never on host.
No model endpoint, credential, protected label, or cross-bundle history exists
in this interface. Source construction does not admit model use.
"""
import contextlib
import io
import json
from pathlib import Path


def _need(ok, why):
    if not ok:
        raise ValueError(why)


class Capture(io.TextIOBase):
    def __init__(self, bound):
        self.bound, self.used, self.parts = bound, 0, []
    def write(self, text):
        self.used += len(text.encode())
        _need(self.used <= self.bound, 'Bounded local tool output')
        self.parts.append(text)
        return len(text)


def _strict(raw):
    def pairs(rows):
        out = {}
        for k, v in rows:
            _need(k not in out, 'Duplicate investigator JSON key'); out[k] = v
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: _need(False, 'Nonfinite JSON'))


def investigate(public, tools):
    cfg_path = Path('/capsule/INSTRUCTIONS.json')
    _need(cfg_path.stat().st_size <= public['payload']['instruction_bytes'], 'Captured instruction extent')
    cfg = _strict(cfg_path.read_bytes())
    _need(set(cfg) == {'prompt', 'max_actions', 'max_output_tokens', 'code_bytes', 'tool_output_bytes'},
          'Explicit complete investigator operands')
    _need(type(cfg['prompt']) is str and bool(cfg['prompt']), 'Frozen prompt')
    for k in set(cfg)-{'prompt'}:
        _need(type(cfg[k]) is int and cfg[k] > 0, 'Positive explicit action limit')
    phase = public['phase']
    instruction = (
        'Fit/tune using only the full original training and validation packet at /training/MANIFEST.json. '
        'No query is mounted. Serialize all retained state into /output/model.bin and finish with fit_files:["model.bin"].'
        if phase == 'train' else
        'Predict every query token in /query/MANIFEST.json using the readonly state /fit. '
        'Training labels are not mounted. Within this arm, adaptation using unlabeled query inputs is permitted. '
        'Do not alter sealed state or communicate across arms/bundles. Finish with predictions, a list of '
        '{token,probabilities:[right,NoGo,left]} records. No private scores/targets or feedback are available.')
    messages = [{'role': 'system', 'content': cfg['prompt']}, {'role': 'user', 'content': instruction +
                ' Return JSON {action:"python",code:...} or {action:"finish",result:...}.'}]
    state = {'__name__': '__neural094_investigation__'}
    for _ in range(cfg['max_actions']):
        reply = tools.generate(messages, cfg['max_output_tokens'])
        value = _strict(reply['text'])
        _need(type(value) is dict and value.get('action') in ('python', 'finish'), 'Explicit action')
        messages.append({'role': 'assistant', 'content': reply['text']})
        if value['action'] == 'finish':
            _need(set(value) == {'action', 'result'}, 'Exact finish action')
            return value['result']
        _need(set(value) == {'action', 'code'} and type(value['code']) is str
              and 0 < len(value['code'].encode()) <= cfg['code_bytes'], 'Bounded isolated Python action')
        capture = Capture(cfg['tool_output_bytes'])
        error = None
        try:
            with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
                exec(compile(value['code'], '<isolated-neural094-action>', 'exec'), state)
        except Exception as exc:
            error = type(exc).__name__
        messages.append({'role': 'user', 'content': json.dumps(
            {'stdout': ''.join(capture.parts), 'error_type': error}, allow_nan=False)})
    raise ValueError('Investigation action allocation exhausted')


def train(public, tools):
    result = investigate(public, tools)
    _need(type(result) is dict and result == {'fit_files':['model.bin']}, 'Complete sealed fitting inventory proposal')
    return result


def predict(public, tools):
    result = investigate(public, tools)
    _need(type(result) is list, 'Complete prediction list')
    return result
