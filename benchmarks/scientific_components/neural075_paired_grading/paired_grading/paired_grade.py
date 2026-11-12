"""Inactive trusted-host complete-pair grading successor for NEURAL-075.

The old producer remains unscored. This entry requires independent explicit
operator authority and validates the complete closed pair before any target
read. It does not launch candidates, supply author code, fit a decoder or confer
scientific/native qualification. Direct internal calls are a trusted-host API,
not a sandbox against arbitrary host Python.
"""
from dataclasses import dataclass
import math
from pathlib import Path
import time

from closed_pair import FileReader, _functions, capture_closed_pair, encoded, need, parse, pin
from paired_contrasts import compare_results
from pinned_scorer import load_scorer

PEOPLE = tuple('Subject' + str(i) for i in range(1, 6))
ARMS = ('neural', 'no_neural', 'training_permuted')
PHASES = ('imagery', 'perception')
ROWS = {'imagery': 500, 'perception': 1750}
CASES = tuple(f'{p}/{a}/{t}' for p in PEOPLE for a in ARMS for t in PHASES)


@dataclass
class Budget:
    """Explicit interface byte ledger; not an OS/NumPy memory traffic meter."""
    max_read_bytes: int
    max_write_bytes: int
    deadline: float
    read_bytes: int = 0
    write_bytes: int = 0

    def __post_init__(self):
        need(type(self.max_read_bytes) is int and self.max_read_bytes > 0 and
             type(self.max_write_bytes) is int and self.max_write_bytes > 0 and
             type(self.deadline) in (float, int) and math.isfinite(self.deadline) and
             self.deadline > time.monotonic(), 'Concrete positive paired-grading resource operands')

    def tick(self):
        need(time.monotonic() < self.deadline, 'Paired-grading deadline')

    def read(self, extent, label='logical input'):
        self.tick()
        need(type(extent) is int and extent >= 0 and self.read_bytes + extent <= self.max_read_bytes,
             'Paired-grading read budget: ' + label)
        self.read_bytes += extent

    def write(self, extent, label='logical output'):
        self.tick()
        need(type(extent) is int and extent >= 0 and self.write_bytes + extent <= self.max_write_bytes,
             'Paired-grading write budget: ' + label)
        self.write_bytes += extent


def _design(design_raw, pair, scorer):
    d = parse(design_raw)
    summary = parse(pair.closure_summary)
    need(pin(design_raw) == summary['design'], 'Exact producer-bound operator design')
    need(d['protocol'] == scorer.VERSION and d['people'] == list(PEOPLE) and
         type(d['cases']) is list and len(d['cases']) == 10 and
         d['roi'] == 'ROI_VC' and d['feature'] == 'cnn7' and d['n_units'] == 1000,
         'Complete unchanged person/feature scope')
    expected = [(p, t) for p in PEOPLE for t in PHASES]
    need([(r['person'], r['phase']) for r in d['cases']] == expected, 'Exact ordered ten target supports')
    rows = {}
    for row in d['cases']:
        key = row['person'], row['phase']
        need(type(row['trial_ids']) is list and len(row['trial_ids']) == ROWS[row['phase']],
             'Original full phase support')
        gold = row['gold']
        need(type(gold) is dict and set(gold) == {'path', 'bytes', 'sha256'} and
             type(gold['path']) is str and Path(gold['path']).name == gold['path'] and
             gold['path'] not in ('', '.', '..') and '\\' not in gold['path'], 'Flat bound target descriptor')
        from closed_pair import descriptor
        descriptor({k: gold[k] for k in ('bytes', 'sha256')}, 2**20)
        rows[key] = row
    need(len({r['gold']['path'] for r in rows.values()}) == 10, 'Ten distinct target bodies')
    return d, rows


