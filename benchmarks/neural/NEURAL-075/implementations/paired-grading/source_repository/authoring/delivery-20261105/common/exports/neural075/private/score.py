"""Artifact grader; producer closure/isolation must be supplied externally."""
import argparse
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'public'))
import numpy as np
from delivery_io import need, read, decode, exact, pin, check_pin, resolve, put
from array_io import fresh_output, arrays
from protocol import VERSION, PEOPLE, ARMS, PHASES, ROWS, REPEATS, SCORE_CAP, case_ids
from scorer_core import summarize


def admit(output, context):
    need(context['person'] in PEOPLE and context['arm'] in ARMS and context['phase'] in PHASES and
         context['case_id'] == '/'.join(context[k] for k in ('person', 'arm', 'phase')), 'Exact person/arm/phase identity')
    ids = context['trial_ids']; cats = context['categories']
    need(type(ids) is list and len(ids) == ROWS[context['phase']] and len(set(ids)) == len(ids) and
         all(type(x) is str and re.fullmatch('q[0-9a-f]{24}', x) for x in ids), 'Exact unique opaque query IDs')
    need(type(cats) is list and len(cats) == len(set(cats)) == 50 and
         all(type(x) is str and re.fullmatch('n[0-9]{8}', x) for x in cats), 'Exact50 unique category identities')
    exact(output, ['protocol', 'case_id', 'context_sha256', 'categories', 'trial_ids', 'scores'])
    need(output['protocol'] == VERSION and output['case_id'] == context['case_id'] and
         output['categories'] == context['categories'] and output['trial_ids'] == context['trial_ids'], 'Exact context/candidate order')
    rows = output['scores']
    need(type(rows) is list and len(rows) == ROWS[context['phase']] and
         all(type(r) is list and len(r) == 50 and all(type(v) in (int, float) and
             np.isfinite(v) and abs(v) <= SCORE_CAP for v in r) for r in rows), 'Complete finite bounded score matrix')
    return np.asarray(rows, dtype=np.float64)


def evaluate(submitted, contexts, design, private_loader):
    # Every condition must pass BEFORE the first private target read.
    need(list(submitted) == case_ids() and list(contexts) == case_ids(), 'Complete ordered30-case panel')
    admitted = {key: admit(submitted[key], contexts[key]) for key in case_ids()}
    by_case = {}
    for person in PEOPLE:
        for phase in PHASES:
            targets = private_loader(person, phase)
            for arm in ARMS:
                key = f'{person}/{arm}/{phase}'
                by_case[key] = summarize(admitted[key], targets, REPEATS[phase])
    aggregate = {}
    for phase in PHASES:
        aggregate[phase] = {}
        for arm in ARMS:
            cells = [by_case[f'{p}/{arm}/{phase}'] for p in PEOPLE]
            aggregate[phase][arm] = {level: {metric: float(np.mean([c[level][metric] for c in cells]))
                                          for metric in cells[0][level]} for level in cells[0]}
        aggregate[phase]['paired_neural_minus_controls'] = {
            control: {p: by_case[f'{p}/neural/{phase}']['trial']['top1_tie_fraction'] -
                         by_case[f'{p}/{control}/{phase}']['trial']['top1_tie_fraction'] for p in PEOPLE}
            for control in ('no_neural', 'training_permuted')}
    return {'protocol': VERSION, 'n_biological_people': 5, 'n_cases': 30,
            'primary': aggregate['imagery']['neural']['trial']['top1_tie_fraction'],
            'primary_definition': 'Equal-person mean50-way imagery trial Top1; exact ties split credit',
            'per_case': by_case, 'participant_macro': aggregate,
            'binary_success': None, 'execution_attested': False,
            'scientific_limits': ['Public development exposure', 'Instructed category, not verified imagined photograph',
                                  'Same-person native voxels; cue carryover and preprocessing remain',
                                  'Five biological units; no SOTA/full-paper/generalization claim']}


