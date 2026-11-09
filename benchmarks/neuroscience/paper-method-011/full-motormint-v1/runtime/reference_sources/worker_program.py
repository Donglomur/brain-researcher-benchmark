"""Concrete sandbox reference dispatcher, never imported by source inspection.

Unchanged accepted comparator bridge is integrated for the selected causal
routes. Missing original full-paper extensions must be independently captured
in the reference-only context and admitted, not synthesized from method labels.
"""
import hashlib
import importlib.util
from pathlib import Path


def checked_module(filename, size, expected):
    root = Path('/context')
    if '/' in filename or '\\' in filename:
        raise ValueError('fixed reference context member')
    path = root / filename
    if path.is_symlink():
        raise ValueError('reference source symlink')
    with path.open('rb') as stream:
        raw = stream.read(size + 1)
    if len(raw) != size or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('independently admitted reference source mismatch')
    spec = importlib.util.spec_from_file_location('independent_reference', path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(raw,str(path),'exec',dont_inherit=True),module.__dict__)
    return module


def create(case, configuration):
    route = configuration.get('reference_route')
    if route == 'accepted_legacy_comparators':
        if case['mode'] != 'behavior_causal':
            raise ValueError('legacy comparator finite-window route is causal only')
        source = checked_module('author_comparators.py', 10507,
                                '9f842fa7de41dcd6896a7893f69ef435842dd67c1b03f600234e283f5c4fc4b4')
        native = source.create(configuration['legacy_case'], configuration['legacy_config'],
                               configuration['seed'], configuration['legacy_dataset'])
        return Legacy(native)
    if route == 'native_mint_three_task_prefix':
        source = checked_module('native_mint_program.py', 4193, '152f3167e293e2c51a945df90dd665ca19c0dc626ad7b9af523b7f3a060ca693')
        return source.create(case, configuration['native_config'])
    if route == 'independently_bound_original_extension':
        binding = configuration['extension_source']
        if set(binding) != {'path', 'bytes', 'sha256'} or binding['path'] != 'original_extension.py':
            raise ValueError('exact original extension binding required')
        source = checked_module(binding['path'], binding['bytes'], binding['sha256'])
        return source.create(case, configuration['extension_config'])
    raise ValueError('No independently admitted source recipe; original scope remains required')


class Legacy:
    def __init__(self, native):
        self.native = native

    def training_start(self, segment):
        self.segment, self.count = {'id': segment}, 0

    def train(self, observation):
        self.native.train_chunk(self.segment, self.count, [observation['neural']],
                                [observation['behavior']], [observation['auxiliary']], False)
        self.count += 1

    def training_end(self):
        self.native.train_chunk(self.segment, self.count, [], [], [], True)

    def fit(self):
        self.native.fit()

    def start_trial(self, opaque_trial):
        # The native finite-window bridge needs the authentic prefix length;
        # start only once history ends, without revealing future query duration.
        self.trial, self.past, self.predicted, self.initialized = opaque_trial, [], 0, False

    def history(self, neural):
        self.past.append(neural)

    def predict(self, neural):
        if not self.initialized:
            self.native.start_trial({'id': self.trial, 'history_samples': len(self.past)})
            for start in range(0, len(self.past), 16):
                self.native.history_chunk(start, self.past[start:start+16])
            self.past.clear(); self.initialized = True
        answer = self.native.predict(self.predicted, neural)
        self.predicted += 1
        return answer
