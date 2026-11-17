"""REVE-specific opaque submission composition; no qualified installation is bound.

Request/capture helpers are trusted operator interfaces, not execution authority.
The ordinary run entrypoint refuses before provider construction. This module
does not add an isolation implementation or replace unresolved scientific limits.
"""
from __future__ import annotations
import hashlib
import importlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
from types import ModuleType

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
MATERIALS = HERE.parent / 'candidate-materials-v1/materials.py'
MATERIALS_SHA = '2c5bb6c48d90db6d811ccd072787e6cb35329ebd05e28af75a0de0484480f429'
TRANSPORT = REPO / 'benchmarks/neural/NEURAL-007/implementations/whole-night-programme/program/vendor_transport'
TRANSPORT_SHA = '93df92be5b388f4b2896805c8e02f0c41f301d1c86e6b06709444c1075ade0e4'
ENCODER = {'bytes': 276773456, 'sha256': '8ecc650619598748286c2457f81f5c6bd12e8bb59db44f7b02af1955c44de8fe'}
COUNTS = {'train': 6300, 'val': 1734, 'test': 1803}
ROLES = {'paper_data': 'A', 'paper_data_code': 'B'}
RESULT_CAP = 1024**2
HEX = re.compile('[0-9a-f]{64}\\Z')


class Refusal(ValueError): pass
class RuntimeUnavailable(Refusal): pass


def need(ok, message):
    if not ok: raise Refusal(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def digest(value): return pin(canonical(value))['sha256']


def descriptor(value):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'}, 'exact file descriptor required')
    need(type(value['bytes']) is int and value['bytes'] > 0 and
         isinstance(value['sha256'], str) and HEX.fullmatch(value['sha256']), 'positive extent and SHA256 required')
    return value


def materials_module():
    raw = MATERIALS.read_bytes()
    need(pin(raw)['sha256'] == MATERIALS_SHA, 'original material implementation changed')
    module = ModuleType('_reve_opaque_original_materials'); module.__file__ = str(MATERIALS)
    exec(compile(raw, str(MATERIALS), 'exec'), module.__dict__)
    return module


def transport_package():
    """Load the exact existing implementation; import does not launch a process."""
    raw = (TRANSPORT / 'SOURCE_MANIFEST.json').read_bytes()
    need(pin(raw)['sha256'] == TRANSPORT_SHA, 'provider source manifest changed')
    manifest = json.loads(raw)
    need(manifest['schema'] == 'osl_transport_source_manifest_v1' and
         set(manifest['files']) == {'__init__.py','archive.py','bounds.py','contract.py','engine.py','holder.py','provider.py'},
         'complete existing provider source required')
    for name, expected in manifest['files'].items():
        need(pin((TRANSPORT / name).read_bytes()) == expected, 'provider dependency changed: ' + name)
    name = '_reve_existing_owned_transport'
    for key, cached in list(sys.modules.items()):
        if key != name and not key.startswith(name + '.'): continue
        filename = '__init__.py' if key == name else key[len(name)+1:] + '.py'
        need(filename in manifest['files'] and getattr(cached,'__file__',None) is not None and
             Path(cached.__file__).resolve() == TRANSPORT / filename, 'provider module namespace collision')
        if key == name:
            need(list(getattr(cached,'__path__',[])) == [str(TRANSPORT)], 'provider package namespace collision')
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, TRANSPORT / '__init__.py', submodule_search_locations=[str(TRANSPORT)])
        module = importlib.util.module_from_spec(spec); sys.modules[name] = module
        try: spec.loader.exec_module(module)
        except BaseException:
            for key in list(sys.modules):
                if key == name or key.startswith(name + '.'): del sys.modules[key]
            raise
    return tuple(importlib.import_module(name + '.' + part) for part in ('provider', 'contract', 'bounds'))


