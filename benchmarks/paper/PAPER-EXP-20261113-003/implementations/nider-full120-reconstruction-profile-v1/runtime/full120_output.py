"""Owner-only bridge; existing validators/scorers remain byte-identical.

Original full120 reporting plus the existing four-case12 computation check.
This module contains no numerical reference values and never runs at import.
"""
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import extended_score
import reporting_core
from custody import need, read_pin

PROFILE = 'nider-full120-original-with-existing12-procedure-v1'
ORIGINAL = 'ef13337351bac9f9fd10d693a81f768633a87a62c8742ad3279528b7f7667498'

def encode_exact(value):
    if isinstance(value, Decimal):
        need(value.is_finite(), 'finite_json_decimal')
        return str(value)
    if value is None or type(value) in (str, int, bool):return json.dumps(value)
    if type(value) is list:return '['+','.join(encode_exact(x) for x in value)+']'
    if type(value) is dict:
        return '{'+','.join(json.dumps(k)+':'+encode_exact(v) for k,v in value.items())+'}'
    raise ValueError('exact_json_type')

def canonical_input(case):
    # The original projection is authenticated separately from its source XLSX.
    # A derivative has its own identity, never a forged original identity.
    return ORIGINAL if case['kind']=='original' else case['workbook']['sha256']

def normalize(raw, case, arm):
    need(type(raw) is bytes and len(raw)<=65536, 'full120_response_extent')
    doc=reporting_core.decode_numeric_json(raw)
    validated=extended_score.validate(doc, arm, canonical_input(case))
    rows=[]
    for contrast in ('amy_self','quest_self','amy_quest'):
        record,_=validated[contrast]
        names={'pearson_r':'random_r_estimate','p_two_sided':'random_z_p',
               'k':'k','N':'N_author_sum'}
        fields={}
        for target,source in names.items():
            cell=record['fields'][source]
            need(cell['state']=='finite', 'procedure_projection_requires_finite_value')
            fields[target]=cell['value']
        rows.append({'contrast':contrast,'fields':fields})
    legacy={'schema':'nider_scientific_case_response_v1','case_id':case['case_id'],
            'workbook_sha256':case['workbook']['sha256'],'rows':rows}
    # No tanh, fit or rounding occurs here: project the submitted named values.
    return (encode_exact(legacy)+'\n').encode()