def main():
    p = argparse.ArgumentParser(); p.add_argument('--submission', required=True)
    p.add_argument('--contexts', required=True); p.add_argument('--context-index-sha256', required=True)
    p.add_argument('--prepared', required=True); p.add_argument('--design-sha256', required=True)
    p.add_argument('--output', required=True); a = p.parse_args()
    fresh_output(a.output)
    for s in (a.context_index_sha256, a.design_sha256): need(re.fullmatch('[0-9a-f]{64}', s), 'Root-bound identity')
    submission = Path(a.submission); contexts_root = Path(a.contexts); prepared = Path(a.prepared)
    collection = decode(read(submission / 'collection.json', 2**20))
    exact(collection, ['protocol', 'program', 'cases'])
    need(collection['protocol'] == VERSION and type(collection['cases']) is list and
         len(collection['cases']) == 30 and [r['case_id'] for r in collection['cases']] == case_ids(), 'Exact full collection')
    check_pin(collection['program'], 131072)
    raw_index = read(contexts_root / 'CONTEXTS.json', 2**20)
    need(pin(raw_index)['sha256'] == a.context_index_sha256, 'Trusted complete context index')
    index = decode(raw_index)
    need(index['protocol'] == VERSION and index['design_sha256'] == a.design_sha256 and
         [r['case_id'] for r in index['cases']] == case_ids(), 'Exact trusted case roster')
    contexts, submitted = {}, {}
    candidate_paths = set()
    for pred, ctx in zip(collection['cases'], index['cases']):
        exact(pred, ['case_id', 'path', 'bytes', 'sha256'])
        check_pin({k: pred[k] for k in ('bytes', 'sha256')}, 4 * 2**20)
        need(pred['path'] not in candidate_paths, 'Distinct candidate output files'); candidate_paths.add(pred['path'])
        raw_context = read(resolve(contexts_root, ctx['path']), 2**20,
                           {k: ctx[k] for k in ('bytes', 'sha256')})
        context = decode(raw_context)
        need(context['case_id'] == pred['case_id'] and context['design_sha256'] == a.design_sha256,
             'Context joins trusted design')
        need(index['access_condition'] in ('A', 'B') and context['access_condition'] == index['access_condition'],
             'No mixing supplied-access conditions')
        result = decode(read(resolve(submission, pred['path']), 4 * 2**20,
                             {k: pred[k] for k in ('bytes', 'sha256')}))
        need(result['context_sha256'] == pin(raw_context)['sha256'], 'Output joins exact frozen context')
        contexts[pred['case_id']] = context; submitted[pred['case_id']] = result
    raw_design = read(prepared / 'OPERATOR_DESIGN.json', 4 * 2**20)
    need(pin(raw_design)['sha256'] == a.design_sha256, 'Trusted operator design')
    design = decode(raw_design)
    need(design['protocol'] == VERSION and design['people'] == PEOPLE and len(design['cases']) == 10, 'Full operator design')
    def gold(person, phase):
        row = next(r for r in design['cases'] if r['person'] == person and r['phase'] == phase)
        for arm in ARMS:
            c = contexts[f'{person}/{arm}/{phase}']
            need(c['trial_ids'] == row['trial_ids'] and c['categories'] == design['categories'], 'Paired support/order')
        descriptor = row['gold']
        need(Path(descriptor['path']).name == descriptor['path'], 'Flat private target')
        body = read(prepared / descriptor['path'], 2**20, {k: descriptor[k] for k in ('bytes', 'sha256')})
        return arrays(body, ['labels', 'source_rows'], 2**20)['labels']
    result = evaluate(submitted, contexts, design, gold)
    result.update(design_sha256=a.design_sha256, context_index_sha256=a.context_index_sha256,
                  supplied_access_condition=index['access_condition'], submitted_program_as_declared=collection['program'])
    put(a.output, result, 2**20)


if __name__ == '__main__': main()