def packet_info(document, expected_identity, expected_panel_identity):
    """Validate complete public metadata; this does not authenticate array bodies."""
    m = materials_module(); manifest = dict(document)
    claimed = manifest.pop('materials_identity', None)
    need(claimed == expected_identity and isinstance(claimed, str) and digest(manifest) == claimed,
         'independently selected material identity differs')
    need(set(manifest) == {'schema','condition','source_panel_identity','source_commit','data_identity','data',
                          'published_epoch_count','observed_epoch_count','published_epoch_count_matches','paper','official_code',
                          'test_labels_delivered','historical_recipe_verified','scientific_qualification','limits'},
         'unexpected public material metadata')
    need(manifest.get('schema') == 'reve-candidate-materials-v1' and manifest.get('condition') in ROLES,
         'exact REVE participant schema/condition required')
    need(manifest.get('source_panel_identity') == expected_panel_identity and
         isinstance(expected_panel_identity, str) and HEX.fullmatch(expected_panel_identity), 'source panel binding differs')
    need(manifest.get('source_commit') == m.SOURCE_COMMIT and manifest.get('historical_recipe_verified') is False and
         manifest.get('scientific_qualification') is False and manifest.get('test_labels_delivered') is False,
         'source/qualification declarations differ')
    need(manifest.get('observed_epoch_count') == manifest.get('published_epoch_count') == 9837 and
         manifest.get('published_epoch_count_matches') is True, 'complete original epoch census required')
    data = manifest.get('data')
    need(isinstance(data, dict) and digest(data) == manifest.get('data_identity'), 'data identity differs')
    need(set(data) == {'profile','units','dtype','sampling_hz','channels','class_order','counts','records',
                       'test_mapping_identity','test_layout','geometry'}, 'unexpected public data metadata')
    need(data.get('profile') == m.PROFILE and data.get('counts') == COUNTS and data.get('dtype') == 'float64' and
         data.get('units') == 'uV' and data.get('sampling_hz') == 200 and data.get('channels') == m.CHANNELS,
         'full released physical contract required')
    need(data.get('class_order') == ['left_fist','right_fist','both_fists','feet'] and
         data.get('test_layout') == 'one_epoch_per_opaque_file_in_one_persisted_global_shuffle' and
         isinstance(data.get('test_mapping_identity'), str) and HEX.fullmatch(data['test_mapping_identity']),
         'opaque layout/class order/private-map commitment differs')
    geometry = data.get('geometry', {})
    need(set(geometry) == {'path','sha256','bytes','electrodes_in_signal_channel_order','coordinate_convention'} and
         geometry.get('coordinate_convention') == 'unchanged numeric coordinates in the pinned author bank' and
         geometry.get('path') == 'positions.json' and geometry.get('sha256') == m.POSITIONS_SHA256 and
         geometry.get('bytes') == m.POSITIONS_BYTES and geometry.get('electrodes_in_signal_channel_order') == m.ELECTRODES,
         'shared original geometry differs')
    need(manifest['limits'] == [
        'Trusted operator export; mount only this tree into a separately qualified candidate environment.',
        'Original annotations are publicly exposed; physical omission does not create a new secret holdout.',
        'Pretrained encoder weights are not included; identical pretrained access requires separate provision and admission.',
        'Full Table12 preprocessing, trained classifier and seed/run aggregation remain unresolved.'],
        'only the original public source limitation text is permitted')
    need(manifest.get('paper') == {'path':'paper.pdf','sha256':m.PAPER_SHA256,'bytes':m.PAPER_BYTES}, 'original paper differs')
    code = {'path':'official-code.tar.gz','sha256':m.CODE_SHA256,'bytes':m.CODE_BYTES,'commit':m.SOURCE_COMMIT}
    need(manifest.get('official_code') == (code if manifest['condition'] == 'paper_data_code' else None), 'code access condition differs')
    rows = data.get('records'); need(type(rows) is list and len(rows) == 2337, 'complete 2337-file material roster required')
    expected = [(person, run) for person in range(1, 90) for run in m.RUNS]
    totals = {'train':0, 'val':0, 'test':0}; seen = set(); files = set(); test_ids = []
    for index, row in enumerate(rows):
        need(type(row) is dict, 'ordinary public row required')
        shape = row.get('shape')
        need(type(shape) is list and len(shape) == 3 and type(shape[0]) is int and shape[0] > 0 and shape[1:] == [64,800], 'physical row geometry')
        need(isinstance(row.get('sha256'), str) and HEX.fullmatch(row['sha256']), 'signal digest required')
        ids = row.get('event_ids'); need(type(ids) is list and len(ids) == shape[0], 'row/event count differs')
        if index < 534:
            person, run = expected[index]; split = 'train' if person <= 70 else 'val'
            need(set(row) == {'participant','run','split','shape','sha256','event_ids','signal','labels'} and
                 type(row['participant']) is type(row['run']) is int and row['participant'] == person and row['run'] == run and row['split'] == split and
                 row['signal'] == f'signals/S{person:03d}R{run:02d}.npy', 'complete original training/validation roster')
            need(type(row['labels']) is list and len(row['labels']) == shape[0] and
                 all(type(label) is int and label in ((0,1) if run in (4,8,12) else (2,3)) for label in row['labels']),
                 'permitted complete labels required')
            need(all(isinstance(eid,str) and re.fullmatch(fr'S{person:03d}R{run:02d}-event[0-9]{{3,}}',eid) for eid in ids), 'original permitted event mapping')
        else:
            split = 'test'
            need(set(row) == {'split','shape','sha256','event_ids','signal'} and row['split'] == 'test' and shape == [1,64,800],
                 'test labels/grouping/source identity forbidden')
            need(isinstance(row['signal'],str) and re.fullmatch(r'signals/query-[0-9a-f]{32}\.npy',row['signal']) and
                 isinstance(ids[0],str) and re.fullmatch(r'trial-[0-9a-f]{32}',ids[0]), 'opaque test identity required')
            test_ids.append(ids[0])
        need(row['signal'] not in files, 'duplicate signal path'); files.add(row['signal'])
        need(all(eid not in seen for eid in ids) and len(set(ids)) == len(ids), 'duplicate event identity')
        seen.update(ids); totals[split] += shape[0]
    need(totals == COUNTS and len(seen) == 9837, 'complete split support required')
    return {'condition':manifest['condition'],'role':ROLES[manifest['condition']], 'materials_identity':claimed,
            'data_identity':manifest['data_identity'], 'test_ids':test_ids, 'records':rows,
            'paper':manifest['paper'], 'official_code':manifest['official_code'], 'geometry':geometry,
            'manifest_pin':pin(canonical(document)+b'\n')}


