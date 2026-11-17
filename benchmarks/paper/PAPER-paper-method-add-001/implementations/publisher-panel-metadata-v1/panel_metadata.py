"""Prepare the original NoMAD monkey-panel identities from publisher source data.

This independently written standard-library reader extracts identity columns,
not predictions, behavior, R2 values or statistics. The command admits exactly
the published workbook; the parser also accepts generated workbooks for tests.
No author software is imported or copied.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

PUBLISHED_URL = ('https://pmc-oa-opendata.s3.amazonaws.com/PMC12089531.1/'
                 '41467_2025_59652_MOESM4_ESM.xlsx?md5=93d1ffcae2bf540a9bbe474f502a72a4')
PUBLISHED_BYTES = 3077326
PUBLISHED_SHA256 = '58c45c042767ffeda0c03e34446656dc3ddb7994a52c157436d0c8a6adfd7ab4'
METHODS = ('NoMAD (causal)', 'Aligned FA', 'ADAN', 'Static decoder')
PANELS = {'Figure 3': ('force', 20, 95), 'Figure 4': ('reaching', 12, 38)}
HEADERS = ('Task', 'Day 0 Dataset', 'Day K Dataset', 'Method', 'R2')
S = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
MAX_ARCHIVE_BYTES = 4 * 1024**2
MAX_MEMBER_BYTES = 32 * 1024**2
MAX_EXPANDED_BYTES = 96 * 1024**2
CELL = re.compile(r'([A-Z]+)([1-9][0-9]*)\Z')
DAY = re.compile(r'(0|[1-9][0-9]*)(?:\.0+)?\Z')


class InvalidSource(ValueError):
    """The supplied package cannot produce this complete identity roster."""


def require(condition, message):
    if not condition:
        raise InvalidSource(message)


def byte_pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def _xml(raw):
    require(len(raw) <= MAX_MEMBER_BYTES, 'XML member exceeds its byte limit')
    require(b'<!DOCTYPE' not in raw.upper() and b'<!ENTITY' not in raw.upper(),
            'XML declarations are not accepted')
    try:
        return ET.fromstring(raw)
    except ET.ParseError as exc:
        raise InvalidSource('invalid source XML') from exc


def _cell_text(cell, strings):
    require(cell.find(S + 'f') is None, 'formula in identity/header column')
    value = cell.find(S + 'v')
    require(value is not None and value.text is not None, 'missing identity/header value')
    text = value.text
    if cell.get('t') == 's':
        require(text.isdigit() and int(text) < len(strings), 'invalid shared-string index')
        return strings[int(text)]
    require(cell.get('t') in (None, 'n'), 'unexpected identity/header cell type')
    return text


def _day(text):
    require(type(text) is str and len(text) <= 12 and DAY.fullmatch(text),
            'session day must be an exact nonnegative integer label')
    return int(text.split('.')[0])


def _panel(sheet, strings, sheet_name):
    task, session_count, span = PANELS[sheet_name]
    data = sheet.find(S + 'sheetData')
    require(data is not None, 'missing worksheet rows')
    source_rows = list(data)
    expected = len(METHODS) * session_count**2
    require(len(source_rows) == expected + 1, 'complete panel row count required')
    parsed = []
    empty_style_cells = []
    for position, row in enumerate(source_rows, 1):
        require(row.tag == S + 'row' and row.get('r') == str(position),
                'source rows must be complete, unique and ordered')
        cells = {}
        seen_columns = set()
        for cell in row:
            match = CELL.fullmatch(cell.get('r', ''))
            require(cell.tag == S + 'c' and match is not None
                    and int(match.group(2)) == position, 'invalid source cell address')
            column = match.group(1)
            require(column not in seen_columns, 'duplicate source column')
            seen_columns.add(column)
            if column not in set('ABCDE'):
                # The authenticated Figure 3 header has 21 styled, empty F:Z
                # cells. Retain their addresses, but refuse any populated extra
                # column instead of dropping a potentially meaningful field.
                require(len(cell) == 0 and cell.text in (None, '')
                        and set(cell.attrib) <= {'r', 's'},
                        'unexpected populated source column')
                empty_style_cells.append(cell.get('r'))
                continue
            cells[column] = cell
        require(set(cells) == set('ABCDE'), 'complete source A:E row required')
        if position == 1:
            require(tuple(_cell_text(cells[c], strings) for c in 'ABCDE') == HEADERS,
                    'original panel headers required')
            continue
        # E contains published results. Do not decode, coerce, retain or return
        # its value. Existence alone binds the identity row to the source table.
        labels = {c: _cell_text(cells[c], strings) for c in 'ABCD'}
        require(labels['A'] == task and labels['D'] in METHODS,
                'panel task and literal method must match the source')
        reference = _day(labels['B'])
        query = None if labels['C'] == 'None' else _day(labels['C'])
        require(query is None or query != reference, 'transfer cannot be a diagonal')
        parsed.append({'source_row': position, 'method': labels['D'],
                       'reference_day': reference, 'query_day': query,
                       'source_reference_label': labels['B'],
                       'source_query_label': labels['C'],
                       'role': 'null_query_anchor' if query is None else 'transfer'})

    days = sorted({r['reference_day'] for r in parsed})
    require(len(days) == session_count and days[0] == 0 and days[-1] == span,
            'original number of sessions and full time span required')
    expected_edges = {(a, b) for a in days for b in days if a != b}
    all_edges = {}
    anchors = {}
    per_method = {}
    for method in METHODS:
        rows = [r for r in parsed if r['method'] == method]
        transfers = [r for r in rows if r['query_day'] is not None]
        within = [r for r in rows if r['query_day'] is None]
        edges = {(r['reference_day'], r['query_day']) for r in transfers}
        require(len(transfers) == len(edges) == session_count*(session_count-1)
                and edges == expected_edges, 'every directed pair exactly once per method')
        require(len(within) == session_count
                and {r['reference_day'] for r in within} == set(days),
                'one null-query anchor per session and method')
        per_method[method] = {'transfer_rows': len(transfers), 'anchor_rows': len(within)}
        for row in transfers:
            key = (row['reference_day'], row['query_day'])
            all_edges.setdefault(key, {})[method] = row['source_row']
        for row in within:
            anchors.setdefault(row['reference_day'], {})[method] = row['source_row']
    # These are source-relative coordinates. They are deliberately not invented
    # recording filenames, trial IDs or final-evaluation support identities.
    pairs = [{'reference_day': a, 'query_day': b, 'signed_day_gap': b-a,
              'absolute_day_gap': abs(b-a), 'source_rows_by_method': all_edges[(a, b)]}
             for a, b in sorted(expected_edges)]
    return {'sheet': sheet_name, 'task': task, 'session_days': days,
            'session_identity_kind': 'publisher_relative_day_label',
            'source_data_rows': expected, 'methods': list(METHODS),
            'empty_style_cells': empty_style_cells,
            'per_method': per_method, 'directed_pairs': pairs,
            'null_query_anchors': [{'reference_day': d, 'source_query_label': 'None',
                                    'source_rows_by_method': anchors[d]} for d in days],
            'source_order_rows': parsed,
            'one_day_directed_pair_count': sum(p['absolute_day_gap'] == 1 for p in pairs),
            'one_day_pair_interpretation': 'calendar-derived subset; not a row join to Supplementary Figure 7'}


def parse_workbook(raw):
    """Extract complete identity panels, without authenticating their provenance.

    Useful for generated fixture tests; use prepare_source_roster for the
    independently pinned publisher body. Package bytes include scores, but
    score cells are never numerically interpreted, extracted or reported.
    """
    require(type(raw) is bytes and 0 < len(raw) <= MAX_ARCHIVE_BYTES,
            'bounded XLSX bytes required')
    try:
        package = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise InvalidSource('invalid XLSX package') from exc
    with package:
        infos = package.infolist()
        names = [item.filename for item in infos]
        require(len(names) <= 256 and len(names) == len(set(names)),
                'bounded package with no duplicate ZIP members')
        require(sum(item.file_size for item in infos) <= MAX_EXPANDED_BYTES
                and all(item.file_size <= MAX_MEMBER_BYTES and not item.flag_bits & 1 for item in infos),
                'unencrypted bounded expanded package')
        member_pins = {}

        def member(name):
            require(name in names, 'required workbook member missing')
            body = package.read(name)
            member_pins[name] = byte_pin(body)
            return _xml(body)

        shared = member('xl/sharedStrings.xml')
        strings = [''.join(node.itertext()) for node in shared.findall(S + 'si')]
        workbook = member('xl/workbook.xml')
        relationships = member('xl/_rels/workbook.xml.rels')
        links = {}
        for rel in relationships:
            identifier = rel.get('Id')
            require(identifier and identifier not in links, 'unique workbook relationship IDs')
            links[identifier] = rel
        sheets = workbook.find(S + 'sheets')
        require(sheets is not None, 'workbook sheet listing required')
        selected = {}
        sheet_names = []
        for sheet in sheets:
            name = sheet.get('name')
            require(name and name not in sheet_names, 'unique worksheet names')
            sheet_names.append(name)
            if name not in PANELS:
                continue
            rel = links.get(sheet.get(R + 'id'))
            require(rel is not None and rel.get('TargetMode', 'Internal') == 'Internal'
                    and rel.get('Type') == R[1:-1] + '/worksheet', 'internal worksheet relation required')
            target = rel.get('Target', '')
            require(re.fullmatch(r'worksheets/sheet[1-9][0-9]*\.xml', target) is not None,
                    'ordinary worksheet member required')
            selected[name] = _panel(member('xl/' + target), strings, name)
        require(set(selected) == set(PANELS), 'both original monkey panels required')
    return {'schema': 'nomad_publisher_panel_metadata_v1',
            'source_pin': byte_pin(raw), 'member_pins': member_pins,
            'published_source_authenticated': False,
            'panels': selected, 'other_sheets_not_processed': [n for n in sheet_names if n not in PANELS],
            'scope': 'source identity preparation only; no scientific scores or benchmark result',
            'remaining_joins': ['relative days to authentic recording IDs and file hashes',
                               'original channel, event, bin, train/validation and evaluation row identities',
                               'author model, decoder and adaptation lineage',
                               'complete supplementary and human obligations']}


def prepare_source_roster(path):
    path = Path(path)
    require(path.stat().st_size == PUBLISHED_BYTES, 'exact published workbook byte length required')
    with path.open('rb') as handle:
        raw = handle.read(PUBLISHED_BYTES + 1)
    require(byte_pin(raw) == {'bytes': PUBLISHED_BYTES, 'sha256': PUBLISHED_SHA256},
            'exact published workbook SHA-256 required')
    result = parse_workbook(raw)
    result['published_source_authenticated'] = True
    result['source_url'] = PUBLISHED_URL
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True,
                        help='new operator-owned JSON file outside the repository')
    args = parser.parse_args()
    result = prepare_source_roster(args.workbook)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write('\n')
    print(json.dumps({'qualification': 'publisher_metadata_only',
                      'panels': {n: {'sessions': len(p['session_days']),
                                     'directed_pairs': len(p['directed_pairs']),
                                     'source_data_rows': p['source_data_rows']}
                                 for n, p in result['panels'].items()}}))


if __name__ == '__main__':
    main()
