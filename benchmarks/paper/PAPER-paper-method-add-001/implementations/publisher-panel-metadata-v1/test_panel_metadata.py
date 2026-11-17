"""Generated software controls; no authentic source result values are used."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('panel_metadata', HERE / 'panel_metadata.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

DAYS = {'force': [0, 1, 2, 6, 7, 8, 9, 10, 21, 25, 26, 27, 28, 29, 32, 37, 38, 40, 91, 95],
        'reaching': [0, 1, 2, 3, 9, 10, 14, 15, 16, 36, 37, 38]}


def rows():
    panels = {}
    for sheet, (task, _, _) in m.PANELS.items():
        days = DAYS[task]
        panels[sheet] = []
        for method in m.METHODS:
            panels[sheet].extend([[task, str(a) + '.0', str(b) + '.0', method]
                                 for a in days for b in days if a != b])
            panels[sheet].extend([[task, str(a) + '.0', 'None', method] for a in days])
    return panels


def workbook(panels=None, *, formula_identity=False, omit_sheet=False,
             score_text='SHOULD_NEVER_APPEAR_IN_METADATA', duplicate_member=False,
             style_extras=False, populated_extra=False):
    panels = rows() if panels is None else panels
    values = list(m.HEADERS)
    for data in panels.values():
        for row in data:
            values.extend(v for v in row if not v.endswith('.0'))
    strings = list(dict.fromkeys(values))
    ids = {value: i for i, value in enumerate(strings)}
    shared = ET.Element(m.S + 'sst')
    for value in strings:
        ET.SubElement(ET.SubElement(shared, m.S + 'si'), m.S + 't').text = value
    book = ET.Element(m.S + 'workbook')
    sheets = ET.SubElement(book, m.S + 'sheets')
    rels = ET.Element('{http://schemas.openxmlformats.org/package/2006/relationships}Relationships')
    members = {'xl/sharedStrings.xml': ET.tostring(shared)}
    for number, (name, data) in enumerate(panels.items(), 1):
        if omit_sheet and number == 2:
            continue
        rid = 'rId' + str(number)
        ET.SubElement(sheets, m.S + 'sheet', {'name': name, m.R + 'id': rid})
        ET.SubElement(rels, 'Relationship', {'Id': rid, 'Type': m.R[1:-1] + '/worksheet',
                                           'Target': 'worksheets/sheet' + str(number) + '.xml'})
        sheet = ET.Element(m.S + 'worksheet')
        body = ET.SubElement(sheet, m.S + 'sheetData')
        for r, row_values in enumerate([list(m.HEADERS)] + data, 1):
            row = ET.SubElement(body, m.S + 'row', {'r': str(r)})
            for col, value in zip('ABCDE', row_values):
                cell = ET.SubElement(row, m.S + 'c', {'r': col + str(r)})
                if value in ids:
                    cell.set('t', 's')
                    value = str(ids[value])
                ET.SubElement(cell, m.S + 'v').text = value
                if formula_identity and r == 2 and col == 'B':
                    ET.SubElement(cell, m.S + 'f').text = '1+1'
            if r > 1:
                cell = ET.SubElement(row, m.S + 'c', {'r': 'E' + str(r)})
                ET.SubElement(cell, m.S + 'v').text = score_text
            if r == 1 and number == 1 and (style_extras or populated_extra):
                for code in range(ord('F'), ord('Z') + 1):
                    cell = ET.SubElement(row, m.S + 'c', {'r': chr(code) + '1', 's': '2'})
                    if populated_extra and chr(code) == 'F':
                        ET.SubElement(cell, m.S + 'v').text = 'unexpected'
        members['xl/worksheets/sheet' + str(number) + '.xml'] = ET.tostring(sheet)
    members['xl/workbook.xml'] = ET.tostring(book)
    members['xl/_rels/workbook.xml.rels'] = ET.tostring(rels)
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for name, body in members.items():
            z.writestr(name, body)
        if duplicate_member:
            z.writestr('xl/workbook.xml', members['xl/workbook.xml'])
    return output.getvalue()


class MetadataTests(unittest.TestCase):
    def test_complete_source_shape_and_opaque_scores(self):
        result = m.parse_workbook(workbook())
        self.assertFalse(result['published_source_authenticated'])
        for sheet, count, pair_count, one_day in [('Figure 3', 20, 380, 22),
                                                 ('Figure 4', 12, 132, 16)]:
            panel = result['panels'][sheet]
            self.assertEqual(len(panel['session_days']), count)
            self.assertEqual(len(panel['directed_pairs']), pair_count)
            self.assertEqual(len(panel['null_query_anchors']), count)
            self.assertEqual(panel['one_day_directed_pair_count'], one_day)
            self.assertEqual(len(panel['source_order_rows']), count*count*4)
            self.assertTrue(all(set(r['source_rows_by_method']) == set(m.METHODS)
                                for r in panel['directed_pairs']))
        self.assertNotIn('SHOULD_NEVER_APPEAR', json.dumps(result))

    def test_score_content_is_not_interpreted_or_extracted(self):
        first = m.parse_workbook(workbook(score_text='not-a-number'))
        second = m.parse_workbook(workbook(score_text='-Infinity'))
        self.assertEqual(first['panels'], second['panels'])
        self.assertNotEqual(first['source_pin'], second['source_pin'])

    def test_missing_row_cannot_become_a_smaller_panel(self):
        data = rows(); data['Figure 3'].pop(4)
        with self.assertRaisesRegex(m.InvalidSource, 'complete panel row count'):
            m.parse_workbook(workbook(data))

    def test_duplicate_pair_replacing_another_keeps_count_but_refuses(self):
        data = rows(); data['Figure 3'][1] = copy.deepcopy(data['Figure 3'][0])
        with self.assertRaisesRegex(m.InvalidSource, 'every directed pair'):
            m.parse_workbook(workbook(data))

    def test_missing_anchor_replaced_by_duplicate_refuses(self):
        data = rows(); data['Figure 3'][381] = copy.deepcopy(data['Figure 3'][380])
        with self.assertRaisesRegex(m.InvalidSource, 'one null-query anchor'):
            m.parse_workbook(workbook(data))

    def test_task_swap_refuses(self):
        data = rows(); data['Figure 3'][0][0] = 'reaching'
        with self.assertRaisesRegex(m.InvalidSource, 'panel task'):
            m.parse_workbook(workbook(data))

    def test_literal_method_alias_refuses(self):
        data = rows(); data['Figure 3'][0][3] = 'NoMAD'
        with self.assertRaisesRegex(m.InvalidSource, 'literal method'):
            m.parse_workbook(workbook(data))

    def test_fractional_session_day_refuses(self):
        data = rows(); data['Figure 3'][0][1] = '0.5'
        with self.assertRaisesRegex(m.InvalidSource, 'exact nonnegative integer'):
            m.parse_workbook(workbook(data))

    def test_formula_in_identity_refuses(self):
        with self.assertRaisesRegex(m.InvalidSource, 'formula'):
            m.parse_workbook(workbook(formula_identity=True))

    def test_both_original_tasks_are_mandatory(self):
        with self.assertRaisesRegex(m.InvalidSource, 'both original monkey panels'):
            m.parse_workbook(workbook(omit_sheet=True))

    def test_source_row_numbers_and_both_directions_preserved(self):
        panel = m.parse_workbook(workbook())['panels']['Figure 3']
        forward = next(p for p in panel['directed_pairs'] if (p['reference_day'], p['query_day']) == (0, 95))
        reverse = next(p for p in panel['directed_pairs'] if (p['reference_day'], p['query_day']) == (95, 0))
        self.assertEqual((forward['signed_day_gap'], reverse['signed_day_gap']), (95, -95))
        self.assertNotEqual(forward['source_rows_by_method'], reverse['source_rows_by_method'])
        self.assertEqual(panel['source_order_rows'][380]['source_query_label'], 'None')

    def test_generated_package_cannot_claim_publisher_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'fixture.xlsx'; path.write_bytes(workbook())
            with self.assertRaisesRegex(m.InvalidSource, 'published workbook byte length'):
                m.prepare_source_roster(path)

    def test_matching_length_does_not_replace_full_source_digest(self):
        raw = workbook()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'same-size.xlsx'
            path.write_bytes(raw + b' ' * (m.PUBLISHED_BYTES - len(raw)))
            with self.assertRaisesRegex(m.InvalidSource, 'published workbook SHA-256'):
                m.prepare_source_roster(path)

    def test_duplicate_zip_member_refuses(self):
        with self.assertWarns(UserWarning):
            raw = workbook(duplicate_member=True)
        with self.assertRaisesRegex(m.InvalidSource, 'duplicate ZIP members'):
            m.parse_workbook(raw)

    def test_original_styled_empty_header_cells_are_retained(self):
        panel = m.parse_workbook(workbook(style_extras=True))['panels']['Figure 3']
        self.assertEqual(panel['empty_style_cells'], [chr(code) + '1' for code in range(ord('F'), ord('Z')+1)])
        self.assertEqual(len(panel['directed_pairs']), 380)

    def test_populated_extra_column_is_not_silently_dropped(self):
        with self.assertRaisesRegex(m.InvalidSource, 'unexpected populated source column'):
            m.parse_workbook(workbook(populated_extra=True))


if __name__ == '__main__':
    unittest.main()
