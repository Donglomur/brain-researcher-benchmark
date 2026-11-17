"""Invented interface controls only; no authentic data, labels or outcomes."""
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import provision_identity_policy as p
import provision_family_ledger as f


def fixture():
    roster = {f'invented-{i}': ['NOD'] + (['COW'] if i >= 8 else [])
              + (['CTN'] if i >= 11 else []) for i in range(16)}
    core = 'MANIFEST = MappingProxyType(' + repr(roster).replace("'NOD'", 'Exps.NOD').replace("'COW'", 'Exps.COW').replace("'CTN'", 'Exps.CTN') + ')\n'
    core += 'EXPERIMENT_DISPLAY_NAMES = {Exps.NOD: "Novelty", Exps.COW: "Locomotion", Exps.CTN: "Dual"}\n'
    loader = 'dual_subjects <- c(' + ','.join(json.dumps(f'invented-{i}') for i in range(11, 16)) + ')'
    columns = {f'mask_{i}': f'Column.{i}' for i in range(13)}
    columns.update({f'keep_{i}': f'Column.{i}' for i in range(13, 27)})
    exclusions = [('invented-0', 'NOD', ('mask_',))] + [(f'invented-{i}', 'NOD', ('unused_',)) for i in range(1, 6)]
    source = 'exclusions = ' + repr(exclusions).replace("'NOD'", 'Exps.NOD') + '\ncontrast_display_names = ' + repr(columns)
    nb = {'cells': [{'cell_type': 'code', 'source': [source], 'outputs': []}]}
    return core, loader, json.dumps(nb)


def workbook(formula=False, duplicate=False, missing=False):
    strings = ['Response variable', 'Primary covariate', 'Figure', 'Invented response', 'Invented covariate', 'Invented figure']
    ns = f.NS['m']
    shared = '<sst xmlns="' + ns + '">' + ''.join('<si><t>' + s + '</t></si>' for s in strings) + '</sst>'
    rows = []
    for i in range(1, 100 if not missing else 99):
        indexes = [0, 1, 2] if i == 1 else [3, 4, 5]
        cells = ''.join(f'<c r="{c}{i}" t="s">' + ('<f>1+1</f>' if formula and i == 2 and c == 'A' else '') + f'<v>{v}</v></c>' for c, v in zip('ABC', indexes))
        cells += f'<c r="D{i}" t="s"><v>999999</v></c>'  # An inaccessible outcome index must never be read.
        rows.append(f'<row r="{i}">{cells}</row>')
    if duplicate:
        rows.append(rows[-1])
    sheet = '<worksheet xmlns="' + ns + '"><sheetData>' + ''.join(rows) + '</sheetData></worksheet>'
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w') as z:
        z.writestr('xl/sharedStrings.xml', shared); z.writestr('xl/worksheets/sheet1.xml', sheet)
    return b.getvalue()


class PolicyControls(unittest.TestCase):
    def test_full_private_policy_derivation(self):
        x = p.derive(*fixture())
        self.assertEqual(len(x['balanced_subjects']), 5)
        self.assertEqual(len(x['ordinary_exclusion']['columns']), 13)
        self.assertEqual(x['ordinary_exclusion']['subject'], 'invented-0')
        self.assertEqual(p.encode(x), p.encode(p.derive(*fixture())))

    def test_not_a_code_executor(self):
        with self.assertRaises(ValueError):
            p.literal(__import__('ast').parse("__import__('os').system('false')", mode='eval').body)

    def test_duplicate_assignment_and_roster(self):
        a, b, c = fixture()
        for changed in [a + '\nMANIFEST = {}', a.replace("'invented-1':", "'invented-0':")]:
            with self.assertRaises(ValueError): p.derive(changed, b, c)

    def test_duplicate_or_ineligible_balanced_person(self):
        a, b, c = fixture()
        for bad in [b.replace('invented-12', 'invented-11'), b.replace('invented-12', 'invented-1')]:
            with self.assertRaises(ValueError): p.derive(a, bad, c)

    def test_extra_exclusion_not_silently_admitted(self):
        a, b, c = fixture(); nb = json.loads(c)
        nb['cells'][0]['source'][0] = nb['cells'][0]['source'][0].replace("('unused_',)", "('keep_',)", 1)
        with self.assertRaises(ValueError): p.derive(a, b, json.dumps(nb))

    def test_notebook_outputs_and_duplicate_json_refused(self):
        a, b, c = fixture(); nb = json.loads(c); nb['cells'][0]['outputs'] = [{'text': 'invented'}]
        with self.assertRaises(ValueError): p.derive(a, b, json.dumps(nb))
        with self.assertRaises(ValueError): p.derive(a, b, '{"cells":[],"cells":[]}')

    def test_fixed_production_inputs_reject_substitutes(self):
        with tempfile.TemporaryDirectory() as d:
            paths = {}
            for role, pin in p.PINS.items():
                path = Path(d) / role; path.write_bytes(b'x' * pin[0]); paths[role] = path
            with self.assertRaises(ValueError): p.provision(paths)

    def test_no_clobber_and_no_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'output'; p.write_exclusive(path, b'first')
            with self.assertRaises(FileExistsError): p.write_exclusive(path, b'second')
            self.assertEqual(path.read_bytes(), b'first')
            link = Path(d) / 'link'; link.symlink_to(path)
            with self.assertRaises(OSError): p.authenticated_file(link, (5, '0' * 64))


