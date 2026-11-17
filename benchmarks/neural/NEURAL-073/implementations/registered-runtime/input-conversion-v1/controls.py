"""Independent invented-image controls; never reads authentic signal bodies."""
import argparse
import copy
import gzip
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import sys
import time
from unittest.mock import patch

sys.dont_write_bytecode = True
import catalogue
import convert


def nifti1(*, endian='<', datatype=4, slope=2.0, intercept=-3.0,
           units=0, scode=2, qcode=1, dims=3, nonfinite=False):
    """Hand-encoded NIfTI-1 fixture, independent of the tested decoder/writer."""
    header = bytearray(352)
    def pack(fmt, offset, *values):
        struct.pack_into(endian+fmt, header, offset, *values)
    pack('i', 0, 348)
    pack('8h', 40, dims, 4, 4, 16, 1, 1, 1, 1)
    pack('h', 70, datatype)
    pack('h', 72, 16 if datatype == 4 else 32)
    pack('8f', 76, 1, 2, 3, 4, 1, 1, 1, 1)
    pack('f', 108, 352)
    pack('2f', 112, slope, intercept)
    pack('B', 123, units)
    pack('2h', 252, qcode, scode)
    pack('3f', 268, 10, 20, 30)
    pack('4f', 280, -2, 0, 0, 10)
    pack('4f', 296, 0, 3, 0, 20)
    pack('4f', 312, 0, 0, 4, 30)
    header[344:348] = b'n+1\0'
    # NIfTI file order is x fastest. Expected canonical order is z fastest.
    vals = list(range(256))
    if datatype != 4:
        vals = [float(v) for v in vals]
        vals[0] = float('nan') if nonfinite else -0.0
    return bytes(header)+struct.pack(endian+('256h' if datatype == 4 else '256f'), *vals)


