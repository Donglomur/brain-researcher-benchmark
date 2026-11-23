"""Figure 6B endpoint for the existing protected full40 programme.

Consumes its already protected grade result, preparation and collection receipts;
never reads labels, prediction arrays, candidate models or a source archive.
This endpoint check is not scientific admission or an inference procedure.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from common import TASK, descriptor, need
from prepare import ARCHIVE, SESSION, VERSIONS
from author_replay import AUTHOR_BYTES, AUTHOR_SHA256
from support import REFERENCES, animal_description, equal_sessions, phases, validate_prepared

PUBLISHED = 0.7271
ROUNDING_TOLERANCE = 0.00005
MAX_RECEIPT_BYTES = 8 * 1024 * 1024
METHODS = ('A', 'B', *REFERENCES)


def read_pinned_json(path, sha256):
    """Read only a bounded metadata receipt at an independently expected digest."""
    path = Path(path)
    need(path.is_file() and not path.is_symlink(), 'ordinary metadata receipt')
    with path.open('rb') as stream:
        raw = stream.read(MAX_RECEIPT_BYTES + 1)
    need(len(raw) <= MAX_RECEIPT_BYTES, 'metadata receipt capacity')
    need(hashlib.sha256(raw).hexdigest() == sha256, 'expected receipt digest')
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'unique JSON keys')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value))), {
                          'bytes': len(raw), 'sha256': sha256}


def _close(a, b, message):
    need(type(a) in (int, float) and math.isfinite(a)
         and abs(a - b) <= 1e-12, message)


def _pooled_score(row, source):
    """Balanced accuracy from integer pooled confusion, never fold averaging."""
    c = row['confusion_counts']
    need(type(c) is list and len(c) == 2
         and all(type(r) is list and len(r) == 2 for r in c)
         and all(type(v) is int and v >= 0 for r in c for v in r),
         '2x2 nonnegative integer pooled confusion counts')
    counts = [sum(c[0]), sum(c[1])]
    expected = [source['source_HW_counts']['avoidance'], source['source_HW_counts']['escape']]
    need(all(type(n) is int and n > 0 for n in expected)
         and counts == expected == row['class_counts']
         and row['rows'] == source['rows'] == sum(counts),
         'all original HW rows/classes represented in every method')
    recalls = [c[i][i] / counts[i] for i in range(2)]
    score = sum(recalls) / 2
    _close(row['balanced_accuracy'], score, 'BA agrees with pooled confusion')
    _close(row['avoidance_recall'], recalls[0], 'avoidance recall agrees with confusion')
    _close(row['escape_recall'], recalls[1], 'escape recall agrees with confusion')
    return score


def _source_panel(bundle, result, collection):
    records = validate_prepared(bundle)  # Reuse original complete-fold checks.
    need(descriptor(bundle['archive']) == ARCHIVE, 'exact official processed archive')
    need(result['schema'] == 'foraging_full40_results_v1' and result['task_id'] == TASK
         and result['sessions'] == 40 and result['outer_folds'] == 200
         and result['producer_phases'] == 1320, 'complete original grade result')
    need(collection['schema'] == 'foraging_collection_v1' and collection['task_id'] == TASK
         and result['source'] == bundle['source'] == collection['source']
         and collection['all1320closed'] is True
         and collection['private_grade_called'] is False, 'same protected source and closed collection')
    expected = phases(records, collection['model_cap_bytes'])
    need(collection['contexts'] == expected
         and [phase['context'] for phase in collection['phases']] == expected,
         'complete original 1320-phase session/fold identity chain')
    # The collection is a large receipt. Full external lifecycle/custody review
    # remains grade.py's responsibility, not something this summary can replace.
    need(result['released_features_transductive'] is True
         and result['causal_or_new_animal_claim'] is False, 'original retrospective task')
    scientific = [r['name'] for r in bundle['archive_inventory']
                  if r['disposition'] == 'full_original_classification_MAT']
    need(len(scientific) == len(set(scientific)) == 40
         and set(scientific) == {r['source_member'] for r in records},
         'exact complete archive scientific roster, not forty arbitrary records')
    for r in records:
        match = SESSION.fullmatch(Path(r['source_member']).name)
        need(match is not None and match.group(1) == r['source_session_token']
             and hashlib.sha256(r['source_member'].encode()).hexdigest()[:24] == r['session_id'],
             'original member/token/session digest joins')
        need(r['window_seconds'] == [-1, 1] and r['bin_seconds'] == 0.05
             and r['features'] == 40 * r['unit_blocks'] and r['clip'] == [-5, 5]
             and r['native_fold_seed'] == 622
             and r['upstream_whole_session_normalized'] is True
             and r['private_row_maps_candidate_visible'] is False,
             'source feature/window/fold/order recipe retained')
    return records


def score_endpoint(result, bundle, collection, animal_mapping=None):
    """Recheck the protected programme's full-panel endpoint without new fits.

    Inputs must come from the original trusted operator. Self-authored receipts
    cannot establish authenticity; CLI hashes bind a selected result chain only.
    """
    records = _source_panel(bundle, result, collection)
    sids = {r['session_id'] for r in records}
    scores = {}
    panels = result['hidden_label_improvement']
    need(set(panels) == set(METHODS), 'both candidates and all separate controls')
    for method in METHODS:
        panel = panels[method]
        need(set(panel['sessions']) == sids, 'complete identical session roster for ' + method)
        scores[method] = {r['session_id']: _pooled_score(panel['sessions'][r['session_id']], r)
                          for r in records}
        _close(panel['equal_session']['balanced_accuracy'], equal_sessions(scores[method], records),
               'equal-session aggregate agrees with every pooled session for ' + method)
    # Both operator paths use reference_math's independent BNB equations, not
    # the authors' sklearn execution. Check their same-fold consistency only.
    # Probability-reconstruction fidelity is not read.
    native = result['native_real_and_separate_seeded_control']['operator']
    need(set(native['sessions']) == sids, 'complete operator native session roster')
    operator_bnb = {}
    for r in records:
        sid = r['session_id']
        operator_bnb[sid] = _pooled_score(native['sessions'][sid][0], r)
        _close(scores['bnb'][sid], operator_bnb[sid], 'paired native and held-out BNB endpoint agreement')
    baseline = equal_sessions(operator_bnb, records)
    _close(native['real']['balanced_accuracy'], baseline, 'complete native operator BNB aggregate')
    rounding_match = abs(baseline - PUBLISHED) <= ROUNDING_TOLERANCE + 1e-15
    summaries = {}
    for method in METHODS:
        mean = equal_sessions(scores[method], records)
        differences = {sid: scores[method][sid] - operator_bnb[sid] for sid in sids}
        # Existing programme's rat summaries are descriptive and explicitly
        # different from the original equal-session primary point estimate.
        description = animal_description(differences, records, animal_mapping)
        summaries[method] = {
            'equal_session_balanced_accuracy': mean,
            'difference_from_operator_bnb': equal_sessions(differences, records),
            'difference_from_published': mean - PUBLISHED,
            'sessions_above_operator_bnb': sum(d > 0 for d in differences.values()),
            'sessions_below_operator_bnb': sum(d < 0 for d in differences.values()),
            'sessions_tied_with_operator_bnb': sum(d == 0 for d in differences.values()),
            'rat_descriptive_stability': description,
        }
    return {
        'schema': 'foraging_figure6b_endpoint_check_v1', 'task_id': TASK,
        'sessions': 40, 'outer_folds': 200,
        'metric': 'equal-session mean of pooled OOF balanced accuracy; escape probability >=0.5',
        'author_replay': None, 'operator_bnb_reconstruction': baseline, 'published': PUBLISHED,
        'rounding_check': {'comparator': 'operator_bnb_reconstruction',
                           'absolute_tolerance': ROUNDING_TOLERANCE,
                           'within_predeclared_rounding_interval': rounding_match,
                           'source_equivalence_established_by_this_check': False},
        'methods': summaries,
        'uncertainty': {'population_interval': None, 'independent_unit': 'rat',
                        'reason': 'Source-authenticated rat joins and a predeclared valid paired procedure remain required.'},
        'meaningful_effect': None, 'paper_win': None, 'improvement_ready': False,
        'interpretation': 'Numerical endpoint check only. Source/fold/environment admission, '
                          'pre-score candidate freeze/custody, meaningful effect and paired uncertainty '
                          'are external requirements. A rounding match alone is not author reproduction.',
        'operator_bnb_outside_rounding_interval': not rounding_match,
        'author_calibration_established': False,
        'released_features_transductive': True, 'new_scientific_improvement_claims': 0,
    }


def compare_author_replay(result, bundle, collection, component, replay_result,
                          prepared_pin, component_pin, animal_mapping=None):
    """Join a complete source-API replay to the same protected preparation.

    Pins identify operator-selected metadata bytes; they do not establish source
    custody, execution, array correctness or comparator competence. The CLI
    obtains the expected pins from its independently selected receipt inputs.
    No probability-vector paths are opened by this comparison.
    """
    output = score_endpoint(result, bundle, collection, animal_mapping)
    records = bundle['records']
    ids = {r['session_id'] for r in records}
    author_pin = {'bytes': AUTHOR_BYTES, 'sha256': AUTHOR_SHA256}
    need(replay_result['schema'] == 'foraging_source_api_cli_result_v1'
         and replay_result['task_id'] == TASK
         and replay_result['status'] == 'complete_author_api_component_only'
         and type(replay_result['complete_sessions']) is int
         and replay_result['complete_sessions'] == 40
         and type(replay_result['completed_real_fits']) is int
         and replay_result['completed_real_fits'] == 200,
         'complete original40-session200-fit source-API result')
    need(descriptor(replay_result['prepared']) == descriptor(prepared_pin)
         and descriptor(replay_result['author_component']) == descriptor(component_pin)
         and replay_result['author_component']['file'] == 'AUTHOR_COMPONENT.json'
         and descriptor(replay_result['author_source']) == author_pin,
         'same preparation and exact source-API component/source descriptor chain')
    need(component['schema'] == 'foraging_source_api_real_branch_v1'
         and component['task_id'] == TASK
         and type(component['completed_real_fits']) is int
         and component['completed_real_fits'] == 200
         and descriptor(component['source_classifier']) == author_pin
         and component['runtime_versions'] == VERSIONS,
         'original author branch and adopted runtime report')
    need(replay_result['paper_reproduced'] is None
         and replay_result['paper_win'] is None
         and replay_result['overall_benchmark_ready'] is False
         and component['paper_reproduced'] is None
         and component['paper_win'] is None
         and component['improvement_ready'] is False
         and all(component[name] is False for name in (
             'unchanged_whole_script_execution', 'historical_environment_equivalence',
             'source_shuffle_companions_executed', 'permutation_importance_executed',
             'source_or_custody_qualification_established')),
         'source-API component retains its scientific qualification limits')
    need(set(component['sessions']) == ids
         and set(replay_result['probabilities']) == ids,
         'complete same40-session source-API metadata roster')
    author_scores = {}
    numeric_bytes = 0
    for source in records:
        sid = source['session_id']
        row = component['sessions'][sid]
        need(row['source_member'] == source['source_member']
             and type(row['fits']) is int and row['fits'] == 5,
             'source member and all five fits for every original session')
        author_scores[sid] = _pooled_score(row, source)
        vector = replay_result['probabilities'][sid]
        pin = descriptor(vector)
        need(vector['file'] == sid + '.f64' and vector['dtype'] == '<f8'
             and type(vector['rows']) is int and vector['rows'] == source['rows']
             and pin['bytes'] == 8 * source['rows'],
             'complete original-row source-API probability descriptor')
        numeric_bytes += pin['bytes']
    need(type(component['output_numeric_bytes']) is int
         and component['output_numeric_bytes'] == numeric_bytes
         and type(replay_result['numeric_output_bytes']) is int
         and replay_result['numeric_output_bytes'] == numeric_bytes,
         'complete source-API numerical extent metadata')
    mean = equal_sessions(author_scores, records)
    _close(component['equal_session_balanced_accuracy'], mean,
           'source-API equal-session aggregate agrees with pooled confusion')
    output['author_replay'] = mean
    output['author_replay_scope'] = {
        'kind': 'source_API_real_label_component_metadata',
        'prepared': descriptor(prepared_pin), 'component': descriptor(component_pin),
        'source_classifier': author_pin, 'runtime_versions': dict(VERSIONS),
        'probability_vectors_reopened': False,
        'source_or_execution_authenticated_by_this_check': False,
        'complete_paper_reproduction': False,
    }
    output['author_rounding_check'] = {
        'comparator': 'source_API_real_label_component',
        'absolute_tolerance': ROUNDING_TOLERANCE,
        'within_predeclared_rounding_interval':
            abs(mean - PUBLISHED) <= ROUNDING_TOLERANCE + 1e-15,
        'source_equivalence_established_by_this_check': False,
    }
    for method in METHODS:
        panel = result['hidden_label_improvement'][method]['sessions']
        differences = {sid: panel[sid]['balanced_accuracy'] - author_scores[sid]
                       for sid in ids}
        output['methods'][method]['difference_from_author_api_replay'] = equal_sessions(
            differences, records)
        output['methods'][method]['author_api_rat_descriptive_stability'] = animal_description(
            differences, records, animal_mapping)
    output['interpretation'] += (
        ' The optional source-API comparison checks the bound report arithmetic and '
        'complete same-preparation metadata only. Its arrays, execution, custody, '
        'shuffle companions and strongest-comparator qualification remain external.')
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('result', 'prepared', 'collection'):
        parser.add_argument('--' + name, required=True)
        parser.add_argument('--' + name + '-sha256', required=True)
    parser.add_argument('--animal-mapping')
    parser.add_argument('--animal-mapping-sha256')
    parser.add_argument('--author-component')
    parser.add_argument('--author-component-sha256')
    parser.add_argument('--author-result')
    parser.add_argument('--author-result-sha256')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    loaded = {name: read_pinned_json(getattr(args, name), getattr(args, name + '_sha256'))
              for name in ('result', 'prepared', 'collection')}
    result, bundle, collection = (loaded[name][0] for name in ('result', 'prepared', 'collection'))
    need(descriptor(result['collection']) == loaded['collection'][1]
         and descriptor(collection['prepared']) == loaded['prepared'][1],
         'exact result-to-collection-to-prepared digest chain')
    need(bool(args.animal_mapping) == bool(args.animal_mapping_sha256), 'mapping and digest together')
    mapping = None if not args.animal_mapping else read_pinned_json(
        args.animal_mapping, args.animal_mapping_sha256)[0]
    author_arguments = (args.author_component, args.author_component_sha256,
                        args.author_result, args.author_result_sha256)
    need(not any(author_arguments) or all(author_arguments),
         'author component, result and both expected digests together')
    if all(author_arguments):
        component, component_pin = read_pinned_json(
            args.author_component, args.author_component_sha256)
        replay_result, result_pin = read_pinned_json(args.author_result, args.author_result_sha256)
        output = compare_author_replay(result, bundle, collection, component, replay_result,
                                      loaded['prepared'][1], component_pin, mapping)
        loaded['author_component'] = (component, component_pin)
        loaded['author_result'] = (replay_result, result_pin)
    else:
        output = score_endpoint(result, bundle, collection, mapping)
    output['inputs'] = {name: loaded[name][1] for name in loaded}
    if args.animal_mapping:
        output['animal_mapping_sha256'] = args.animal_mapping_sha256
    # Explicit operator path: report carries per-method scores and must remain
    # evaluator-only until the episode's feedback policy allows its release.
    with Path(args.output).open('x', encoding='utf-8') as stream:
        json.dump(output, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


if __name__ == '__main__':
    main()