def pair_info(a, b, expected_a, expected_b, expected_panel_identity):
    left = packet_info(a, expected_a, expected_panel_identity); right = packet_info(b, expected_b, expected_panel_identity)
    need(left['condition'] == 'paper_data' and right['condition'] == 'paper_data_code', 'ordered paired access conditions')
    need(a['data'] == b['data'] and left['data_identity'] == right['data_identity'], 'paired observations/labels/map must be identical')
    need(expected_a != expected_b, 'condition material identities must differ')
    return left, right


def packet_mount(info, directory, manifest_pin, signal_sizes):
    """Compile the provider's immutable descriptor; its tree() authenticates bodies."""
    descriptor(manifest_pin)
    need(manifest_pin == info['manifest_pin'], 'exact canonical exported manifest bytes required')
    need(set(signal_sizes) == {row['signal'] for row in info['records']}, 'all signal extents required')
    files = {'materials.json':manifest_pin, 'paper.pdf':{k:info['paper'][k] for k in ('bytes','sha256')},
             'positions.json':{k:info['geometry'][k] for k in ('bytes','sha256')}}
    for row in info['records']:
        size = signal_sizes[row['signal']]; payload = math.prod(row['shape']) * 8
        need(type(size) is int and payload + 10 <= size <= payload + 65548, 'bounded full NPY extent')
        files[row['signal']] = {'bytes':size, 'sha256':row['sha256']}
    if info['official_code'] is not None: files['official-code.tar.gz'] = {k:info['official_code'][k] for k in ('bytes','sha256')}
    need(Path(directory).is_absolute(), 'explicit absolute packet root required')
    # B's whole packet includes author source; A's packet never does.
    return {'path':str(directory), 'kind':'directory', 'purpose':'historical_author_source' if info['role'] == 'B' else 'input', 'files':files}


def common_mount(directory, files):
    need(type(files) is dict and set(files) == {'encoder.safetensors','encoder-config.json','encoder-runtime.py','ENCODER_SOURCE.json'},
         'explicit identical usable encoder package required')
    for value in files.values(): descriptor(value)
    need(files['encoder.safetensors'] == ENCODER, 'pinned released encoder required; not a classifier identity')
    need(Path(directory).is_absolute(), 'explicit absolute common-asset root')
    return {'path':str(directory), 'kind':'directory', 'purpose':'program', 'files':files}


