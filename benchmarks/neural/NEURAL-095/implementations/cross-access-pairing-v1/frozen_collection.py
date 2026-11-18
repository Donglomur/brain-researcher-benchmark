"""Two original frozen Cells; a closed public collection, never an evaluator.

This module is injected from captured source in a separately reviewed owner
assembly. The original four-cell Study and its scoring path remain untouched.
"""
import time

MODE = 'frozen_pair_ungraded/v1'
VIEWS = ('cue_only', 'neural')
STATUS = 'frozen_pair_outputs_collected_ungraded'


class FrozenPairCollection:
    def __init__(self, *, api, source, method, case_ids, limits, reservations,
                 tool_ids, backend_factory, comparison_id, seal, clock_us=None):
        api.need(type(source) is bytes and 0 < len(source) <= 65536,
                 'bounded frozen actor source')
        api.need(type(method) is bytes and 0 < len(method) <= 32768,
                 'bounded common method document')
        source.decode('utf-8'); method.decode('utf-8')
        api.submission_npz(case_ids, (0.0,) * 258)
        api.need(isinstance(limits, api.Limits) and len(tool_ids) == 1,
                 'one frozen numerical programme and original limits')
        self.api, self.source, self.method = api, source, method
        self.ids, self.limits, self.reservations = case_ids, limits, reservations
        self.tools, self.factory, self.comparison = tool_ids, backend_factory, comparison_id
        self.seal = seal
        self.manifest = api.load_manifest()
        self.clock = clock_us or (lambda: time.monotonic_ns() // 1000)
        self.state, self.cells, self.outputs, self.records = 'new', {}, {}, {}

    def run(self):
        api = self.api
        api.need(self.state == 'new', 'ungraded collection is single-use')
        self.state = 'producing'
        backends, sessions = [], set()
        def admission(session):
            api.need(session not in sessions, 'fresh separate frozen actor session')
            sessions.add(session)
        try:
            for view in VIEWS:
                backend = self.factory('frozen_program', view)
                api.need(all(backend is not old for old in backends), 'fresh backend per view')
                backends.append(backend)
                cell = api.Cell(mode='frozen_program', view=view, source=self.source,
                    method=self.method, case_ids=self.ids, limits=self.limits,
                    reservations=self.reservations, tool_ids=self.tools, backend=backend,
                    comparison_id=self.comparison, manifest=self.manifest,
                    clock_us=self.clock, on_admission=admission)
                self.cells[view] = cell
                body, record = cell.run()
                api.need(cell.closed and cell.state == 'committed', 'original Cell has closed before collection')
                self.outputs[view], self.records[view] = body, record
            pair = {'schema': 'dmfc-frozen-pair-ungraded-collection/v1', 'mode': MODE,
                'comparison_id': self.comparison, 'case_count_per_cell': 258,
                'training_count': 748, 'case_ids': list(self.ids),
                'limits_sha256': self.limits.identity(),
                'delivery_manifest_sha256': api.MANIFEST['sha256'],
                'cells': [self.records[v] for v in VIEWS],
                'policy': 'single_frozen_fit_batch/v1',
                'private_grades_so_far': 0, 'private_target_reads': 0,
                'private_reference_reads': 0, 'numerical_units_expected': 6}
            body = api.encode(pair)
            api.need(self.seal(pair) == api.digest(body), 'durable public two-cell commitment')
            self.state = 'complete'
            return {'status': STATUS, 'mode': MODE, 'pair_sha256': api.digest(body),
                'private_grades_so_far': 0, 'operational_qualification_claimed': False}
        except BaseException:
            self.state = 'failed'
            raise
