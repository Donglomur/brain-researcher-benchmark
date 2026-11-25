"""Owner-only paired descriptive comparison of existing original-result exports.

No R, candidate program, estimator, scientific tolerance or success decision is
executed. Owner-selected reference bytes are not thereby scientifically qualified.
"""
import argparse
import csv
from fractions import Fraction
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat

TASK = 'PAPER-EXP-20261113-003'
CONTRACT_SHA = '57e738ebd79ecd07620a20dccccf7873c5cbf57aace29342cd842592099977a8'
IDS = ('quest_self', 'amy_quest', 'amy_self')
FILES = ('full120.json', 'row_lineage.json', 'table1/habit_associations.csv') + tuple(
    kind + '/' + contrast + '.json' for kind in ('dl', 'bayes') for contrast in IDS)
ARMS = {'reference': 'A', 'paper_data': 'A', 'paper_data_author_code': 'B'}
TABLE_COLUMNS = ('Model', 'r', '95% CIa', 'pa', 'k', 'N', 'tau', '95% CIb', 'Q', 'df', 'pb')
TABLE_MODELS = ('Rating-Amygdala', 'Rating-Questionnaires', 'Amygdala-Questionnaires')
FILE_LIMIT = 262144
REPORT_LIMIT = 16 * 1024 * 1024


def need(condition, code):
    if not condition:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        need(key not in out, 'duplicate_JSON_key')
        out[key] = value
    return out


def regular_read(path, limit):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts and
         not any(p.is_symlink() for p in (path, *path.parents)), 'regular_absolute_path')
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and info.st_size <= limit, 'bounded_regular_input')
        raw = stream.read(limit + 1)
    need(len(raw) <= limit, 'input_extent')
    return raw


def pinned_read(pin, limit=FILE_LIMIT):
    need(type(pin) is dict and set(pin) == {'path', 'bytes', 'sha256'}, 'input_pin_keys')
    need(type(pin['bytes']) is int and 0 < pin['bytes'] <= limit and
         type(pin['sha256']) is str and len(pin['sha256']) == 64, 'input_pin_extent')
    raw = regular_read(pin['path'], limit)
    need(len(raw) == pin['bytes'] and sha(raw) == pin['sha256'], 'input_pin_identity')
    return raw


def load_contract(implementations):
    path = Path(implementations) / 'nider-primary-companions-v1/companion_contract.py'
    raw = regular_read(path, FILE_LIMIT)
    need(sha(raw) == CONTRACT_SHA, 'companion_contract_identity')
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader('_nider_comparison_contract', loader=None))
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    base = module.load_predecessor()
    public = base.public_contract()
    decoder, validator = base.load_validator(public)
    return module, base, public, decoder, validator


def parse_table(raw):
    # This is the literal source outTable representation, not a recalculation of
    # its ambiguously named r column and not an alternative numeric score.
    rows = list(csv.reader(io.StringIO(raw.decode('utf-8'), newline=''), strict=True))
    need(len(rows) == 4 and tuple(rows[0]) == TABLE_COLUMNS and
         all(len(row) == len(TABLE_COLUMNS) for row in rows[1:]) and
         tuple(row[0] for row in rows[1:]) == TABLE_MODELS, 'original_Table1_shape_and_order')
    return rows[1:]