def request(info, packet, program, common, *, phase_id, image, exposure_pin, origin, deadline, resources):
    """Compile existing provider ABI only. Positive resources are not scientific admission."""
    provider, contract, bounds = transport_package()
    need(packet['purpose'] == ('historical_author_source' if info['role'] == 'B' else 'input'), 'condition mount role differs')
    signal_sizes = {row['signal']:packet['files'][row['signal']]['bytes'] for row in info['records']}
    need(packet == packet_mount(info,packet['path'],packet['files']['materials.json'],signal_sizes), 'packet descriptor differs from selected material')
    need(type(program) is dict and program.get('kind') == 'directory' and program.get('purpose') == 'program' and
         set(program.get('files', {})) == {'solution.py'}, 'one frozen submitted program required')
    descriptor(program['files']['solution.py'])
    common_mount(common['path'], common['files'])
    need(common.get('kind') == 'directory' and common.get('purpose') == 'program', 'exact shared encoder mount')
    mounts = {'/input':packet, '/candidate':program, '/common':common}
    source = pin(canonical(program['files']))
    phase = {'schema':'osl_owned_phase_request_v1','phase_id':phase_id,'action':'held_attempt','role':info['role'],
             'image':image,'command':['/usr/local/bin/python','-I','-B','/candidate/solution.py'], 'workdir':'/work',
             'source':source,'exposure':descriptor(exposure_pin),'clock':{'origin':origin,'phase_deadline':deadline},
             'resources':dict(resources),'output':{'kind':'generic','manifest':'OUTPUTS.json'}}
    contract.validate_request(phase,mounts,deadline)
    minimum = 2 * sum(entry['bytes'] for mount in mounts.values() for entry in mount['files'].values())
    need(resources['source_read_bytes'] > minimum, 'before/after complete input hashing plus overhead required')
    need(resources['max_files'] == 2 and resources['max_directories'] == 1 and
         resources['manifest_bytes'] <= 65536 and resources['max_file_bytes'] <= RESULT_CAP,
         'REVE emits only bounded RESULT.json and OUTPUTS.json')
    return {'request':phase, 'mounts':mounts, 'materials_identity':info['materials_identity'],
            'minimum_input_hash_reads':minimum, 'runtime_qualified':False, 'scientific_budget_adopted':False}


def paired_requests(infos, packets, programs, common, *, phase_ids, image, exposure_pins, origin, deadline, resources):
    need(len(infos) == len(packets) == len(programs) == len(phase_ids) == len(exposure_pins) == 2,
         'exact two access conditions required')
    need([info['role'] for info in infos] == ['A','B'] and infos[0]['data_identity'] == infos[1]['data_identity'] and
         infos[0]['test_ids'] == infos[1]['test_ids'] and phase_ids[0] != phase_ids[1], 'matched views and distinct phase identities')
    return [request(infos[i],packets[i],programs[i],common,phase_id=phase_ids[i],image=image,
                    exposure_pin=exposure_pins[i],origin=origin,deadline=deadline,resources=resources)
            for i in range(2)]


def admit_result(document, info):
    need(type(document) is dict and set(document) == {'schema','materials_identity','predictions'} and
         document['schema'] == 'reve-candidate-predictions-v1' and document['materials_identity'] == info['materials_identity'],
         'exact condition-bound REVE result required')
    rows = document['predictions']; need(type(rows) is list and len(rows) == 1803, 'complete 1803 predictions required')
    expected = set(info['test_ids']); seen = set()
    for row in rows:
        need(type(row) is dict and set(row) in ({'event_id','prediction'},{'event_id','scores'}), 'closed prediction row required')
        eid = row['event_id']; need(isinstance(eid,str) and eid in expected and eid not in seen, 'opaque prediction IDs must be a bijection')
        seen.add(eid)
        if 'prediction' in row: need(type(row['prediction']) is int and row['prediction'] in range(4), 'four-class integer prediction')
        else: need(type(row['scores']) is list and len(row['scores']) == 4 and
                   all(type(x) in (int,float) and math.isfinite(x) for x in row['scores']), 'finite four-class scores')
    need(len(canonical(document)) <= RESULT_CAP, 'bounded complete result')
    return document


