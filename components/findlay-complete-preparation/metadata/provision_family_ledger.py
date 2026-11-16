"""Reconstruct all 98 fixed family metadata rows using explicit authored curation.

Read-only XLSX label extraction; no result columns, recalculation or author code
execution. The result stays external. The curated join is not publisher metadata.
"""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

from provision_identity_policy import authenticated_file, need, unique, write_exclusive

CROSSWALK_PIN = (32045, '508f2929ce81e100af354daffa9c28eb567d3d38fd0273180d3c76aa87045194')
WORKBOOK_PIN = (26378, 'e0f45c39c36cf9b9b82f84d54e622cb2449ac2e7607ac57ab3fec20ddc17f62b')
OUTPUT_PIN = (66285, 'e6602394041e2a6f448db374ffccbf06856f262e13df468003a901ae4fa2eced')
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def parameters(body):
    """Only the flat string-mapping YAML subset present in the pinned release."""
    text = body.decode('utf-8')
    rows = []; row = None
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        match = re.fullmatch(r'(- |  )([A-Za-z_]+):\s*(.*?)\s*', line)
        need(match is not None, 'Unsupported YAML grammar')
        marker, key, raw = match.groups()
        if marker == '- ':
            row = {'source_line': number}; rows.append(row)
        need(row is not None and key not in row and raw, 'Unique nonempty YAML fields')
        if raw[0] in ('\"', "'"):
            value = ast.literal_eval(raw)
            need(type(value) is str, 'String YAML scalar required')
        else:
            need(not any(c in raw for c in '[]{}&*!|>#'), 'Unsupported YAML scalar')
            value = raw
        row[key] = value
    need(rows and all(type(x.get('title')) is str and type(x.get('fstem')) is str for x in rows),
         'Complete rendering configurations')
    return rows


def xml(body):
    need(b'<!DOCTYPE' not in body and b'<!ENTITY' not in body, 'No XML entity declarations')
    return ET.fromstring(body)


def headers(body):
    """Extract A:C only, never D:I results or calculation caches."""
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        entries = archive.infolist()
        need(len(entries) <= 32 and len({x.filename for x in entries}) == len(entries)
             and sum(x.file_size for x in entries) <= 524288, 'Bounded unique workbook members')
        names = {x.filename for x in entries}
        need('xl/sharedStrings.xml' in names and 'xl/worksheets/sheet1.xml' in names,
             'Expected label sources')
        shared = xml(archive.read('xl/sharedStrings.xml'))
        sheet = xml(archive.read('xl/worksheets/sheet1.xml'))
    strings = [''.join(t.text or '' for t in si.findall('.//m:t', NS)) for si in shared]
    result = {}; title = None
    for row in sheet.findall('m:sheetData/m:row', NS):
        number = int(row.attrib['r']); cells = {}
        for cell in row:
            coordinate = cell.attrib.get('r', '')
            match = re.fullmatch(r'([A-Z]+)([1-9][0-9]*)', coordinate)
            need(match is not None and int(match[2]) == number, 'Exact workbook cell coordinates')
            if match[1] not in ('A', 'B', 'C'):
                continue
            need(match[1] not in cells and cell.find('m:f', NS) is None, 'Unique literal label cell')
            value = cell.find('m:v', NS)
            cells[match[1]] = None
            if value is not None:
                need(cell.get('t') == 's' and value.text is not None, 'Shared-string labels required')
                index = int(value.text)
                need(0 <= index < len(strings), 'Valid shared-string label index')
                cells[match[1]] = strings[index]
        if number == 1:
            need(title is None, 'Unique workbook header'); title = cells
        elif cells.get('A'):
            need(number not in result and set(cells) == {'A', 'B', 'C'}
                 and all(type(v) is str and v for v in cells.values()), 'Complete unique family header')
            result[number] = {'response': cells['A'], 'covariate': cells['B'], 'figure': cells['C']}
    need(title == {'A': 'Response variable', 'B': 'Primary covariate', 'C': 'Figure'}, 'Exact header meanings')
    need(len(result) == 98, 'All ninety-eight published family headers required')
    return result


def assemble(crosswalk, label_rows, configs):
    need(crosswalk.get('schema') == 'findlay-authored-family-crosswalk/v1', 'Authored crosswalk schema')
    mapping = crosswalk['rows']
    need(len(mapping) == 98 and len({x['source_analysis_id'] for x in mapping}) == 98
         and len({x['table1_row'] for x in mapping}) == 98
         and {x['table1_row'] for x in mapping} == set(label_rows), 'Complete bijective 98-row crosswalk')
    need(sum(map(len, configs.values())) == 109, 'All 109 source configurations including drafts')
    unpublished = {(family, i) for family, rows in configs.items()
                   for i, row in enumerate(rows, 1) if row['fstem'] == 'RevFig999'}
    need(len(unpublished) == 15, 'Preserve fifteen excluded source configurations')
    rows = []; selected = set()
    for item in mapping:
        family, selector = item['source_analysis_id'].split(':', 1)
        index = 1 if family == 'fractional_occupancy' else int(selector)
        need(family in configs and 1 <= index <= len(configs[family])
             and (family, index) not in unpublished, 'Existing published configuration')
        selected.add((family, index))
        rows.append({'table1_row': item['table1_row'], **label_rows[item['table1_row']],
                     'source_analysis_id': item['source_analysis_id'],
                     'source_parameters': configs[family][index - 1],
                     'template_source': item['template_source'], 'input_tables': item['input_tables']})
    need(len(selected) == 94 and len(selected | unpublished) == 109, 'Complete published/draft partition')
    metadata = crosswalk['ledger_metadata']
    # Historical field order is deliberate: reproduce the fixed byte contract.
    result = {}
    for key, value in metadata.items():
        result[key] = value
        if key == 'publisher_table_sha256':
            result['rows'] = rows
    return (json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()


def provision(workbook, source_root):
    crosswalk = json.loads(authenticated_file(Path(__file__).with_name('CURATED_CROSSWALK.json'),
                                             CROSSWALK_PIN), object_pairs_hook=unique)
    label_rows = headers(authenticated_file(workbook, WORKBOOK_PIN))
    configs = {}
    for pin in crosswalk['parameter_files']:
        relative = Path(pin['repository_path'])
        need(not relative.is_absolute() and '..' not in relative.parts, 'Relative official source path')
        family = relative.parent.name
        need(family not in configs, 'Unique source family')
        configs[family] = parameters(authenticated_file(source_root / relative,
                                                      (pin['bytes'], pin['sha256'])))
    body = assemble(crosswalk, label_rows, configs)
    need((len(body), hashlib.sha256(body).hexdigest()) == OUTPUT_PIN,
         'Reconstruction differs from fixed ledger; no replacement admitted')
    return body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook', type=Path, required=True)
    parser.add_argument('--official-source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    body = provision(args.workbook, args.official_source_root)
    write_exclusive(args.output, body)
    print(json.dumps({'schema': 'findlay-families-provisioned/v1', 'families': 98,
                      'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
                      'mapping_is_benchmark_authored': True, 'scientifically_qualified': False}, sort_keys=True))


if __name__ == '__main__':
    main()
