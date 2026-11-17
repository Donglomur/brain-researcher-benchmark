"""Regenerate evaluator-local schema and click metadata from the exact local NWBs.

No download or native import occurs at module import. The explicit command is a
future authenticated-data operation and needs a separately bounded execution.
It hashes every source on the same descriptor before minimal metadata and click
reads. No spike/index values, response arrays or images are decoded here. The
later counting stage authenticates the full sources again: two passes, not one.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runtime_io
import prepare_counts
import metadata_source

CONTRACT_PINS = {
    'SOURCES.json': '320eb843e01353ce59936393df37dd9eda1d12150f9fc9fc66f48aa968dc9966',
    'DECLARED_SUPPORT.json': '35a59c971f015b2b58d923098be21ff208fd889e7fbbe7dd6af233afa38b5e8b',
    'COHORT_BINDING.json': '87f7087dce132a08d4edbc89ab0f982f0672c2bc8f89e29fd2ee40fda5e575eb',
    'PROTOCOL.json': '9d76c4d149b2a99c2609225d511c720607f77f547d3b3aae0cfe50dd2fe71a7a',
}
RUNTIME = {'h5py':'3.13.0', 'hdf5':'1.14.6', 'numpy':'2.2.6'}
MAX_DOCUMENT_BYTES = 1048576
MAX_OUTPUT_BYTES = 2359296


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=True, allow_nan=False)+'\n').encode('utf-8')


def read_contract(package_root):
    """Authenticate the immutable scientific contract before any native import."""
    folder = Path(package_root) / 'contract'
    values = {name: runtime_io._read_pinned_json(folder/name, sha)
              for name,sha in CONTRACT_PINS.items()}
    plan = runtime_io.inspection_plan(values['SOURCES.json'], values['DECLARED_SUPPORT.json'],
                                     sources_sha256=CONTRACT_PINS['SOURCES.json'])
    return values, plan


def inspect_asset(root_fd, planned, source_entry, declared, h5api):
    """Authenticated same-descriptor metadata read; also fake-object testable."""
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, 'O_CLOEXEC', 0)
    fd = os.open(planned['basename'], flags, dir_fd=root_fd)
    with os.fdopen(fd, 'rb') as source:
        before = os.fstat(source.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size == planned['bytes'],
                'Source must have its exact authenticated regular-file extent')
        digest, consumed = hashlib.sha256(), 0
        while True:
            chunk = source.read(min(1048576, planned['bytes']-consumed+1))
            if not chunk:
                break
            consumed += len(chunk)
            require(consumed <= planned['bytes'], 'Source grew during authentication')
            digest.update(chunk)
        require(consumed == planned['bytes'] and digest.hexdigest() == planned['sha256'],
                'Complete source SHA-256 mismatch')
        signature = runtime_io._file_signature
        require(signature(before) == signature(os.fstat(source.fileno())),
                'Source changed during authentication')
        source.seek(0)
        with h5api.File(source, 'r', rdcc_nbytes=1048576) as handle:
            asset = metadata_source.read_metadata(handle, h5api=h5api,
                                                  source=source_entry, declared=declared)
            ids, starts, stops = runtime_io.read_trial_columns(
                handle, h5api=h5api, expected_rows=planned['expected_rows'])
        require(signature(before) == signature(os.fstat(source.fileno())),
                'Source changed during metadata decoding')
    trial = runtime_io.validate_trial_rows(ids, starts, stops,
                                           expected_rows=planned['expected_rows'])
    record = {key:planned[key] for key in ('asset_id','source_subject_id','source_path','bytes','sha256')}
    record.update(trial)
    record.update(value_reads=list(runtime_io.TRIAL_PATHS),
                  decoded_value_bytes=planned['expected_rows']*24,
                  full_file_hash_bytes=consumed)
    return asset, record


def documents(assets, trials, contract):
    """Join complete source support before any local metadata is published."""
    schema = {
        'schema':'neural099-conditional-preparation-schema-bounds/v1',
        'producer':'portable-regeneration/v1',
        'source_manifest_sha256':CONTRACT_PINS['SOURCES.json'],
        'source_unit_order':'Original units/id row order; IDs are not row ordinals',
        'spike_and_index_values_decoded':False,
        'assets':sorted(assets,key=lambda value:value['asset_id']),
    }
    timing = {
        'schema':'neural099-authenticated-click-timing-inspection/v1',
        'producer':'portable-regeneration/v1',
        'sources_sha256':CONTRACT_PINS['SOURCES.json'],
        'declared_support_sha256':CONTRACT_PINS['DECLARED_SUPPORT.json'],
        'records':sorted(trials,key=lambda value:value['asset_id']),
        'qualification':{'actual_trial_values_authenticated':True,
                         'continuous_support_verified':False,
                         'physical_stimulus_onset_parity_verified':False,
                         'biological_identity_verified':False,
                         'spike_response_values_read':False,
                         'physiological_rate_qualified':False,
                         'ready_for_scoring':False},
    }
    # Frozen join preserves every source row, identity, anatomical denominator and
    # exact binary64 anchor/stop. Protocol bytes were authenticated on entry.
    _,_,cases = prepare_counts.join_inputs(schema,timing,contract['DECLARED_SUPPORT.json'],
                                           contract['COHORT_BINDING.json'],runtime_io)
    require(len(cases)==9867, 'Full accepted case roster required')
    # This is the canonical cases FILE commitment, including final newline.
    body=canonical(cases)
    require(len(body)==2755199 and hashlib.sha256(body).hexdigest()==
            '4cf619e8c06b012b299a45aaab1397c31ebe6cafee00db985077783f026e0582',
            'Regenerated canonical cases differ from the accepted commitment')
    return schema,timing


def write_new(path, value, limit):
    body=canonical(value)
    require(len(body)<=limit, 'Local metadata output exceeds its selected bound')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(body);stream.flush();os.fsync(stream.fileno())
    return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-authenticated-metadata-regeneration',action='store_true')
    parser.add_argument('--raw-root',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    require(args.execute_authenticated_metadata_regeneration,
            'Explicit flag and separately bounded authentic execution required')
    raw,output=Path(args.raw_root),Path(args.output)
    require(raw.is_absolute() and output.is_absolute(), 'Explicit absolute operator paths required')
    require(not output.exists() and not output.is_symlink(), 'Fresh private output directory required')
    require(hasattr(os,'O_NOFOLLOW') and hasattr(os,'O_DIRECTORY'), 'Supported POSIX descriptors required')
    package=HERE.parent
    contract,plan=read_contract(package)
    sources={item['asset_id']:item for item in contract['SOURCES.json']['assets']}
    support={item['asset_id']:item for item in contract['DECLARED_SUPPORT.json']['assets']}
    h5api,versions=runtime_io.initialize_runtime()
    require(versions==RUNTIME, 'Unqualified native runtime version')
    root_fd=os.open(raw,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    assets,trials=[],[]
    try:
        for item in plan:
            asset,trial=inspect_asset(root_fd,item,sources[item['asset_id']],support[item['asset_id']],h5api)
            assets.append(asset);trials.append(trial)
    finally:
        os.close(root_fd)
    schema,timing=documents(assets,trials,contract)
    # Nothing is written until every source and canonical case commitment passes.
    output.mkdir(mode=0o700)
    parent=os.open(output.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(parent)
    finally:os.close(parent)
    pins={}
    pins['schema']=write_new(output/'SCHEMA_BOUNDS.json',schema,MAX_DOCUMENT_BYTES)
    pins['timing']=write_new(output/'CLICK_TIMINGS.json',timing,MAX_DOCUMENT_BYTES)
    from bindings import create_binding
    binding=create_binding(package,output/'SCHEMA_BOUNDS.json',output/'CLICK_TIMINGS.json',
                           binding_path=output/'BINDING.json')
    pins['binding']=write_new(output/'BINDING.json',binding,65536)
    require(sum(p['bytes'] for p in pins.values())+65536<=MAX_OUTPUT_BYTES,
            'Local metadata outputs exceed whole-phase logical bound')
    receipt={'schema':'neural099-portable-local-metadata-completion/v1',
             'source_files':26,'source_bytes_hashed':455615424,'trial_rows':5238,
             'cases':9867,'outputs':pins,'runtime':versions,
             'spike_and_index_values_decoded':False,'observation_coverage_verified':False,
             'physical_stimulus_onset_parity_verified':False,'models_or_scores':0,
             'requires_clean_supervised_completion':True}
    final=write_new(output/'METADATA_COMPLETE.json',receipt,65536)
    directory=os.open(output,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)
    print(json.dumps({'complete':True,'receipt':final,'outputs':pins},sort_keys=True))
    return 0


if __name__=='__main__':raise SystemExit(main())
