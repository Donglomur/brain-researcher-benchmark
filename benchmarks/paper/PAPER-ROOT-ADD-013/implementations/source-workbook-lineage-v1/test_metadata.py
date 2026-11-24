"""Generated OOXML controls; never opens authentic workbooks or neural inputs."""
import importlib.util
import io
import json
from pathlib import Path
import unittest
import warnings
import zipfile

spec = importlib.util.spec_from_file_location("metadata", Path(__file__).with_name("inspect_metadata.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture(*, formula=False, duplicate=False, target="worksheets/second.xml", external=False,
            extra=None, shared="presleep", outside=False, mixed_type=False):
    workbook = f'<workbook xmlns="{m.S}" xmlns:r="{m.R}"><sheets><sheet name="Metadata" sheetId="7" r:id="first"/></sheets></workbook>'
    relationships = f'<Relationships xmlns="{m.P}"><Relationship Id="first" Type="{m.R}/worksheet" Target="{target}"'+(' TargetMode="External"' if external else '')+f'/><Relationship Id="strings" Type="{m.R}/sharedStrings" Target="sharedStrings.xml"/></Relationships>'
    shared_xml = f'<sst xmlns="{m.S}"><si><t>{shared}</t></si><si><r><t>post</t></r><r><t>sleep</t></r></si></sst>'
    row2 = '<c r="A2"><v>1</v></c><c r="B2"><v>3</v></c><c r="C2" t="s"><v>0</v></c><c r="D2"><v>0</v></c><c r="E2" t="inlineStr"><is><t>private/path1</t></is></c>'
    if formula:
        row2 = row2.replace('<c r="D2"><v>0</v></c>', '<c r="D2"><f>1+1</f><v>2</v></c>')
    if duplicate:
        row2 += '<c r="D2"><v>1</v></c>'
    row3 = '<c r="A3"><v>1</v></c><c r="B3"><v>3</v></c><c r="C3" t="s"><v>1</v></c><c r="D3"><v>0.5</v></c><c r="E3" t="inlineStr"><is><t>private/path2</t></is></c>'
    if mixed_type:
        row3 = row3.replace('<c r="D3"><v>0.5</v></c>', '<c r="D3" t="inlineStr"><is><t>0</t></is></c>')
    overflow = '<row r="275"><c r="A275"><f>BAD()</f><v>5</v></c></row>' if outside else ''
    sheet = f'<worksheet xmlns="{m.S}"><sheetData><row r="2">{row2}</row><row r="3">{row3}</row>{overflow}</sheetData></worksheet>'
    items = [('xl/workbook.xml',workbook),('xl/_rels/workbook.xml.rels',relationships),
             ('xl/sharedStrings.xml',shared_xml),('xl/worksheets/second.xml',sheet)]
    if extra:
        items.append(extra)
    out=io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',UserWarning)
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            for name, body in items:z.writestr(name,body)
    return out.getvalue()


def inspect(raw):
    return m.inspect_workbook(raw, m.identity(raw))


class MetadataTests(unittest.TestCase):
    def test_relationship_resolved_and_literal_metadata_preserved(self):
        r=inspect(fixture())
        self.assertEqual(r['selected_sheet_member'],'xl/worksheets/second.xml')
        self.assertEqual(r['summary']['groups_with_literal_presleep_and_postsleep'],1)
        self.assertEqual(r['summary']['groups_with_multiple_condition_values_or_types'],1)
        expected=[{'kind':'n','value':'0','count':1},{'kind':'n','value':'0.5','count':1}]
        self.assertEqual(r['summary']['condition_values'],expected)
        self.assertEqual(r['groups'][0]['condition_counts'],expected)
        self.assertEqual(r['groups'][0]['rows'],[2,3])
        self.assertNotIn('rows',r)
        self.assertNotIn('private/path',str(r))


    def test_original_row_session_condition_associations_are_retained(self):
        # Same animal/day and marginal totals, different original row pairing.
        raw=fixture()
        source=io.BytesIO(raw)
        changed=io.BytesIO()
        with zipfile.ZipFile(source) as old, zipfile.ZipFile(changed,'w',zipfile.ZIP_DEFLATED) as new:
            for member in old.infolist():
                body=old.read(member)
                if member.filename=='xl/worksheets/second.xml':
                    body=body.replace(b'<c r="D2"><v>0</v></c>',b'<c r="D2"><v>0.5</v></c>')
                    body=body.replace(b'<c r="D3"><v>0.5</v></c>',b'<c r="D3"><v>0</v></c>')
                new.writestr(member.filename,body)
        a,b=inspect(raw),inspect(changed.getvalue())
        self.assertEqual(a['summary'],b['summary'])
        self.assertEqual(a['groups'][0]['condition_counts'],b['groups'][0]['condition_counts'])
        self.assertEqual(a['groups'][0]['session_counts'],b['groups'][0]['session_counts'])
        self.assertNotEqual(a['groups'][0]['records'],b['groups'][0]['records'])
        projected=json.loads(m.serialize_report(a))
        self.assertEqual(projected['schema'],'food-ripples-workbook-lineage/v3')
        self.assertEqual(projected['groups'][0]['records'],[
            {'row':2,'session':{'kind':'text','value':'presleep'},'condition':{'kind':'n','value':'0'}},
            {'row':3,'session':{'kind':'text','value':'postsleep'},'condition':{'kind':'n','value':'0.5'}}])
        self.assertNotIn('private/path',str(projected))
        self.assertNotIn('recording_path_sha256',str(projected))

    def test_row_associations_preserve_blank_and_typed_values(self):
        report=inspect(fixture(mixed_type=True))
        records=report['groups'][0]['records']
        self.assertEqual([r['condition']['kind'] for r in records],['n','text'])
        self.assertEqual([r['condition']['value'] for r in records],['0','0'])
        raw=fixture()
        stream=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw)) as old, zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as new:
            for member in old.infolist():
                body=old.read(member)
                if member.filename=='xl/worksheets/second.xml':
                    body=body.replace(b'<c r="D3"><v>0.5</v></c>',b'')
                new.writestr(member.filename,body)
        missing=inspect(stream.getvalue())['groups'][0]['records'][1]['condition']
        self.assertEqual(missing,{'kind':'blank','value':''})

    def test_source_identity_checked_before_zip(self):
        with self.assertRaisesRegex(m.MetadataError,'identity'):
            m.inspect_workbook(fixture())

    def test_formula_with_cached_value_rejected(self):
        with self.assertRaisesRegex(m.MetadataError,'formula'):
            inspect(fixture(formula=True))

    def test_duplicate_cell_and_member_rejected(self):
        for raw in [fixture(duplicate=True),fixture(extra=('xl/workbook.xml','<x/>'))]:
            with self.assertRaisesRegex(m.MetadataError,'duplicate'):inspect(raw)

    def test_external_and_traversal_relationship_rejected(self):
        for raw in [fixture(external=True),fixture(target='../evil.xml')]:
            with self.assertRaises(m.MetadataError):inspect(raw)

    def test_dtd_and_entities_rejected(self):
        with self.assertRaises(m.MetadataError):
            inspect(fixture(shared='<!DOCTYPE foo [<!ENTITY x "bad">]>&x;'))

    def test_expansion_cap_rejected_before_decompression(self):
        with self.assertRaisesRegex(m.MetadataError,'expanded'):
            inspect(fixture(extra=('large.txt','x'*(m.MAX_EXPANDED+1))))

    def test_original_row_boundary_does_not_interpret_other_formula(self):
        r=inspect(fixture(outside=True))
        self.assertEqual(r['summary']['nonblank_metadata_rows'],2)
        self.assertEqual(r['cells_outside_selected_range_not_interpreted'],1)

    def test_macro_and_external_sheet_relationships_rejected(self):
        outside = f'<Relationships xmlns="{m.P}"><Relationship Id="link" Target="https://example.invalid" TargetMode="External"/></Relationships>'
        for raw in [fixture(extra=('xl/vbaProject.bin','bad')),
                    fixture(extra=('xl/worksheets/_rels/second.xml.rels',outside))]:
            with self.assertRaises(m.MetadataError):inspect(raw)

    def test_utf16_and_utf32_entity_counterexamples_rejected(self):
        text='''<?xml version="1.0"?><!DOCTYPE a [<!ENTITY x "expanded">]><a>&x;</a>'''
        for encoding in ('utf-16','utf-16-le','utf-32','utf-32-le'):
            with self.assertRaises(m.MetadataError):m.xml(text.encode(encoding))
        with self.assertRaises(m.MetadataError):
            m.xml(b'<?xml version="1.0" encoding="UTF-16"?><a/>')
        self.assertEqual(m.xml(b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8"?><a/>').tag,'a')

    def test_numeric_and_text_conditions_do_not_merge(self):
        r=inspect(fixture(mixed_type=True))
        self.assertEqual(r['summary']['condition_values'],[
            {'kind':'n','value':'0','count':1},{'kind':'text','value':'0','count':1}])
        self.assertEqual(r['summary']['groups_with_multiple_condition_values_or_types'],1)

    def test_bounded_report_preserves_full_grouping_and_typed_identities(self):
        # Generated maximum row/member counts, escaped Unicode, and long names.
        target='worksheets/'+'z'*110+'.xml'
        long_text='\U0001f600'*4096
        workbook=f'<workbook xmlns="{m.S}" xmlns:r="{m.R}"><sheets><sheet name="{long_text}" sheetId="1" r:id="first"/></sheets></workbook>'
        rels=f'<Relationships xmlns="{m.P}"><Relationship Id="first" Type="{m.R}/worksheet" Target="{target}"/><Relationship Id="strings" Type="{m.R}/sharedStrings" Target="sharedStrings.xml"/></Relationships>'
        shared=f'<sst xmlns="{m.S}"><si><t>{long_text}</t></si></sst>'
        headers=''.join(f'<c r="{chr(64+column)}1" t="s"><v>0</v></c>' for column in range(1,16))
        rows=[f'<row r="1">{headers}</row>']
        for row in range(2,275):
            condition='1'*128+str(row)
            session='&quot;'*80+str(row)
            rows.append(f'<row r="{row}"><c r="A{row}"><v>{row}</v></c><c r="B{row}" t="s"><v>0</v></c><c r="C{row}" t="inlineStr"><is><t>{session}</t></is></c><c r="D{row}"><v>{condition}</v></c></row>')
        sheet=f'<worksheet xmlns="{m.S}"><sheetData>{"".join(rows)}</sheetData></worksheet>'
        items=[('xl/workbook.xml',workbook),('xl/_rels/workbook.xml.rels',rels),
               ('xl/sharedStrings.xml',shared),('xl/'+target,sheet)]
        items += [(f'xl/extra/{i:03d}-'+('r'*80)+'.rels',f'<Relationships xmlns="{m.P}"/>')
                  for i in range(124)]
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
            for name,value in items:archive.writestr(name,value)
        report=inspect(stream.getvalue())
        self.assertEqual(len(report['groups']),273)
        self.assertEqual(len(report['members_read']),128)
        self.assertEqual(len(report['summary']['session_values']),273)
        self.assertEqual(len(report['summary']['condition_values']),273)
        self.assertEqual(report['groups'][0]['animal']['value'],long_text)
        body=m.serialize_report(report)
        projected=json.loads(body)
        self.assertLessEqual(len(body),521592)
        self.assertLessEqual(len(m.run_receipt(report,body))+1,2048)
        self.assertEqual(len(projected['groups']),273)
        self.assertEqual(sum(len(g['records']) for g in projected['groups']),273)
        for group in projected['groups']:
            self.assertEqual([r['row'] for r in group['records']],group['rows'])
            self.assertEqual(group['records'][0]['condition']['value_identity'],
                             group['condition_counts'][0]['value_identity'])
            self.assertEqual(group['records'][0]['session']['value_identity'],
                             group['session_counts'][0]['value_identity'])
        self.assertEqual(projected['groups'][0]['animal']['value_identity'],m.value_identity(long_text))
        self.assertEqual(len({g['condition_counts'][0]['value_identity']['sha256'] for g in projected['groups']}),273)
        self.assertIsInstance(projected['first_sheet_name'],dict)
        self.assertIsInstance(projected['selected_sheet_member'],dict)
        typed=[m.bounded_cell({'kind':kind,'value':'1'*128,'count':273}) for kind in ('n','text')]
        self.assertNotEqual(typed[0],typed[1])
        self.assertEqual(typed[0]['value_identity'],typed[1]['value_identity'])
        self.assertEqual(m.bounded_cell({'kind':'text','value':'short'}),{'kind':'text','value':'short'})
        self.assertTrue(all(len(m.compact_json(cell))<=192 for cell in typed))
        self.assertNotIn('session_values',json.loads(m.run_receipt(report,body))['summary'])


if __name__=='__main__':unittest.main()