def grade_verified_pair(pair, enclosing_observation, design_read, private_read, scorer, budget):
    """Grade an already captured/verified complete producer in trusted host code.

    This is also the actual numerical integration seam for explicit invented
    fixtures. It does not authenticate a freely constructed ClosedPair by its
    Python type; production callers must use grade_selected below. No result is
    returned between A and B. The protected reader receives only ten exact gold
    descriptors after all sixty score matrices have passed original admission.
    """
    need(tuple((r.access, r.case) for r in pair.cases) == tuple((a, c) for a in ('A', 'B') for c in CASES),
         'Complete ordered sixty captured cases')
    closure = parse(pair.closure_summary)
    need(type(enclosing_observation) is dict and set(enclosing_observation) == {'child', 'returned'} and
         enclosing_observation['returned'] == {'status': 'complete_unscored',
                                               'completion': closure['complete'], 'outputs': 60},
         'Separate enclosing operator returned exact unscored complete pair')
    # These functions were source-authenticated during capture; no candidate
    # imports and no invented producer-owned root receipt are introduced.
    invoke_source = dict(pair.snapshot.bodies)[pair.snapshot.root + '/runs/A/00/source/invoke.py']
    _functions(invoke_source, {'need', 'child_ok'}, {}).child_ok(enclosing_observation['child'])
    design_pin = closure['design']
    outputs = {'A': {}, 'B': {}}
    contexts = {'A': {}, 'B': {}}
    for row in pair.cases:
        budget.read(len(row.prediction) + len(row.context), 'captured prediction/context parse')
        output, context = parse(row.prediction), parse(row.context)
        need(output['context_sha256'] == pin(row.context)['sha256'] and
             context['design_sha256'] == design_pin['sha256'] and
             context['access_condition'] == row.access and context['case_id'] == row.case,
             'Exact captured context/design/access/output identity')
        p, arm, phase = row.case.split('/')
        need(context['person'] == p and context['arm'] == arm and context['phase'] == phase and
             context['n_units'] == 1000, 'Full common design support and unchanged features')
        outputs[row.access][row.case] = output
        contexts[row.access][row.case] = context
    # Real original admission of ALL 60 matrices; no private reader exists in
    # this loop. Arrays are released one at a time after admission, not retained.
    for access in ('A', 'B'):
        for case in CASES:
            extent = ROWS[case.rsplit('/', 1)[1]] * 50 * 8
            budget.read(extent, 'all-sixty numeric admission input')
            budget.write(extent, 'all-sixty float64 admission array')
            admitted = scorer.admit(outputs[access][case], contexts[access][case])
            need(admitted.shape == (ROWS[case.rsplit('/', 1)[1]], 50), 'Full real admitted array')
            del admitted
    # Even the operator design is opened only after all sixty original numeric
    # admissions. Contexts already bind its selected hash; its actual support is
    # now joined before the first gold body is opened.
    design_raw = design_read()
    need(type(design_raw) is bytes, 'Immutable captured operator design')
    budget.read(len(design_raw), 'operator design parse')
    design, support = _design(design_raw, pair, scorer)
    for access in ('A', 'B'):
        for case in CASES:
            context = contexts[access][case]
            source = support[(context['person'], context['phase'])]
            need(context['trial_ids'] == source['trial_ids'] and context['categories'] == design['categories'],
                 'Exact paired design support before gold')
    cache = {}
    private_callbacks = 0

    def gold(person, phase):
        nonlocal private_callbacks
        private_callbacks += 1
        key = person, phase
        if key not in cache:
            row = support[key]
            descriptor = row['gold']
            raw = private_read(descriptor)
            need(type(raw) is bytes and pin(raw) == {k: descriptor[k] for k in ('bytes', 'sha256')},
                 'Protected bytes match selected exact descriptor')
            budget.read(len(raw), 'protected NPZ decode')
            # Decoder is the unchanged pinned task decoder; no filesystem path
            # is passed to NumPy and no object/pickle arrays are permitted.
            values = scorer.arrays(raw, ['labels', 'source_rows'], 2**20)
            labels, source_rows = values['labels'], values['source_rows']
            n = ROWS[phase]
            need(labels.shape == source_rows.shape == (n,) and labels.dtype.kind in 'iu' and
                 source_rows.dtype.kind in 'iu' and scorer.np.all((labels >= 0) & (labels < 50)) and
                 len(scorer.np.unique(source_rows)) == n and scorer.np.all(source_rows >= 0) and
                 all(scorer.np.sum(labels == i) == scorer.REPEATS[phase] for i in range(50)),
                 'Complete labels, source rows and category repeats')
            budget.write(labels.nbytes + source_rows.nbytes, 'decoded protected primitive arrays')
            labels.setflags(write=False)
            cache[key] = labels
        budget.read(cache[key].nbytes, 'original scorer protected callback')
        return cache[key]

    grades = {}
    for access in ('A', 'B'):
        # Original evaluate re-admits all30, creates its own float64 matrices,
        # and calls summarize unchanged. Reserve those interface arrays before
        # the call; internal NumPy temporaries are not byte-metered by Python.
        extent = sum(ROWS[c.rsplit('/', 1)[1]] * 50 * 8 for c in CASES)
        budget.read(extent, 'unchanged evaluate numeric input')
        budget.write(extent, 'unchanged evaluate admitted float64 arrays')
        # Logical selected-score copies, per-category means and stacked arrays
        # created by original summarize. This is conservative boundary charging,
        # not measurement of every internal NumPy scalar/mask temporary.
        category_extent = extent + 2 * 30 * 50 * 50 * 8
        budget.read(category_extent, 'original category score-vector reduction buffers')
        budget.write(category_extent, 'original category selected/mean/stack buffers')
        grades[access] = scorer.evaluate(outputs[access], contexts[access], design, gold)
    need(len(cache) == 10 and private_callbacks == 20, 'Original complete ten-support reuse across A/B')
    report = compare_results(grades['A'], grades['B'])
    result = {'schema': 'neural075_authorized_closed_pair_grade_v1',
              'producer_closure': parse(pair.closure_summary),
              'design': design_pin, 'scorer_sources': scorer.source_pins,
              'complete_cases_admitted_before_private_read': 60,
              'score_entries_admitted': 3375000, 'private_underlying_reads': 10,
              'original_scorer_private_callbacks': 20, 'comparison': report,
              'old_producer_private_scoring_calls': 0,
              'runtime_qualified': False, 'scientific_qualification_added': False,
              'scientific_tasks': 1, 'new_assignment_count': 0, 'binary_success': None}
    body = encoded(result)
    need(len(body) <= 2**20, 'Bounded aggregate paired result')
    budget.write(len(body), 'paired result serialization')
    return result


