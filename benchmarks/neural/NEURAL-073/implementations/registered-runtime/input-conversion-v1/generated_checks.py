"""Generated-only checks: no external evaluator, catalogue or original maps.

Requires the exact packages in requirements.txt. Explicit --evidence names a
new directory for invented fixtures and outputs; never reuse an existing one.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import json
from pathlib import Path
import struct

import catalogue
import convert
from controls import nifti1, oracle_scaled


def run(evidence):
    evidence.mkdir(mode=0o700)
    contract, contract_sha = convert.load_contract()
    limits = dict(original_file_bytes=16384, decompressed_file_bytes=16384,
                  canonical_file_bytes=2048, total_original_bytes=1 << 20,
                  total_canonical_bytes=1 << 20, metadata_output_bytes=2 << 20,
                  max_workspace_bytes=64 << 20, whole_seconds=30)
    results = []

    def equal(name, observed, expected):
        if observed != expected:
            raise AssertionError(name)
        results.append(name)

    def refuses(name, function):
        try:
            function()
        except (convert.ConversionError, catalogue.AdmissionError, OSError, EOFError):
            results.append(name)
            return
        raise AssertionError('expected refusal: '+name)

    raw = nifti1()
    for name, original in [('scaled_C_order', raw),
                           ('big_endian', nifti1(endian='>')),
                           ('gzip', gzip.compress(raw, mtime=0))]:
        equal(name, convert.decode(original, limits, contract)[0], oracle_scaled())
    equal('signed_zero', convert.decode(nifti1(datatype=16, slope=1, intercept=0),
          limits, contract)[0][:8], struct.pack('<d', -0.0))
    decoded, geometry, details = convert.decode(raw, limits, contract)
    equal('unknown_units_preserved', details['spatial_units'], 'unknown')
    equal('sform_orientation', geometry['orientation'], ['L', 'A', 'S'])
    for name, fmt, offset, value in [('zero_offset','f',108,0),
                                    ('fractional_offset','f',108,352.5),
                                    ('qfac_repair','f',76,2),
                                    ('bitpix_repair','h',72,32)]:
        malformed = bytearray(raw)
        struct.pack_into('<'+fmt, malformed, offset, value)
        refuses(name, lambda data=bytes(malformed): convert.decode(data, limits, contract))
    refuses('nonfinite_values', lambda: convert.decode(
        nifti1(datatype=16, nonfinite=True), limits, contract))
    refuses('truncated_values', lambda: convert.decode(raw[:-2], limits, contract))

    # Six invented records exercise the complete same-schema conversion path.
    records = [catalogue.Record('invented:%d'%i, 'invented-person:%d'%(i//2),
        i%2, ('A','B')[i%2], 'AP', 'invented-session', 'invented-source', len(raw))
        for i in range(6)]
    cat = catalogue.invented_catalogue(records, ['A','B'])
    originals = evidence/'invented-originals'
    originals.mkdir(mode=0o700)
    rows = []
    for i, record in enumerate(records):
        name = '%d.nii'%i
        (originals/name).write_bytes(raw)
        rows.append({'record_id':record.record_id,'path':name,
                     'original':{'bytes':len(raw),'sha256':convert.sha(raw)},
                     'source_version':'invented-generated-check-only',
                     'source_locator_digest':'1'*64,'rights_evidence_digest':'2'*64})
    plan = {'schema':'n073_original_conversion_plan_v1','domain':cat.domain,
            'catalogue_digest':cat.fingerprint,'limits':limits,'records':rows}
    output = evidence/'invented-corpus'
    summary = convert.convert_catalogue(cat,plan,originals,output,contract,contract_sha)
    inventory = json.loads((output/'INVENTORY.json').read_bytes())
    equal('complete_invented_roster', {r['record_id'] for r in inventory['records']},
          {r.record_id for r in records})
    equal('invented_domain_only', summary['domain'], catalogue.INVENTED_DOMAIN)
    equal('no_qualification', summary['independent_fidelity_rights_identity_qualification'], False)
    equal('all_six_canonical_arrays', [(output/r['canonical']['path']).read_bytes()
          for r in inventory['records']], [oracle_scaled()]*6)
    refuses('no_destination_reuse', lambda: convert.convert_catalogue(
        cat,plan,originals,output,contract,contract_sha))
    partial = copy.deepcopy(plan)
    partial['records'].pop()
    refuses('incomplete_roster', lambda: convert.validate_plan(partial,cat))
    report = {'schema':'n073_generated_only_controls_v1','passed':len(results),
              'checks':results,'authentic_data_reads':0,'external_evaluator_used':False,
              'scientific_qualification':False}
    (evidence/'GENERATED_CHECKS.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,required=True)
    args = parser.parse_args()
    if not args.evidence.is_absolute():
        parser.error('--evidence must be an absolute path with no symlink ancestors')
    print(json.dumps(run(args.evidence),sort_keys=True))


if __name__ == '__main__':
    main()
