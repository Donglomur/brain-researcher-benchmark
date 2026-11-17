"""Recover published Figure 5b aggregate results; never read person-level data."""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

SOURCE_URL = ('https://static-content.springer.com/esm/art%3A10.1038%2F'
              's41586-026-11203-1/MediaObjects/41586_2026_11203_MOESM10_ESM.xlsx')
SOURCE_BYTES = 13647
SOURCE_SHA256 = 'fcd1e3d83241fa84d2327d0d97ffe5feaf218160377914b6be2bc0186b427410'
SHEET = 'Fig5b'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
HEADERS = ('outcome', 'signature', 'study', 'estimate', 'conf.low', 'conf.high')
OUTCOMES = ('Trait questionnaire', 'Task-based affective rating')
SUPPORT = {
    'Negative Affect Decoder': ('Average', 'Study 2', 'Study 3', 'Study 4'),
    'Reappraisal Ability Decoder': ('Average', 'Study 1', 'Study 3', 'Study 4'),
    'Reappraisal State Decoder': ('Average', 'Study 1', 'Study 2', 'Study 3', 'Study 4'),
}


class SourceError(ValueError):
    """The supplied source does not match the original complete panel."""


def _number(text: str) -> Decimal:
    # The official workbook stores decimal-comma quantities as text. A comma
    # here is a decimal separator, never a thousands separator.
    if not re.fullmatch(r'[+-]?\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?', text):
        raise SourceError(f'Invalid published decimal: {text!r}')
    try:
        value = Decimal(text.replace(',', '.'))
    except InvalidOperation as exc:
        raise SourceError('Invalid decimal') from exc
    if not value.is_finite():
        raise SourceError('Non-finite published value')
    return value


def _label(text: str) -> str:
    return ' '.join(text.replace('_x000D_', '\r').split())


def validate_rows(rows: list[tuple[int, list[str]]]) -> list[dict]:
    """Validate all 26 source rows, retaining original strings and locations."""
    if not rows or rows[0] != (1, list(HEADERS)):
        raise SourceError('Expected the exact Fig5b six-column header at row 1')
    expected = {(outcome, signature, study) for signature, studies in SUPPORT.items()
                for outcome in OUTCOMES for study in studies}
    found = set()
    recovered = []
    for row_number, cells in rows[1:]:
        if len(cells) != 6:
            raise SourceError('Each Fig5b row must contain exactly six cells')
        outcome, signature, study = map(_label, cells[:3])
        key = (outcome, signature, study)
        if key not in expected:
            raise SourceError(f'Unexpected decoder/outcome/study support: {key!r}')
        if key in found:
            raise SourceError(f'Duplicate decoder/outcome/study: {key!r}')
        found.add(key)
        estimate, lower, upper = map(_number, cells[3:])
        if not Decimal(-1) <= estimate <= Decimal(1):
            raise SourceError('Correlation estimate outside [-1, 1]')
        if not lower <= estimate <= upper:
            raise SourceError('Confidence interval does not contain its estimate')
        recovered.append({
            'outcome': outcome, 'signature': signature, 'study': study,
            'aggregation': 'pooled_people' if study == 'Average' else 'within_study',
            'estimate_decimal': str(estimate),
            'conf_low_decimal': str(lower), 'conf_high_decimal': str(upper),
            'source_range': f'{SHEET}!A{row_number}:F{row_number}',
            'source_cell_text': dict(zip(HEADERS, cells)),
        })
    if found != expected:
        raise SourceError(f'Incomplete original panel: missing {sorted(expected - found)!r}')
    return recovered


