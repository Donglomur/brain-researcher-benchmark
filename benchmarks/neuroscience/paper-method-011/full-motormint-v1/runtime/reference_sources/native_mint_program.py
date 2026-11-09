"""Prospective Python/MATLAB-engine connection for three existing native routes.

Engine import/launch occurs only on separately admitted execution. Original
extraction, alignment, conditions, runtime/licensing and prefix cost remain
unqualified. This deliberately cannot invent Cycle or additional task packages.
"""
import json
import re


class NativeMint:
    def __init__(self, case, config):
        if case['mode'] != 'behavior_causal' or config['dataset'] not in ('Area2_Bump', 'MC_Maze', 'MC_RTT'):
            raise ValueError('only three source-bound causal native routes exist')
        required = {'dataset','fit_request','condition_map','behavior_columns','native_source_evidence_sha256'}
        if set(config) != required or re.fullmatch('[a-f0-9]{64}', config['native_source_evidence_sha256']) is None:
            raise ValueError('independently bound native configuration')
        request = config['fit_request']
        if request.get('dataset') != config['dataset'] or any(request.get(k) is not True for k in
                ('native_alignment_verified','training_only','source_conditions_verified')):
            raise ValueError('original source/native alignment admission')
        self.config, self.request, self.training, self.current = config, request, [], None
        self.engine = None

    def training_start(self, segment):
        if self.current is not None:
            raise ValueError('unfinished original training segment')
        self.current = {'neural': [], 'behavior': [], 'condition': None}

    def train(self, row):
        condition = self.config['condition_map'][row['condition']]
        if type(condition) is not int:
            raise ValueError('native condition identity must be original integer index')
        if self.current['condition'] is not None and condition != self.current['condition']:
            raise ValueError('one source condition per original segment')
        self.current['condition'] = condition
        self.current['neural'].append(row['neural'])
        behavior = []
        for selection in self.config['behavior_columns']:
            if set(selection) != {'field','column'} or selection['field'] not in ('behavior','auxiliary'):
                raise ValueError('explicit original Z column mapping')
            if type(selection['column']) is not int or selection['column'] < 0:
                raise ValueError('native behavior column index')
            behavior.append(row[selection['field']][selection['column']])
        if not behavior:
            raise ValueError('native behavior channels required')
        self.current['behavior'].append(behavior)

    def training_end(self):
        if self.current is None or not self.current['neural']:
            raise ValueError('complete nonempty original training segment')
        self.training.append(self.current); self.current = None

    def fit(self):
        if self.current is not None or not self.training:
            raise ValueError('complete original training support')
        import matlab.engine
        self.engine = matlab.engine.start_matlab('-nodesktop -nosplash')
        # The entire context tree is an independently pinned reference-only
        # capture. Native source and bridges are placed there before admission.
        self.engine.addpath(self.engine.genpath('/context'), nargout=0)
        request = dict(self.request, segments=self.training)
        self.engine.mint_stream_entry('fit', json.dumps(request, allow_nan=False), nargout=1)
        self.training.clear()

    def start_trial(self, opaque_trial):
        self.prefix = []

    def history(self, neural):
        self.prefix.append(neural)

    def predict(self, neural):
        self.prefix.append(neural)
        answer = self.engine.mint_stream_entry('predict_causal_prefix',
                    json.dumps({'neural_prefix':self.prefix}, allow_nan=False), nargout=1)
        value = json.loads(answer)
        return [float(x) for x in value] if isinstance(value,list) else [float(value)]

    def close(self):
        if self.engine is not None:
            self.engine.quit(); self.engine = None


def create(case, config):
    return NativeMint(case, config)