def grade_selected(repository, producer_root, complete_pin, commits, prepared_root,
                   enclosing_observation, authority, budget):
    """Future operator entry; no CLI or default approval is supplied.

    `authority.require_neural075_paired_grading(selection)` is trusted-host code
    which must raise unless the exact operation is explicitly authorized. It
    must return None on success. Merely creating JSON/setting a field does not
    authorize grading. Candidates never supply this object or the selected paths.
    """
    selection = {'schema': 'neural075_separate_paired_grading_selection_v1',
                 'repository': str(Path(repository).absolute()),
                 'producer_root': str(Path(producer_root).absolute()),
                 'complete': complete_pin, 'commits': commits,
                 'enclosing_observation': pin(encoded(enclosing_observation)),
                 'prepared_root': str(Path(prepared_root).absolute()),
                 'read_limit': budget.max_read_bytes, 'write_limit': budget.max_write_bytes,
                 'deadline': budget.deadline}
    need(authority.require_neural075_paired_grading(selection) is None, 'Explicit trusted grading authority')
    pair = capture_closed_pair(repository, producer_root, complete_pin, commits, budget)
    reader = FileReader(budget)
    scorer = load_scorer(repository, reader)
    expected = parse(pair.closure_summary)['design']
    def design_read():
        return reader.read(str(Path(prepared_root) / 'OPERATOR_DESIGN.json'), expected, 2**20)

    def protected(descriptor):
        return reader.read(str(Path(prepared_root) / descriptor['path']),
                           {k: descriptor[k] for k in ('bytes', 'sha256')}, 2**20)

    return grade_verified_pair(pair, enclosing_observation, design_read, protected, scorer, budget)