class FamilyControls(unittest.TestCase):
    def test_all_headers_without_outcome_access(self):
        x = f.headers(workbook()); self.assertEqual(len(x), 98)
        self.assertEqual(set(x[2]), {'response', 'covariate', 'figure'})

    def test_formula_duplicate_and_missing_headers_refuse(self):
        for args in [{'formula': True}, {'duplicate': True}, {'missing': True}]:
            with self.assertRaises(ValueError): f.headers(workbook(**args))

    def test_flat_yaml_quoted_and_unquoted_lineage(self):
        x = f.parameters(b'# note\n- title: "invented"\n  fstem: X\n\n- title: \'also invented\'\n  fstem: Y\n')
        self.assertEqual([r['source_line'] for r in x], [2, 5])
        self.assertEqual(x[0]['title'], 'invented')

    def test_yaml_duplicate_nested_or_executable_refuses(self):
        for text in ['- title: x\n  fstem: y\n  fstem: z', '- title: x\n  fstem: [y]', '- title: !!python/object:x\n  fstem: y']:
            with self.assertRaises(ValueError): f.parameters(text.encode())

    def test_full_98_and_15_partition(self):
        cross = json.loads(Path(__file__).with_name('CURATED_CROSSWALK.json').read_bytes())
        configs = {}
        counts = {'condition_correlation': 15, 'condition_difference_correlation': 24,
                  'cortical_spindle': 6, 'eta_ext_wake_increase': 1, 'ewk_change': 4,
                  'firing_rates': 10, 'first_novelty': 7, 'fractional_occupancy': 1,
                  'homeostasis': 13, 'multiregion_condition_difference_correlation': 20,
                  'off_change': 4, 'ripple_freq': 1, 'sgfg': 1, 'state_rate': 2}
        for family, count in counts.items():
            configs[family] = [{'source_line': i, 'title': 'Invented', 'fstem':
                               'RevFig999' if family in ('ewk_change', 'off_change') or family == 'firing_rates' and i not in (4, 5, 6) else 'Invented'}
                              for i in range(1, count + 1)]
        labels = {r['table1_row']: {'response': 'Invented', 'covariate': 'Invented', 'figure': 'Invented'} for r in cross['rows']}
        result = json.loads(f.assemble(cross, labels, configs))
        self.assertEqual(len(result['rows']), 98)
        self.assertEqual(sum(x['source_analysis_id'].startswith('fractional_occupancy:') for x in result['rows']), 5)
        bad = copy.deepcopy(cross); bad['rows'][1]['source_analysis_id'] = bad['rows'][0]['source_analysis_id']
        with self.assertRaises(ValueError): f.assemble(bad, labels, configs)
        configs['firing_rates'][0]['fstem'] = 'Invented'
        with self.assertRaises(ValueError): f.assemble(cross, labels, configs)


if __name__ == '__main__':
    unittest.main()