def validate_exports(raws, arm, loaded):
    contract, base, public, decoder, validator = loaded
    need(set(raws) == set(FILES), 'complete_export_file_set')
    full = base.validate_output(raws['full120.json'], arm, public)
    need(tuple(row['contrast'] for row in full['contrasts']) == IDS, 'source_contrast_order')
    documents = {name: decoder.decode_numeric_json(raw) for name, raw in raws.items() if name.endswith('.json')}
    ledger = documents['row_lineage.json']
    need(ledger['schema'] == 'nider_primary_native_row_lineage_v1' and
         ledger['task'] == TASK and ledger['workbook_sha256'] == full['workbook_sha256'] and
         len(ledger['contrasts']) == 3, 'complete_row_lineage_identity')
    cells, metadata = {}, {}
    for row, lineage in zip(full['contrasts'], ledger['contrasts']):
        contrast = row['contrast']
        model, subset, converted, n_column = contract.MODEL_BINDINGS[contrast]
        need(lineage['contrast'] == contrast and lineage['membership'] == row['membership'] and
             lineage['native_model'] == model and lineage['native_subset'] == subset and
             lineage['bayes_input_object'] == converted and lineage['dl_n_column'] == n_column and
             lineage['bayes_n_column'] == 'sample size quest', 'source_row_lineage_alignment')
        for key in ('membership', 'settings', 'tau_interval'):
            metadata[f'{contrast}/full120/{key}'] = row[key]
        for key in validator.FIELDS:
            cells[f'{contrast}/full120/{key}'] = row['fields'][key]
        forest = documents['dl/' + contrast + '.json']
        contract.check_forest_export(forest, row, model)
        for field, vector in forest['vectors'].items():
            prefix = f'{contrast}/forest/{field}'
            metadata[prefix] = {key: vector[key] for key in ('storage_type', 'names')}
            for position, (unit, cell) in enumerate(zip(row['membership'], vector['values'])):
                # Retain source lineage and position; never sort or join on a
                # display label, drop missing rows, or select a matching subset.
                key = prefix + f'/position={position}/source={unit["source_id"]}'
                cells[key] = cell
        bayes = documents['bayes/' + contrast + '.json']
        contract.check_bayes_export(bayes, contrast, model)
        for field in ('incl.BF', 'incl.prior', 'incl.posterior'):
            cells[f'{contrast}/bayes/inclusion/{field}'] = bayes['inclusion'][field]
        vectors = {'inclusion/' + field: bayes['inclusion'][field] for field in ('include', 'prior', 'posterior')}
        vectors.update({'models/' + field: value for field, value in bayes['model_vectors'].items()})
        for field, vector in vectors.items():
            prefix = f'{contrast}/bayes/{field}'
            metadata[prefix] = {key: vector[key] for key in ('storage_type', 'names')}
            for position, cell in enumerate(vector['values']):
                cells[prefix + f'/position={position}'] = cell
        matrix = bayes['pairwise_BF']
        prefix = f'{contrast}/bayes/pairwise_BF'
        metadata[prefix] = {key: value for key, value in matrix.items() if key != 'values_by_row'}
        for i, row_values in enumerate(matrix['values_by_row']):
            for j, cell in enumerate(row_values):
                cells[prefix + f'/row={i}/column={j}'] = cell
    expected = 120 + 8 * sum(len(row['membership']) for row in full['contrasts']) + 3 * 41
    need(len(cells) == expected, 'complete_numeric_export_coverage')
    return {'cells': cells, 'metadata': metadata, 'table': parse_table(raws['table1/habit_associations.csv']),
            'membership': {row['contrast']: row['membership'] for row in full['contrasts']},
            'workbook_sha256': full['workbook_sha256']}


def json_value(value):
    # Decimal-bearing metadata stays exact and distinguishable from text.
    from decimal import Decimal
    if isinstance(value, Decimal):
        return {'JSON_decimal': str(value)}
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    return value


def numeric_comparison(left, right):
    # All values have passed the existing strict validators. Fractions avoid
    # Decimal-context rounding, including cancellation and extreme exponents.
    out = {'left': json_value(left), 'right': json_value(right), 'left_minus_right': None}
    if left['state'] == right['state'] == 'finite':
        delta = Fraction(left['value']) - Fraction(right['value'])
        out.update(status='FINITE_EQUAL' if delta == 0 else 'FINITE_DIFFERENT',
                   left_minus_right={'numerator': str(delta.numerator), 'denominator': str(delta.denominator)})
    else:
        out['status'] = 'SAME_NONFINITE_STATE_UNSCORED' if left['state'] == right['state'] else 'STATE_DIFFERENCE'
    return out