def oracle_scaled():
    return b''.join(struct.pack('<d', 2*(x+4*(y+4*z))-3)
                    for x in range(4) for y in range(4) for z in range(16))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--evidence', type=Path, required=True)
    ap.add_argument('--existing-package', type=Path, required=True)
    args = ap.parse_args()
    args.evidence.mkdir(mode=0o700)
    contract, contract_sha = convert.load_contract()
    limits = dict(original_file_bytes=16384, decompressed_file_bytes=16384,
                  canonical_file_bytes=2048, total_original_bytes=1 << 20,
                  total_canonical_bytes=1 << 20, metadata_output_bytes=2 << 20,
                  max_workspace_bytes=64 << 20, whole_seconds=30)
    results = []
    def check(name, f):
        f()
        results.append({'name': name, 'passed': True})
    def equal(a, b):
        assert a == b, (a, b)
    def refuse(f):
        try:
            f()
        except (ValueError, OSError, EOFError):
            return
        raise AssertionError('expected refusal')
    def decoded(raw, lim=None, c=None):
        return convert.decode(raw, limits if lim is None else lim, contract if c is None else c)

    raw = nifti1()
    out, geometry, evidence = decoded(raw)
    check('scaled_values_C_order_independent_byte_oracle', lambda: equal(out, oracle_scaled()))
    check('big_endian_same_canonical', lambda: equal(decoded(nifti1(endian='>'))[0], oracle_scaled()))
    check('gzip_same_canonical', lambda: equal(decoded(gzip.compress(raw, mtime=0))[0], oracle_scaled()))
    check('sform_precedence_and_full_geometry', lambda: equal(geometry,
          {'shape': [4,4,16], 'affine': [-2.,0.,0.,10.,0.,3.,0.,20.,0.,0.,4.,30.,0.,0.,0.,1.],
           'orientation': ['L','A','S']}))
    check('qform_disagreement_preserved', lambda: equal(evidence['qform'][0], 2.0))
    check('unknown_units_preserved', lambda: equal(evidence['spatial_units'], 'unknown'))
    check('qform_only_used_when_sform_uncoded', lambda: equal(decoded(nifti1(scode=0))[2]['selected_affine'], 'qform'))
    zeros = decoded(nifti1(datatype=16, slope=1, intercept=0))[0]
    check('negative_zero_preserved', lambda: equal(zeros[:8], struct.pack('<d', -0.0)))
    import numpy as np
    import nibabel as nib
    n2 = nib.Nifti2Image(np.arange(256,dtype=np.float64).reshape((4,4,16),order='C'), np.eye(4))
    n2.header.set_xyzt_units('mm')
    n2bytes = n2.to_bytes()
    check('NIfTI2_real_reader_full_values', lambda: equal(decoded(n2bytes)[0], struct.pack('<256d', *range(256))))
    check('nonfinite_signal_refused', lambda: refuse(lambda: decoded(nifti1(datatype=16, nonfinite=True))))
    check('truncated_voxels_refused', lambda: refuse(lambda: decoded(raw[:-2])))
    check('four_dimensional_even_singleton_refused', lambda: refuse(lambda: decoded(nifti1(dims=4))))
    check('uncoded_affine_refused', lambda: refuse(lambda: decoded(nifti1(scode=0, qcode=0))))
    bad = bytearray(raw); bad[344:348] = b'ni1\0'
    check('paired_NIfTI_refused', lambda: refuse(lambda: decoded(bytes(bad))))
    bad = bytearray(raw); struct.pack_into('<h',bad,70,32)
    check('complex_voxels_refused', lambda: refuse(lambda: decoded(bytes(bad))))
    bad = bytearray(raw); struct.pack_into('<f',bad,280,0)
    check('singular_affine_refused', lambda: refuse(lambda: decoded(bytes(bad))))
    cap = dict(limits, decompressed_file_bytes=512)
    check('gzip_expansion_cap', lambda: refuse(lambda: decoded(gzip.compress(raw), cap)))
    cap = dict(limits, canonical_file_bytes=1024)
    check('canonical_extent_cap', lambda: refuse(lambda: decoded(raw, cap)))
    cap = dict(limits, max_workspace_bytes=1024)
    check('workspace_admission_before_expansion', lambda: refuse(lambda: decoded(raw, cap)))
    c = copy.deepcopy(contract); c['runtime_versions']['nibabel']='0.invalid'
    check('runtime_version_mismatch_refused', lambda: refuse(lambda: decoded(raw, c=c)))
    for name, fmt, offset, value in [
            ('zero_payload_offset_refused','f',108,0),
            ('fractional_payload_offset_refused','f',108,352.5),
            ('qfac_repair_refused','f',76,2),
            ('negative_pixdim_repair_refused','f',80,-2),
            ('datatype_bitpix_repair_refused','h',72,32)]:
        malformed = bytearray(raw); struct.pack_into('<'+fmt,malformed,offset,value)
        check(name, lambda b=bytes(malformed): refuse(lambda: decoded(b)))
    malformed = bytearray(raw); malformed[348]=1
    check('extension_flag_without_extent_refused', lambda: refuse(lambda: decoded(bytes(malformed))))
    extended = bytearray(raw[:352])+struct.pack('<ii8s',16,6,b'invented')+raw[352:]
    extended[348]=1;struct.pack_into('<f',extended,108,368)
    check('valid_extension_preserves_payload', lambda: equal(decoded(bytes(extended))[0],oracle_scaled()))
    struct.pack_into('<i',extended,352,32)
    check('extension_overlaps_payload_refused', lambda: refuse(lambda: decoded(bytes(extended))))

    records = [catalogue.Record('invented:%d'%i, 'invented-person:%d'%(i//2),
               i%2, ('A','B')[i%2], 'AP', 'invented-session', 'invented-source', len(raw))
               for i in range(6)]
    cat = catalogue.invented_catalogue(records, ['A','B'])
    originals = args.evidence/'invented-originals'; originals.mkdir(mode=0o700)
    rows = []
    for i, r in enumerate(records):
        p = originals/('%d.nii'%i); p.write_bytes(raw)
        rows.append({'record_id': r.record_id, 'path': p.name,
                     'original': {'bytes': len(raw), 'sha256': convert.sha(raw)},
                     'source_version': 'invented-control-only',
                     'source_locator_digest': '1'*64, 'rights_evidence_digest': '2'*64})
    plan = {'schema':'n073_original_conversion_plan_v1','domain':cat.domain,
            'catalogue_digest':cat.fingerprint,'limits':limits,'records':rows}
    output = args.evidence/'complete-invented-corpus'
    summary = convert.convert_catalogue(cat,plan,originals,output,contract,contract_sha)
    inventory = json.loads((output/'INVENTORY.json').read_bytes())
    check('complete_invented_corpus_six_rows', lambda: equal(summary['records'],6))
    check('invented_domain_not_promoted', lambda: equal(summary['domain'],catalogue.INVENTED_DOMAIN))
    check('no_qualification_from_conversion', lambda: equal(summary['independent_fidelity_rights_identity_qualification'],False))
    check('fresh_destination_no_reuse', lambda: refuse(lambda: convert.convert_catalogue(cat,plan,originals,output,contract,contract_sha)))
    impossible = copy.deepcopy(plan);impossible['limits']['max_workspace_bytes']=1024
    with patch.object(convert,'read_pinned',side_effect=AssertionError('signal read before workspace admission')):
        check('whole_workspace_refusal_before_original_read',lambda: refuse(lambda:
              convert.convert_catalogue(cat,impossible,originals,args.evidence/'no-read',contract,contract_sha)))
    late = args.evidence/'late-inventory-write-failure'
    writer = convert._write
    def fail_after_inventory_write(fd,name,body):
        writer(fd,name,body)
        if name == 'INVENTORY.pending.json':
            raise OSError('invented post-write fsync/close failure')
    with patch.object(convert,'_write',side_effect=fail_after_inventory_write):
        check('late_inventory_write_failure_observed',lambda: refuse(lambda:
              convert.convert_catalogue(cat,plan,originals,late,contract,contract_sha)))
    check('late_failure_has_staged_body_but_no_final_inventory',lambda: equal(
          ((late/'INVENTORY.pending.json').is_file(),(late/'FAILURE.json').is_file(),
           (late/'INVENTORY.json').exists()),(True,True,False)))
    missing = copy.deepcopy(plan); missing['records'].pop()
    check('missing_record_refused', lambda: refuse(lambda: convert.validate_plan(missing,cat)))
    duplicate = copy.deepcopy(plan); duplicate['records'][-1]=duplicate['records'][0]
    check('duplicate_record_refused', lambda: refuse(lambda: convert.validate_plan(duplicate,cat)))
    badpath = copy.deepcopy(plan); badpath['records'][0]['path']='../escape.nii'
    check('path_escape_refused', lambda: refuse(lambda: convert.validate_plan(badpath,cat)))
    badpin = dict(rows[0]['original'],sha256='0'*64)
    check('original_hash_refused', lambda: refuse(lambda: convert.read_pinned(originals,'0.nii',badpin,16384)))
    (originals/'link.nii').symlink_to('0.nii')
    check('symlink_original_refused', lambda: refuse(lambda: convert.read_pinned(originals,'link.nii',rows[0]['original'],16384)))
    mixed = nifti1(units=2); (originals/'5.nii').write_bytes(mixed)
    failplan = copy.deepcopy(plan); failplan['records'][5]['original']={'bytes':len(mixed),'sha256':convert.sha(mixed)}
    failed = args.evidence/'mixed-units-failure'
    check('mixed_units_refused', lambda: refuse(lambda: convert.convert_catalogue(cat,failplan,originals,failed,contract,contract_sha)))
    check('failure_preserved_without_full_inventory', lambda: equal(((failed/'FAILURE.json').is_file(),(failed/'INVENTORY.json').exists()),(True,False)))

    # Use actual current source parser, not a reimplementation of its schema.
    spec = importlib.util.spec_from_file_location('n073_existing', args.existing_package/'__init__.py',
                     submodule_search_locations=[str(args.existing_package)])
    mod = importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
    existing = importlib.import_module('n073_existing.corpus')
    g = existing.admission.Geometry(**summary['geometry'])
    entries, receipts = existing._parse_inventory(inventory,cat,g,
                         {'per_file_bytes':2048,'total_read_bytes':6*2048})
    check('current_corpus_parser_accepts_exact_inventory', lambda: equal((len(entries),len(receipts)),(6,6)))
    for entry in entries.values():
        equal((output/entry['path']).read_bytes(),oracle_scaled())
    check('every_canonical_file_independent_oracle', lambda: equal(len(entries),6))

    # Metadata-only whole authentic roster coverage: no original bodies opened.
    full = convert.load_catalogue(args.existing_package/'static/catalogue', contract)
    fullrows = [dict(rows[0],record_id=r.record_id,path='not-opened/'+r.record_id+'.nii') for r in full.records]
    full_limits = dict(limits,total_original_bytes=len(fullrows)*len(raw),
                      total_canonical_bytes=len(fullrows)*2048,metadata_output_bytes=len(fullrows)*8192+(1<<20))
    full_plan = dict(plan,domain=full.domain,catalogue_digest=full.fingerprint,
                     records=fullrows,limits=full_limits)
    check('full9532_source_metadata_roster_admission', lambda: equal(len(convert.validate_plan(full_plan,full)[0]),9532))
    check('full13people25protocols300cells',lambda: equal((len(full.people),len(full.label_order),len(full.cell_counts)),(13,25,300)))
    full_plan['records'] = fullrows[:-1]
    check('9531_subset_refused_before_any_data_read', lambda: refuse(lambda: convert.validate_plan(full_plan,full)))
    report = {'schema':'n073_conversion_controls_v1','domain':'invented_images_and_public_source_metadata_only',
              'controls':results,'passed':len(results),'authentic_signal_bodies_read':0,
              'fits':0,'Docker_API_calls':0,'scientific_qualification':False,
              'complete_authentic_conversion_executed':False}
    report['source_pins'] = {name:{'bytes':len(body),'sha256':convert.sha(body)}
        for name in ('convert.py','controls.py','catalogue.py','CONTRACT.json','README.md','requirements.txt')
        for body in [Path(__file__).with_name(name).read_bytes()]}
    (args.evidence/'CONTROLS.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'passed':len(results),'report':str(args.evidence/'CONTROLS.json')},sort_keys=True))


if __name__ == '__main__':
    main()
