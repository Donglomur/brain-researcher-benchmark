"""Small invented workbook controls; these do not establish reproduction."""
import copy
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

spec = importlib.util.spec_from_file_location('reference', Path(__file__).with_name('recover_reference.py'))
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


def fixture_rows():
    header = ['outcome', 'signature', 'study', 'estimate', 'conf.low', 'conf.high']
    rows = [(1, header)]
    # An independent literal support list, not the implementation's SUPPORT.
    for signature, studies in [
        ('Negative Affect_x000D_\nDecoder', ['Average', 'Study 2', 'Study 3', 'Study 4']),
        ('Reappraisal Ability_x000D_\nDecoder', ['Average', 'Study 1', 'Study 3', 'Study 4']),
        ('Reappraisal State_x000D_\nDecoder', ['Average', 'Study 1', 'Study 2', 'Study 3', 'Study 4']),
    ]:
        for outcome in ['Trait questionnaire', 'Task-based affective rating']:
            for study in studies:
                rows.append((len(rows)+1, [outcome, signature, study, '-0,125', '-0,25', '0,5']))
    return rows


def workbook(rows, formula=False):
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    sheet = ET.Element('worksheet', xmlns=ns)
    body = ET.SubElement(sheet, 'sheetData')
    for number, values in rows:
        row = ET.SubElement(body, 'row', r=str(number))
        for column, value in zip('ABCDEF', values):
            cell = ET.SubElement(row, 'c', r=f'{column}{number}', t='inlineStr')
            ET.SubElement(ET.SubElement(cell, 'is'), 't').text = value
            if formula and column == 'D' and number == 2:
                ET.SubElement(cell, 'f').text = '1+1'
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as archive:
        archive.writestr('xl/workbook.xml',
            f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Fig5b" sheetId="2" r:id="rId2"/></sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId2" Target="worksheets/sheet2.xml"/></Relationships>')
        archive.writestr('xl/worksheets/sheet2.xml', ET.tostring(sheet))
    return out.getvalue()


class ReferenceControls(unittest.TestCase):
    def test_complete_panel_retains_sign_precision_and_all_support(self):
        recovered = reference.validate_rows(reference._read_rows(workbook(fixture_rows())))
        self.assertEqual(len(recovered), 26)
        self.assertEqual(sum(r['aggregation'] == 'pooled_people' for r in recovered), 6)
        self.assertEqual(recovered[0]['estimate_decimal'], '-0.125')
        self.assertEqual(recovered[0]['source_cell_text']['estimate'], '-0,125')
        self.assertEqual(recovered[0]['source_range'], 'Fig5b!A2:F2')
        self.assertEqual(recovered[0]['signature'], 'Negative Affect Decoder')

    def test_missing_pair_is_not_silently_reduced(self):
        with self.assertRaisesRegex(reference.SourceError, 'Incomplete'):
            reference.validate_rows(fixture_rows()[:-1])

    def test_training_cohort_exclusions_are_signature_specific(self):
        for signature, prohibited in [('Negative Affect', 'Study 1'), ('Reappraisal Ability', 'Study 2')]:
            rows = fixture_rows()
            row = next(c for _, c in rows[1:] if c[1].startswith(signature))
            row[2] = prohibited
            with self.subTest(signature=signature), self.assertRaisesRegex(reference.SourceError, 'Unexpected'):
                reference.validate_rows(rows)

    def test_duplicate_pair_is_not_double_counted(self):
        rows = fixture_rows()
        rows[-1] = (27, copy.deepcopy(rows[-2][1]))
        with self.assertRaisesRegex(reference.SourceError, 'Duplicate'):
            reference.validate_rows(rows)

    def test_unknown_target_is_not_aliased(self):
        rows = fixture_rows()
        rows[1][1][0] = 'Amygdala down-regulation'
        with self.assertRaisesRegex(reference.SourceError, 'Unexpected'):
            reference.validate_rows(rows)

    def test_decimal_format_ambiguity_and_nonfinite_rejected(self):
        for value in ['1,234.5', 'NaN', 'Infinity', '', '0,1,2', ' 0,1']:
            with self.subTest(value=value), self.assertRaises(reference.SourceError):
                reference._number(value)

    def test_invalid_interval_rejected(self):
        rows = fixture_rows()
        rows[1][1][4] = '0,2'
        with self.assertRaisesRegex(reference.SourceError, 'interval'):
            reference.validate_rows(rows)

    def test_column_permutation_rejected(self):
        rows = fixture_rows()
        rows[0][1][0:2] = rows[0][1][1::-1]
        with self.assertRaisesRegex(reference.SourceError, 'header'):
            reference.validate_rows(rows)

    def test_formula_cached_values_cannot_enter_reference(self):
        with self.assertRaisesRegex(reference.SourceError, 'formula'):
            reference._read_rows(workbook(fixture_rows(), formula=True))

    def test_sparse_cell_and_row_number_gap_rejected(self):
        rows = fixture_rows()
        rows[1][1].pop()
        with self.assertRaisesRegex(reference.SourceError, 'Missing Fig5b cell'):
            reference._read_rows(workbook(rows))
        rows = fixture_rows()
        rows[1] = (3, rows[1][1])
        with self.assertRaisesRegex(reference.SourceError, 'worksheet row'):
            reference._read_rows(workbook(rows))

    def test_equal_length_changed_source_fails_digest(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'source.xlsx'
            source.write_bytes(b'x' * reference.SOURCE_BYTES)
            with self.assertRaisesRegex(reference.SourceError, 'SHA-256'):
                reference.recover(source)


if __name__ == '__main__':
    unittest.main()