def compare_pair(left, right):
    need(left['workbook_sha256'] == right['workbook_sha256'] and
         left['membership'] == right['membership'], 'same_complete_source_population_required')
    need(left['cells'].keys() == right['cells'].keys() and
         left['metadata'].keys() == right['metadata'].keys(), 'same_complete_export_support_required')
    cells = {key: numeric_comparison(value, right['cells'][key]) for key, value in left['cells'].items()}
    metadata = {key: {'equal': value == right['metadata'][key], 'left': json_value(value),
                     'right': json_value(right['metadata'][key])} for key, value in left['metadata'].items()}
    table = [{'model': model, 'column': column, 'left': left['table'][i][j],
              'right': right['table'][i][j], 'text_equal': left['table'][i][j] == right['table'][i][j]}
             for i, model in enumerate(TABLE_MODELS) for j, column in enumerate(TABLE_COLUMNS)]
    counts = {}
    for value in cells.values():
        counts[value['status']] = counts.get(value['status'], 0) + 1
    return {'numeric_cells': cells, 'numeric_cell_count': len(cells), 'numeric_status_counts': counts,
            'metadata': metadata, 'Table1_literal_cells': table,
            'numeric_aggregation_performed': False, 'scientific_pass_defined': False}


def compare_request(request, loaded):
    need(type(request) is dict and set(request) == {'schema', 'task', 'exports'} and
         request['schema'] == 'nider_original_export_comparison_request_v1' and request['task'] == TASK and
         type(request['exports']) is dict and set(request['exports']) == set(ARMS), 'owner_request_schema')
    validated = {}
    for role, arm in ARMS.items():
        entry = request['exports'][role]
        need(type(entry) is dict and set(entry) == {'arm', 'files'} and entry['arm'] == arm and
             type(entry['files']) is dict and set(entry['files']) == set(FILES), 'owner_role_and_file_set')
        raws = {name: pinned_read(entry['files'][name]) for name in FILES}
        validated[role] = validate_exports(raws, arm, loaded)
    pairs = {'paper_data_minus_reference': ('paper_data', 'reference'),
             'paper_data_author_code_minus_reference': ('paper_data_author_code', 'reference'),
             'paper_data_author_code_minus_paper_data': ('paper_data_author_code', 'paper_data')}
    return {'schema': 'nider_original_paired_export_comparison_v1', 'task': TASK,
            'input_bindings': request, 'contract_sha256': CONTRACT_SHA,
            'comparisons': {name: compare_pair(validated[left], validated[right]) for name, (left, right) in pairs.items()},
            'comparison_completed': True, 'reference_scientifically_qualified_by_this_tool': False,
            'information_condition_isolation_verified': False, 'native_objects_verified': False,
            'reproduction_success': None, 'improvement_success': None, 'readiness_changed': False,
            'unassessed': ['RDS objects and native computation', 'forest image rendering and scientific agreement',
                           'Bayesian print output', 'runtime and source acquisition custody',
                           'paper/archive correspondence', 'scientific reproduction tolerance',
                           'primary same-result superiority criterion']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--implementations', type=Path, required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--request-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    request_raw = regular_read(args.request, FILE_LIMIT)
    need(sha(request_raw) == args.request_sha256, 'owner_request_identity')
    request = json.loads(request_raw, object_pairs_hook=no_duplicates,
                         parse_constant=lambda value: need(False, 'nonfinite_request_number'))
    result = compare_request(request, load_contract(args.implementations))
    result['owner_request_sha256'] = args.request_sha256
    raw = (json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n').encode()
    need(len(raw) <= REPORT_LIMIT, 'comparison_report_extent')
    output = args.output
    need(output.is_absolute() and '..' not in output.parts and output.parent.is_dir() and
         not any(p.is_symlink() for p in (output, *output.parents)), 'fresh_private_output_path')
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
    print(json.dumps({'comparison_completed': True, 'report_bytes': len(raw),
                      'scientific_pass_defined': False, 'readiness_changed': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