def _read_rows(blob: bytes) -> list[tuple[int, list[str]]]:
    """Read only the named aggregate sheet from the pinned OOXML source."""
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise SourceError('Duplicate ZIP members')
        if sum(i.file_size for i in archive.infolist()) > 2 * 1024**2:
            raise SourceError('Unexpected expanded source size')
        workbook = ET.fromstring(archive.read('xl/workbook.xml'))
        sheets = [s for s in workbook.findall('s:sheets/s:sheet', NS)
                  if s.get('name') == SHEET]
        if len(sheets) != 1:
            raise SourceError('Expected exactly one Fig5b sheet')
        relid = sheets[0].get(f'{{{REL_NS}}}id')
        rels = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        selected = [r for r in rels if r.get('Id') == relid]
        if (len(selected) != 1 or selected[0].get('TargetMode') == 'External'
                or selected[0].get('Target') != 'worksheets/sheet2.xml'):
            raise SourceError('Unexpected Fig5b worksheet relationship')
        strings = []
        if 'xl/sharedStrings.xml' in names:
            strings = [''.join(e.text or '' for e in item.iter(f'{{{NS["s"]}}}t'))
                       for item in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
        sheet = ET.fromstring(archive.read('xl/worksheets/sheet2.xml'))
        rows = []
        for row in sheet.findall('s:sheetData/s:row', NS):
            row_number = int(row.attrib['r'])
            if row_number != len(rows) + 1:
                raise SourceError('Missing, repeated or reordered worksheet row')
            cells = {}
            for cell in row.findall('s:c', NS):
                address = cell.attrib['r']
                if address in cells or address not in {f'{c}{row_number}' for c in 'ABCDEF'}:
                    raise SourceError('Duplicate or unexpected cell address')
                if cell.find('s:f', NS) is not None:
                    raise SourceError('Cached formula values cannot stand in for source values')
                value = cell.find('s:v', NS)
                kind = cell.get('t', 'n')
                if kind == 's':
                    if value is None:
                        raise SourceError('Missing shared-string index')
                    index = int(value.text)
                    if not 0 <= index < len(strings):
                        raise SourceError('Shared-string index out of bounds')
                    text = strings[index]
                elif kind == 'inlineStr':
                    text = ''.join(e.text or '' for e in cell.iter(f'{{{NS["s"]}}}t'))
                elif kind in ('n', 'str') and value is not None:
                    text = value.text or ''
                else:
                    raise SourceError('Missing or unsupported source cell')
                cells[address] = text
            if set(cells) != {f'{c}{row_number}' for c in 'ABCDEF'}:
                raise SourceError('Missing Fig5b cell')
            rows.append((row_number, [cells[f'{c}{row_number}'] for c in 'ABCDEF']))
        return rows


def recover(source: Path) -> dict:
    if source.stat().st_size != SOURCE_BYTES:
        raise SourceError('Source workbook byte count differs from the official snapshot')
    blob = source.read_bytes()
    if hashlib.sha256(blob).hexdigest() != SOURCE_SHA256:
        raise SourceError('Source workbook SHA-256 differs from the official snapshot')
    records = validate_rows(_read_rows(blob))
    return {
        'schema': 'nider-published-fig5b-reference/v1',
        'task_id': 'PAPER-EXP-20261113-003',
        'qualification': 'published_aggregate_reference_recovered',
        'source': {'url': SOURCE_URL, 'bytes': SOURCE_BYTES, 'sha256': SOURCE_SHA256,
                   'sheet': SHEET, 'range': 'A1:F27'},
        'metric': 'signed between-person association reported for Figure 5b',
        'interval': 'published uncorrected two-sided 95% confidence limits',
        'record_count': len(records),
        'pooled_count': sum(r['study'] == 'Average' for r in records),
        'study_count': sum(r['study'] != 'Average' for r in records),
        'records': records,
        'limits': [
            'Extraction is not an author-model rerun, candidate result or scientific reproduction.',
            'The Average rows are pooled person-level results, not equal-weight study means.',
            'Participant identities, per-pair missingness, beta images and decoder weights are absent.',
            'No per-pair sample sizes or p-values are inferred from this workbook.',
            'No sign flip, absolute-value score, composite, superiority margin or decision is defined.',
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        parser.error('Output must not overwrite the immutable source workbook')
    result = recover(args.source)
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write('\n')
    print(json.dumps({k: result[k] for k in
                      ('qualification', 'record_count', 'pooled_count', 'study_count')}))


if __name__ == '__main__':
    main()
