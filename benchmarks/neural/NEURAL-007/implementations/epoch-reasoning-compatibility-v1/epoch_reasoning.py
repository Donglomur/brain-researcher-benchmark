"""Explicit current-turn reasoning adapter for the existing isolated epoch route.

Already-loaded donor modules and their runtime are trusted operator operands.
This module imports no donor, mutates no donor globals and performs no work on
import. Exact original run/replay code is rebound to adapter-private globals.
"""
from __future__ import annotations

import hashlib
import ast
import json
import os
from pathlib import Path
import stat
from types import FunctionType, ModuleType, SimpleNamespace

POLICY = 'current_turn_reasoning_v1'
PARSER_BINDING = 'pinned_previous_initializer_removed_v1'
SOURCE_BASE = 'd15803fb8ab39d377563f56c99d3a21a81f65f1f'
EXPECTED = {
    'epoch_provider': {'bytes': 16962, 'sha256': '4205f7d9c8ee6bd7c3ac6968bab5576f4c13a0d4944a2acb45d57356393b5d47'},
    'epoch_visual': {'bytes': 15668, 'sha256': '003bc12b1e9340d56daa2de767ba9156574409361a9da4e953978a23fd0f5828'},
    'reasoning_provider': {'bytes': 10359, 'sha256': '02f30555f6c0ec317581d88e9bbed9d481396f5c0d668f574ea6d6bb6c6d3e77'},
    'reasoning_bindings': {'bytes': 487, 'sha256': '6d216c24d45109531c774a7eecac61317b6f79547a567ed1495657ef7c8f03a9'},
    'previous_provider': {'bytes': 18476, 'sha256': 'a41bff305cfbcba79c4317be59f97c5cbe7f68d3cbd06a942a523ffc491655fb'},
    'previous_policy': {'bytes': 12079, 'sha256': '4201c0cc95b8db65da3bb034651e0abe5fd9f0ac2456ad81c0ad0a79c0241cb2'},
    'previous_bindings': {'bytes': 885, 'sha256': '7a5cfab381098d0562fbfaecfeceefd7fb2da9b262cd91718b24a01d887f56cf'},
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def _capture(path, expected=None, cap=32768):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts
         and not any(p.is_symlink() for p in (path, *path.parents)), 'Ordinary absolute source path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= cap, 'Bounded ordinary source file')
        raw = stream.read(cap + 1)
        fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        need(fields(before) == fields(os.fstat(stream.fileno())) == fields(path.lstat())
             and len(raw) == before.st_size, 'Stable exact source body')
        need(expected is None or pin(raw) == expected, 'Frozen donor source identity mismatch')
    return raw


def _identity(epoch, reasoning):
    need(type(epoch) is ModuleType and type(reasoning) is ModuleType
         and type(epoch.V) is ModuleType and type(reasoning.previous) is ModuleType,
         'Explicit already-loaded trusted donor modules')
    previous = reasoning.previous
    paths = {
        'epoch_provider': epoch.__file__, 'epoch_visual': epoch.V.__file__,
        'reasoning_provider': reasoning.__file__,
        'reasoning_bindings': Path(reasoning.__file__).with_name('SOURCE_BINDINGS.json'),
        'previous_provider': previous.__file__, 'previous_policy': previous.policy.__file__,
        'previous_bindings': Path(previous.__file__).with_name('SOURCE_BINDINGS.json'),
    }
    for name, path in paths.items():
        _capture(path, EXPECTED[name])
    here = Path(__file__).resolve().parent
    bindings = _capture(here / 'SOURCE_BINDINGS.json', cap=8192)
    need(json.loads(bindings) == {'schema': 'sleep007-epoch-reasoning-dependencies/v1',
                                'source_base': SOURCE_BASE, 'members': EXPECTED},
         'Exact declared adapter dependencies')
    own = _capture(Path(__file__).resolve())
    need(epoch.CONDITION == epoch.V.CONDITION == 'epoch_isolated_raw_viewer_zero_shot_v1'
         and reasoning.POLICY == POLICY, 'Unchanged epoch condition and selected reasoning policy')
    for name in ('run_epoch', 'audit_session'):
        function = getattr(epoch, name)
        need(type(function) is FunctionType and function.__globals__ is vars(epoch),
             'Original trusted epoch function namespace')
    return {'adapter': pin(own), 'bindings': pin(bindings), 'dependencies': dict(EXPECTED),
            'source_base': SOURCE_BASE}


def _clone(function, namespace):
    result = FunctionType(function.__code__, namespace, function.__name__,
                          function.__defaults__, function.__closure__)
    result.__kwdefaults__ = function.__kwdefaults__
    return result


class Adapter:
    """One immutable declared execution policy; each call still opens a fresh target.

    It reuses the caller's admitted runtime objects without modifying them. This
    is trusted source composition, not hostile-code isolation or qualification.
    """
    def __init__(self, epoch, reasoning, runtime, *, execution_policy, reasoning_effort):
        need(execution_policy == POLICY and type(execution_policy) is str,
             'Explicit current-turn reasoning opt-in required')
        need(type(reasoning_effort) is str and reasoning_effort in reasoning.EFFORTS,
             'Explicit frozen documented reasoning effort required')
        identity = _identity(epoch, reasoning)
        need(type(runtime) is dict and runtime.get('contract') is not None
             and runtime['contract'].TOTAL == 5450
             and runtime['contract'].CASES == (('development-001', 2780), ('development-002', 2670)),
             'Original complete two-person epoch runtime')
        selected = {'execution_policy': POLICY,
                    'requested_reasoning': {'context': 'current_turn', 'effort': reasoning_effort},
                    'prior_turn_opaque_replay': False, 'source': identity,
                    'parser_binding': getattr(reasoning, '_epoch_parser_binding',
                                              'already_loaded_authenticated_parser_v1')}
        # A canonical private copy prevents later caller edits to source/policy
        # dictionaries from changing the selected receipt identity.
        selected = json.loads(encode(selected))
        private_runtime = dict(runtime)
        private_runtime['source'] = {'epoch_runtime': json.loads(encode(runtime['source'])),
                                     'reasoning_compatibility': selected}
        visual = SimpleNamespace(**vars(epoch.V))

        def request_bytes(session, model, budget, knowledge):
            value = epoch.V.encode  # Use the original request JSON encoding.
            request = json.loads(epoch.V.request_bytes(session, model, budget, knowledge))
            need('reasoning' not in request, 'Original epoch request has no implicit reasoning policy')
            request['reasoning'] = dict(selected['requested_reasoning'])
            raw = value(request)
            need(len(raw) <= budget.max_request_bytes <= session.runtime['sender'].REQUEST_CAP,
                 'Complete reasoning epoch request must fit original byte ceiling')
            return raw

        visual.request_bytes = request_bytes

        class ReplyContext(reasoning.Bridge):
            def __init__(self, model, budget):
                # Only the fields used by the pinned response parser. No viewer
                # Bridge constructor, policy change, history or sender is needed.
                self.model, self.b, self.stage = model, budget, None
                self.reasoning_effort = reasoning_effort

        def response_action(current_runtime, model, budget, raw, token_bound):
            context = ReplyContext(model, budget)
            return context.response(raw, token_bound)

        def config_value(current_runtime, session, knowledge, budget):
            value = epoch.config_value(current_runtime, session, knowledge, budget)
            value['reasoning_compatibility'] = json.loads(encode(selected))
            return value

        def event(config_pin, session, deadline, sequence, previous, request, response,
                  bound, action, details, status, failure):
            value = epoch._event(config_pin, session, deadline, sequence, previous,
                                 request, response, bound, action, details, status, failure)
            value.update(execution_policy=POLICY,
                         requested_reasoning=dict(selected['requested_reasoning']),
                         prior_turn_opaque_replay=False)
            # Raw RESPONSE.bin is always the authority, including failed parses.
            # Bounded metadata mirrors the existing reasoning receipt projection;
            # output items / encrypted content are never copied into it.
            if type(response) is bytes:
                try:
                    decoded = reasoning.decode(response)
                    if type(decoded) is dict:
                        report = {key: decoded[key] for key in ('status', 'error', 'incomplete_details',
                                  'usage', 'reasoning', 'input_transformations') if key in decoded}
                        projection = encode({'provider_report': report})
                        need(len(projection) <= 4096, 'Bounded private reasoning report')
                        value['provider_report'] = report
                        value['provider_report_is_action_authority'] = False
                except (ValueError, UnicodeError, TypeError, RecursionError, OverflowError):
                    value['provider_report_projection'] = 'unavailable_raw_body_retained'
            return value

        def end(*args):
            value = epoch._end(*args)
            value.update(execution_policy=POLICY,
                         requested_reasoning=dict(selected['requested_reasoning']),
                         prior_turn_opaque_replay=False)
            return value

        namespace = dict(vars(epoch))
        namespace.update(V=visual, response_action=response_action,
                         config_value=config_value, _event=event, _end=end)
        self.__run = _clone(epoch.run_epoch, namespace)
        self.__audit = _clone(epoch.audit_session, namespace)
        self.__runtime = private_runtime
        self.__selected = selected

    @property
    def policy(self):
        return json.loads(encode(self.__selected))

    def run_epoch(self, packet, knowledge, budget, custody_root, credential, input_token_bound, **kwargs):
        return self.__run(self.__runtime, packet, knowledge, budget, custody_root,
                          credential, input_token_bound, **kwargs)

    def audit_session(self, session_root, packet, knowledge):
        return self.__audit(session_root, packet, self.__runtime, knowledge)


def bind(epoch_provider, reasoning_provider, runtime, *, execution_policy, reasoning_effort):
    """Explicit opt-in; there is no default, automatic fallback or provider call."""
    return Adapter(epoch_provider, reasoning_provider, runtime,
                   execution_policy=execution_policy, reasoning_effort=reasoning_effort)


def load_selected(selection, epoch_provider, runtime):
    """Authenticate one operator selection and privately bind the pinned parser.

    Only the exact pinned donor's `previous = load_previous()` initializer is
    removed. Its already-authenticated previous provider is supplied instead.
    Every parser class/method is compiled unchanged; no import registry changes.
    """
    need(type(selection) is dict and set(selection) == {
        'execution_policy', 'reasoning_effort', 'adapter', 'bindings', 'reasoning_provider'},
        'Exact explicit operator reasoning selection')
    need(selection['execution_policy'] == POLICY, 'Explicit current-turn reasoning selection')
    for name in ('adapter', 'bindings', 'reasoning_provider'):
        descriptor = selection[name]
        need(type(descriptor) is dict and set(descriptor) == {'path', 'bytes', 'sha256'},
             'Exact selected source descriptor')
        expected = {key: descriptor[key] for key in ('bytes', 'sha256')}
        _capture(descriptor['path'], expected)
    need(Path(selection['adapter']['path']) == Path(__file__).resolve()
         and Path(selection['bindings']['path']) == Path(__file__).resolve().with_name('SOURCE_BINDINGS.json'),
         'Selected adapter and adjacent binding identity')
    parser_path = Path(selection['reasoning_provider']['path'])
    raw = _capture(parser_path, EXPECTED['reasoning_provider'])
    previous = runtime['provider']
    need(type(previous) is ModuleType, 'Authenticated original provider module required')
    _capture(previous.__file__, EXPECTED['previous_provider'])
    _capture(previous.policy.__file__, EXPECTED['previous_policy'])
    _capture(Path(previous.__file__).with_name('SOURCE_BINDINGS.json'), EXPECTED['previous_bindings'])
    _capture(parser_path.with_name('SOURCE_BINDINGS.json'), EXPECTED['reasoning_bindings'])
    tree = ast.parse(raw, filename=str(parser_path))
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == 'previous' for target in node.targets)]
    need(len(assignments) == 1, 'One pinned previous-provider initializer')
    node = assignments[0]
    need(len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
         and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
         and node.value.func.id == 'load_previous' and not node.value.args and not node.value.keywords,
         'Exact pinned previous-provider initializer shape')
    tree.body.remove(node)
    private = ModuleType('sleep007_private_reasoning_parser')
    private.__file__ = str(parser_path)
    private.previous = previous
    exec(compile(tree, str(parser_path), 'exec'), private.__dict__)
    private._epoch_parser_binding = PARSER_BINDING
    adapter = bind(epoch_provider, private, runtime,
                   execution_policy=selection['execution_policy'],
                   reasoning_effort=selection['reasoning_effort'])
    identity = adapter.policy['source']
    need(all(identity[name] == {key: selection[name][key] for key in ('bytes', 'sha256')}
             for name in ('adapter', 'bindings')), 'Selected source identity remains exact through binding')
    return adapter
