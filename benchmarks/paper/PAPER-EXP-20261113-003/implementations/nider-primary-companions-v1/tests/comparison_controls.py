"""Generated paired-export controls; no R, original data or candidate execution."""
import argparse
import copy
import csv
from decimal import Decimal, localcontext
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


arguments = argparse.ArgumentParser()
arguments.add_argument('--implementations', type=Path, required=True)
arguments.add_argument('--scratch', type=Path, required=True)
args, remaining = arguments.parse_known_args()
compare = load('original_export_comparison', Path(__file__).resolve().parents[1] / 'compare_exports.py')
fixtures = load('original_companion_fixtures', args.implementations / 'nider-primary-companions-v1/tests/generated_controls.py')
loaded = compare.load_contract(args.implementations)
WRITTEN_BYTES = 0
READ_BYTES = 0
original_read = compare.regular_read


def counted_read(path, limit):
    global READ_BYTES
    raw = original_read(path, limit)
    READ_BYTES += len(raw)
    return raw


compare.regular_read = counted_read


def write(path, raw):
    global WRITTEN_BYTES
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    WRITTEN_BYTES += len(raw)


def generate(arm='A', drop_last=False):
    full = fixtures.prior_fixtures.generated_document()
    full['arm'] = arm
    if drop_last:
        row = full['contrasts'][0]
        row['membership'].pop()
        for field in ('k', 'k_all', 'k_TE', 'k_study', 'submitted_rows'):
            row['fields'][field]['value'] -= 1
        row['fields']['df_Q']['value'] -= 1
    ledger = fixtures.generated_ledger(full)
    documents = {'full120.json': full, 'row_lineage.json': ledger}
    for row in ledger['contrasts']:
        documents['dl/' + row['contrast'] + '.json'] = fixtures.generated_forest(row)
        documents['bayes/' + row['contrast'] + '.json'] = fixtures.generated_bayes(row)
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(compare.TABLE_COLUMNS)
    for model in compare.TABLE_MODELS:
        writer.writerow([model] + ['generated literal, "not a result"'] * 10)
    raws = {name: fixtures.base.json_bytes(value) for name, value in documents.items()}
    raws['table1/habit_associations.csv'] = stream.getvalue().encode()
    return raws


def mutate(raws, name, operation):
    value = json.loads(raws[name])
    operation(value)
    raws[name] = fixtures.base.json_bytes(value)


def validated(raws, arm='A'):
    return compare.validate_exports(raws, arm, loaded)