def _collect_observed(provider, bundle, returned, original_deadline, info):
    """Trusted composition seam, not authority: re-read the concrete provider receipt."""
    p, contract, bounds = transport_package()
    need(type(provider) is p.Provider, 'only the exact pinned provider type is supported')
    phase = bundle['request']
    need(bundle['materials_identity'] == info['materials_identity'] and phase['role'] == info['role'] and
         bundle['mounts']['/input']['files']['materials.json'] == info['manifest_pin'],
         'captured request must bind the selected condition/material manifest')
    request_hash = pin(p.encoded(phase))['sha256']
    observed = provider.observe(phase['phase_id'],request_hash,returned['receipt_pin'],original_deadline)
    receipt = observed['receipt']; need(receipt == returned['receipt'], 'independent provider observation differs')
    need(receipt['schema'] == 'osl_owned_phase_receipt_v1' and receipt['status'] == 'captured' and
         receipt['phase_id'] == phase['phase_id'] and receipt['request_sha256'] == request_hash and
         all(receipt[k] == phase[k] for k in ('action','role','image','source','exposure')), 'exact captured phase identity required')
    need(receipt['all_native_resources_closed'] is True and receipt['cli_reaped'] is True and
         receipt['producer_closed_before_capture'] is True and receipt['error'] is None and receipt['oom'] is False and
         receipt['deadline_exceeded'] is False and len(receipt['retired_resources']) == 3 and
         all(row['closed'] is True for row in receipt['retired_resources']), 'complete owned transport closure required')
    closures = receipt['retired_resources']
    need(sorted(row['kind'] for row in closures) == ['container','container','volume'] and
         len({row['name'] for row in closures}) == 3 and
         all(row.get('absence_observed') is True and row.get('creation_outcome_unknown') is False for row in closures),
         'three distinct resources need observed absence and known creation outcomes')
    p.validate_cli_records(receipt['command_metadata'],p.caps(phase['resources']['inventory_bytes']))
    p.validate_natural_exit(receipt['natural_exit'])
    need(receipt['enforced_resource_limits'] == phase['resources'] and
         receipt['input_before'] == receipt['input_after'] == bounds.mount_identity(bundle['mounts']), 'resource or input identity changed')
    need(receipt['timing']['original_deadline'] == original_deadline and receipt['qualification_inherited'] is False and
         receipt['scientific_qualification'] is False, 'original time/qualification scope differs')
    capture = receipt['output_inventory']; need(capture['complete'] is True and set(capture['files']) == {'OUTPUTS.json','RESULT.json'}, 'exact complete output capture')
    root = provider.quarantine_root / phase['phase_id']
    need(Path(receipt['quarantine_root']) == root, 'owned quarantine path differs')
    allowance = min(4*RESULT_CAP,provider.read_limit-provider.read_used)
    need(allowance > 0, 'whole provider metadata read allowance exhausted')
    meter = bounds.Meter(allowance,1,original_deadline)
    try:
        envelope = p.parse(bounds.body(root/'OUTPUTS.json',capture['files']['OUTPUTS.json'],meter,65536))
        inventory = {'files':[{'name':name,'bytes':item['bytes']} for name,item in capture['files'].items()]}
        declared = contract.output_files(envelope,phase,request_hash,inventory)
        need(declared == {'RESULT.json':capture['files']['RESULT.json']}, 'only one declared scientific result allowed')
        raw = bounds.body(root/'RESULT.json',declared['RESULT.json'],meter,RESULT_CAP)
        result = admit_result(p.parse(raw),info)
    finally:
        provider.read_used += meter.read_bytes
    return {'result':result,'result_path':str(root/'RESULT.json'),'result_pin':pin(raw),
            'receipt_pin':returned['receipt_pin'],'private_restoration_pending':True,
            'collection_metadata_read_bytes':meter.read_bytes,
            'runtime_qualification':False,'scientific_qualification':False,'candidate_model_activity_measured':False}


def _compose_owned_phase(provider, bundle, original_deadline, journal, info):
    """Internal call graph exercised with inert fixtures; public run remains closed."""
    _require_installation()
    p, _, _ = transport_package()
    need(type(provider) is p.Provider, 'arbitrary backend objects are not accepted')
    returned = provider.execute_phase(bundle['request'],bundle['mounts'],original_deadline,journal)
    return _collect_observed(provider,bundle,returned,original_deadline,info)


def restore_private(collected, *, panel_path, mapping_path, materials_path, output,
                    expected_panel_identity, expected_mapping_identity, expected_materials_identity):
    """Trusted operator continuation only; never calls the scorer or reads targets."""
    m = materials_module()
    with m.regular(collected['result_path'],RESULT_CAP) as (stream,size):
        raw = stream.read(RESULT_CAP+1); need(len(raw) == size, 'bounded collected result required')
    need(pin(raw) == collected['result_pin'] and collected['private_restoration_pending'] is True, 'collected output changed')
    return m.restore_predictions(panel_path,mapping_path,materials_path,collected['result_path'],output,
        expected_panel_identity=expected_panel_identity,expected_mapping_identity=expected_mapping_identity,
        expected_materials_identity=expected_materials_identity)


def _require_installation():
    raise RuntimeUnavailable('No independently qualified REVE Linux/GPU installation or adopted paired scientific budget is bound. '
                             'The reused provider is CPU-only; preparation controls and exposure booleans are not execution authority.')


def run(*args, **kwargs):
    """No side effects or caller override can turn source composition into a deployment."""
    _require_installation()