class ComparisonControls(unittest.TestCase):
    def test_complete_numeric_universe_and_source_coordinates(self):
        reference = validated(generate())
        result = compare.compare_pair(reference, reference)
        self.assertEqual(result['numeric_cell_count'], 120 + 8 * 117 + 123)
        self.assertEqual(result['numeric_status_counts'], {'FINITE_EQUAL': 1179})
        self.assertEqual(len(result['Table1_literal_cells']), 33)
        for contrast in compare.IDS:
            prefix = contrast + '/bayes/pairwise_BF/'
            self.assertEqual(sum(key.startswith(prefix) for key in result['numeric_cells']), 16)
        self.assertFalse(result['scientific_pass_defined'])

    def test_partial_but_internally_valid_population_cannot_be_compared(self):
        partial = validated(generate(drop_last=True))
        with self.assertRaisesRegex(ValueError, 'same_complete_source_population_required'):
            compare.compare_pair(partial, validated(generate()))
        raw = generate()
        mutate(raw, 'full120.json', lambda value: value['contrasts'].reverse())
        with self.assertRaisesRegex(ValueError, 'source_contrast_order'):
            validated(raw)

    def test_states_are_distinct_and_never_imputed_or_scored_as_agreement(self):
        for state in ('NA', 'NaN', '+Inf', '-Inf'):
            cell = {'state': state}
            same = compare.numeric_comparison(cell, cell)
            self.assertEqual(same['status'], 'SAME_NONFINITE_STATE_UNSCORED')
            self.assertIsNone(same['left_minus_right'])
            other = compare.numeric_comparison(cell, {'state': 'finite', 'value': Decimal('0')})
            self.assertEqual(other['status'], 'STATE_DIFFERENCE')
        self.assertEqual(compare.numeric_comparison({'state': 'NA'}, {'state': 'NaN'})['status'], 'STATE_DIFFERENCE')
        raws = generate()
        mutate(raws, 'dl/quest_self.json', lambda value: value['vectors']['TE']['values'].__setitem__(0, {'state': 'NA'}))
        comparison = compare.compare_pair(validated(raws), validated(generate()))
        self.assertEqual(comparison['numeric_status_counts']['STATE_DIFFERENCE'], 1)
        self.assertEqual(comparison['numeric_cell_count'], 1179)

    def test_exact_differences_do_not_depend_on_decimal_context(self):
        with localcontext() as context:
            context.prec = 2
            result = compare.numeric_comparison({'state': 'finite', 'value': Decimal('1e400')},
                                                {'state': 'finite', 'value': Decimal('1e-400')})
        self.assertEqual(result['left_minus_right']['numerator'], str(10 ** 800 - 1))
        self.assertEqual(result['left_minus_right']['denominator'], str(10 ** 400))

    def test_bayesian_matrix_orientation_and_inclusion_scalar_remain_separate(self):
        raws = generate()
        def transpose(value):
            matrix = value['pairwise_BF']['values_by_row']
            value['pairwise_BF']['values_by_row'] = [list(row) for row in zip(*matrix)]
            value['inclusion']['incl.BF']['value'] = 9.25
        mutate(raws, 'bayes/amy_quest.json', transpose)
        result = compare.compare_pair(validated(raws), validated(generate()))
        self.assertEqual(result['numeric_status_counts']['FINITE_DIFFERENT'], 13)
        delta = result['numeric_cells']['amy_quest/bayes/pairwise_BF/row=0/column=1']['left_minus_right']
        self.assertEqual(delta, {'numerator': '3', 'denominator': '1'})
        inclusion = result['numeric_cells']['amy_quest/bayes/inclusion/incl.BF']['left_minus_right']
        self.assertEqual(inclusion, {'numerator': '7', 'denominator': '1'})

    def test_metadata_differences_are_reported_without_silent_relabeling(self):
        raws = generate()
        mutate(raws, 'dl/quest_self.json', lambda value: value['vectors']['TE'].__setitem__('names', [None] * 39))
        mutate(raws, 'bayes/amy_self.json', lambda value: value['inclusion']['include'].__setitem__('storage_type', 'double'))
        mutate(raws, 'full120.json', lambda value: value['contrasts'][1]['tau_interval'].__setitem__('lower_sign', ''))
        result = compare.compare_pair(validated(raws), validated(generate()))
        self.assertEqual(sum(not record['equal'] for record in result['metadata'].values()), 3)
        self.assertEqual(result['numeric_status_counts'], {'FINITE_EQUAL': 1179})

    def test_complete_exports_and_literal_original_table_are_required(self):
        for defect in ('file', 'vector', 'column', 'model_order'):
            raws = generate()
            if defect == 'file':
                del raws['bayes/amy_self.json']
            elif defect == 'vector':
                mutate(raws, 'dl/amy_self.json', lambda value: value['vectors']['TE']['values'].pop())
            elif defect == 'column':
                raws['table1/habit_associations.csv'] = raws['table1/habit_associations.csv'].replace(b'95% CIa', b'95% CI')
            else:
                rows = raws['table1/habit_associations.csv'].splitlines(keepends=True)
                rows[1], rows[2] = rows[2], rows[1]
                raws['table1/habit_associations.csv'] = b''.join(rows)
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                validated(raws)

    def test_one_pinned_request_pairs_both_arms_to_the_same_reference(self):
        global WRITTEN_BYTES
        with tempfile.TemporaryDirectory(dir=args.scratch, prefix='generated-paired-exports-') as directory:
            root = Path(directory)
            request = {'schema': 'nider_original_export_comparison_request_v1', 'task': compare.TASK, 'exports': {}}
            for role, arm in compare.ARMS.items():
                raws = generate(arm)
                if role == 'paper_data_author_code':
                    mutate(raws, 'dl/amy_self.json', lambda value: value['vectors']['TE']['values'][0].__setitem__('value', 0.5))
                pins = {}
                for name, raw in raws.items():
                    path = root / role / name
                    write(path, raw)
                    pins[name] = {'path': str(path), 'bytes': len(raw), 'sha256': compare.sha(raw)}
                request['exports'][role] = {'arm': arm, 'files': pins}
            request_raw = fixtures.base.json_bytes(request)
            request_path, output = root / 'request.json', root / 'report.json'
            write(request_path, request_raw)
            command = ['--implementations', str(args.implementations), '--request', str(request_path),
                       '--request-sha256', compare.sha(request_raw), '--output', str(output)]
            self.assertEqual(compare.main(command), 0)
            WRITTEN_BYTES += output.stat().st_size
            report = json.loads(output.read_bytes())
            self.assertEqual(report['owner_request_sha256'], compare.sha(request_raw))
            self.assertEqual(set(report['comparisons']), {'paper_data_minus_reference',
                'paper_data_author_code_minus_reference', 'paper_data_author_code_minus_paper_data'})
            for name, pair in report['comparisons'].items():
                self.assertEqual(pair['numeric_cell_count'], 1179)
                self.assertEqual(pair['numeric_status_counts'].get('FINITE_DIFFERENT', 0), int(name != 'paper_data_minus_reference'))
            self.assertIsNone(report['reproduction_success'])
            self.assertIsNone(report['improvement_success'])
            self.assertFalse(report['reference_scientifically_qualified_by_this_tool'])
            before = output.read_bytes()
            with self.assertRaises(FileExistsError):
                compare.main(command)
            self.assertEqual(output.read_bytes(), before)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            candidate = Path(request['exports']['paper_data']['files']['full120.json']['path'])
            write(candidate, candidate.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'input_pin_identity'):
                compare.compare_request(request, loaded)
            bad_sha_command = list(command)
            bad_sha_command[5] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'owner_request_identity'):
                compare.main(bad_sha_command)


if __name__ == '__main__':
    try:
        unittest.main(argv=[sys.argv[0]] + remaining, verbosity=2)
    finally:
        print(json.dumps({'generated_test_written_bytes': WRITTEN_BYTES,
                          'comparison_body_read_bytes': READ_BYTES,
                          'scientific_runs': 0, 'native_processes': 0}))
