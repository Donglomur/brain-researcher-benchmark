"""Task-local raw epoch programme adapter around the maintained owned Provider.

The contained producer is this same pinned file; no candidate is imported on the host.
A prepared definition is shared by both modalities. Actual execution needs external
image/exposure admission and native capacity; source or generated controls confer neither.
"""
from __future__ import annotations
import argparse
import importlib.util
import math
from pathlib import Path
import sys
import types

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import raw_contract as C

COMMON = 'benchmarks/neural/NEURAL-007/implementations/finite-workflow-v1/common.py'
PROVIDER = 'benchmarks/neural/NEURAL-007/implementations/whole-night-programme/provider-public-mode-v2/vendor_transport'
COMMAND = ['/usr/local/bin/python', '-I', '-B', '/trusted/raw_programme.py', 'produce']
INPUT_TARGETS = {'/input/case.json', '/input/signals.npy', '/program/program.py',
                 '/trusted/PROGRAMME.json', '/trusted/raw_programme.py', '/trusted/raw_contract.py'}


def plain(value):
    return C.checked_pin({k: value[k] for k in ('bytes', 'sha256')})


def module(name, path, pin):
    raw = C.read_exact(path, pin, 2**20)
    value = types.ModuleType(name)
    value.__file__ = str(path)
    sys.modules[name] = value
    exec(compile(raw, str(path), 'exec'), value.__dict__)
    return value


def load_runtime(source, dependency_root=None):
    runtime = C.verify_source(source, dependency_root)
    required = {COMMON, str(Path(COMMON).with_name('SOURCE_BINDINGS.json'))}
    required |= {PROVIDER + '/' + name for name in ('SOURCE_MANIFEST.json', '__init__.py', 'provider.py',
                  'engine.py', 'bounds.py', 'contract.py', 'archive.py', 'holder.py')}
    C.need(required <= runtime['bindings']['upstream'].keys(), 'Complete maintained Provider source closure')
    C.need({'raw_contract.py', 'raw_programme.py'} <= runtime['bindings']['local'].keys(), 'Bound raw producer source')
    runtime.update(source_descriptor=source, provider=None, common=None)
    return runtime


def provider_module(runtime):
    if runtime['provider'] is None:
        common = module('_raw008_common', runtime['root'] / COMMON, runtime['bindings']['upstream'][COMMON])
        name = '_sleep_finite_transport.provider'
        if name in sys.modules:
            provider = sys.modules[name]
            C.need(Path(provider.__file__).resolve() == runtime['root'] / PROVIDER / 'provider.py', 'Exact maintained Provider')
        else:
            provider = common.load_provider()
        runtime.update(common=common, provider=provider)
    return runtime['provider']


def snapshot(path, cap):
    path = C.ordinary_path(path)
    C.need(path.is_file() and 0 < path.stat().st_size <= cap, 'Bounded ordinary operand')
    raw = path.read_bytes()
    return C.read_exact(path, C.pin(raw), cap)


def definition_value(programme, knowledge, source, image, generation):
    C.need(type(image) is str and len(image) == 71 and image.startswith('sha256:')
           and all(c in '0123456789abcdef' for c in image[7:]), 'Immutable externally admitted image')
    return {'schema': 'neural008_raw_programme_definition_v1', 'family': C.FAMILY,
            'conditions': C.PROGRAMME_CONDITIONS, 'programme': plain(programme), 'knowledge': plain(knowledge),
            'source': plain(source), 'image': image, 'generation_provenance': None if generation is None else plain(generation),
            'additional_training_or_reference_assets': [], 'hidden_pretraining_verified': False,
            'matched_agent_provenance_qualified': False}


def prepare(programme_path, knowledge, source, output_root, *, image, dependency_root=None, generation_provenance=None):
    runtime = load_runtime(source, dependency_root)
    raw = snapshot(programme_path, 200000)
    raw.decode('utf-8', errors='strict')
    prior = C.capture(knowledge, 8192)
    C.need(C.encode(C.checked_knowledge(C.decode(prior))) == prior, 'Canonical declared shared prior')
    if generation_provenance is not None: C.capture(generation_provenance, 2**20)
    root = C.ordinary_path(output_root)
    root.mkdir(mode=0o700)
    programme = C.write_new(root / 'program.py', raw)
    definition = C.write_new(root / 'PROGRAMME.json', C.encode(definition_value(
        programme, knowledge, source, image, generation_provenance)))
    return C.write_new(root / 'PREPARED.json', C.encode({'schema': 'neural008_raw_prepared_v1',
        'programme': programme, 'knowledge': knowledge, 'source': source, 'definition': definition,
        'generation_provenance': generation_provenance, 'scientific_input_reads': 0}))


def checked_prepared(prepared, runtime):
    value = C.decode(C.capture(prepared, 32768))
    C.need(type(value) is dict and set(value) == {'schema','programme','knowledge','source','definition',
           'generation_provenance','scientific_input_reads'} and value['schema'] == 'neural008_raw_prepared_v1'
           and value['scientific_input_reads'] == 0, 'One pre-input frozen programme for both modalities')
    C.need(plain(value['source']) == runtime['source'], 'Exact executing source freeze')
    C.capture(value['source'], 65536)
    C.capture(value['programme'], 200000).decode('utf-8', errors='strict')
    prior = C.capture(value['knowledge'], 8192)
    knowledge = C.checked_knowledge(C.decode(prior))
    C.need(C.encode(knowledge) == prior, 'Canonical declared prior')
    if value['generation_provenance'] is not None: C.capture(value['generation_provenance'], 2**20)
    definition = C.decode(C.capture(value['definition'], 32768))
    C.need(definition == definition_value(value['programme'], value['knowledge'], value['source'],
            definition.get('image'), value['generation_provenance']), 'Unchanged shared two-modality definition')
    return value, definition, knowledge


def file_mount(path, expected, purpose):
    p = C.ordinary_path(path)
    return {'path':str(p), 'kind':'file', 'purpose':purpose, 'files':{p.name:plain(expected)}}


def make_mounts(prepared_value, runtime, projection):
    packet = C.read_projection(projection)
    root = C.ordinary_path(projection['root'])
    local = runtime['bindings']['local']
    mounts = {'/input/case.json':file_mount(root/'case.json', projection['case'], 'contract'),
              '/input/signals.npy':file_mount(root/'signals.npy', projection['signals'], 'input'),
              '/program/program.py':file_mount(prepared_value['programme']['path'], prepared_value['programme'], 'program'),
              '/trusted/PROGRAMME.json':file_mount(prepared_value['definition']['path'], prepared_value['definition'], 'contract')}
    for name in ('raw_programme.py','raw_contract.py'):
        mounts['/trusted/'+name] = file_mount(runtime['here']/name, local[name], 'program')
    return checked_mounts(mounts), packet


def checked_mounts(mounts):
    C.need(type(mounts) is dict and set(mounts) == INPUT_TARGETS, 'Exactly six current-epoch file mounts')
    for item in mounts.values():
        C.need(type(item) is dict and set(item) == {'path','kind','purpose','files'} and item['kind']=='file'
               and item['purpose'] in {'program','input','contract'} and list(item['files']) == [Path(item['path']).name],
               'No directory, model, label, reference or other-target export')
        C.ordinary_path(item['path']); C.checked_pin(next(iter(item['files'].values())))
    return mounts


def phase_request(packet, definition, definition_pin, exposure_pin, resources, origin, phase_deadline):
    C.need(type(resources) is dict and all(type(v) is int and v > 0 for v in resources.values()), 'Finite Provider limits')
    C.need(all(type(v) in (int,float) and math.isfinite(v) for v in (origin,phase_deadline))
           and 0 <= origin < phase_deadline, 'Finite immutable clock')
    return {'schema':'osl_owned_phase_request_v1',
            'phase_id':'raw008_'+packet.modality+'_'+packet.case.replace('-','_')+'_'+str(packet.epoch_index).zfill(5),
            'action':'held_attempt','role':'A','image':definition['image'],'command':list(COMMAND),'workdir':'/work',
            'source':plain(definition_pin),'exposure':plain(exposure_pin),'clock':{'origin':origin,'phase_deadline':phase_deadline},
            'resources':dict(resources),'output':{'kind':'generic','manifest':'OUTPUTS.json'}}


def validate(runtime, request, mounts, exposure, boundary_audit, deadline):
    provider = provider_module(runtime)
    contract = sys.modules[provider.__package__+'.contract']
    contract.validate_request(request, mounts, deadline)
    approved = C.decode(C.capture(exposure, 2**20))
    C.need(plain(exposure) == request['exposure'], 'Exact external exposure approval')
    contract.validate_exposure(approved, request, mounts)
    C.need(plain(boundary_audit) == approved['boundary_audit'], 'Bound external image/source boundary audit')
    C.capture(boundary_audit, 2**20)
    return approved


def open_provider(runtime, control_root, quarantine_root, provider_config, approvals, read_limit, write_limit):
    C.need(type(provider_config) is dict and set(provider_config)=={'docker_binary','docker_socket'}, 'External Docker interface')
    C.need(type(approvals) is list and approvals, 'Operator-selected exact exposure approvals')
    registry = {}
    for approval in approvals:
        C.need(type(approval) is dict and set(approval)=={'exposure','boundary_audit'}, 'External approval and boundary audit')
        item = approval['exposure']; value = C.decode(C.capture(item, 2**20))
        C.need(plain(approval['boundary_audit']) == value['boundary_audit'], 'Bound boundary audit')
        C.capture(approval['boundary_audit'], 2**20)
        registry[item['sha256']] = item['path']
    provider = provider_module(runtime)
    return provider.Provider(control_root, quarantine_root, provider_config['docker_binary'], provider_config['docker_socket'],
        runtime['common'].bindings()['provider_manifest'], registry, read_limit, write_limit)


def execute_phase(runtime, provider, prepared, projection, exposure, resources, origin, phase_deadline, deadline, journal, *, boundary_audit):
    value, definition, knowledge = checked_prepared(prepared, runtime)
    mounts, packet = make_mounts(value, runtime, projection)
    request = phase_request(packet, definition, value['definition'], exposure, resources, origin, phase_deadline)
    validate(runtime, request, mounts, exposure, boundary_audit, deadline)
    result = provider.execute_phase(request, mounts, deadline, journal)
    observed = provider.observe(request['phase_id'], result['receipt']['request_sha256'], result['receipt_pin'], deadline)
    C.need(observed['receipt'] == result['receipt'] and observed['receipt_pin'] == result['receipt_pin']
           and observed.get('independent_candidate_channel') is True, 'Independent maintained closure observation')
    receipt = observed['receipt']; output = C.ordinary_path(receipt['quarantine_root'])
    return {'epoch_id':packet.epoch_id,'modality':packet.modality,'projection':projection,'prepared':prepared,
        'exposure':exposure,'boundary_audit':boundary_audit,
        'request':{'path':str(C.ordinary_path(provider.control_root)/request['phase_id']/'REQUEST.json'),
                   **C.pin(provider_module(runtime).encoded(request))},
        'receipt':{'path':result['receipt_path'],**result['receipt_pin']}, 'observer_value':observed,
        'prediction':{'path':str(output/'prediction.json'),**receipt['output_inventory']['files']['prediction.json']},
        'result':{'path':str(output/'RESULT.json'),**receipt['output_inventory']['files']['RESULT.json']}}


def admit_phase(runtime, record, packet, expected_knowledge):
    C.need(type(record) is dict and set(record)=={'epoch_id','modality','projection','prepared','exposure','boundary_audit',
           'request','receipt','observer_value','prediction','result'} and record['epoch_id']==packet.epoch_id
           and record['modality']==packet.modality, 'Exact modality and target phase record')
    prepared, definition, knowledge = checked_prepared(record['prepared'], runtime)
    projected = C.read_projection(record['projection'])
    C.need(projected.metadata()==packet.metadata() and projected.signals_npy==packet.signals_npy, 'Authenticated original epoch only')
    C.need(knowledge==C.checked_knowledge(expected_knowledge), 'Same declared prior')
    request = C.decode(C.capture(record['request'],32768)); receipt = C.decode(C.capture(record['receipt'],2**20))
    observer = record['observer_value']
    C.need(type(observer) is dict and observer['receipt']==receipt and observer['receipt_pin']==plain(record['receipt'])
           and observer.get('independent_candidate_channel') is True, 'Independent exact captured receipt')
    C.need(request==phase_request(packet,definition,prepared['definition'],record['exposure'],request['resources'],
            request['clock']['origin'],request['clock']['phase_deadline']), 'Exact raw epoch producer request')
    C.need(receipt['schema']=='osl_owned_phase_receipt_v1' and receipt['request_sha256']==record['request']['sha256']
           and all(receipt[k]==request[k] for k in ('phase_id','source','image','action','role','exposure'))
           and receipt['status']=='captured' and receipt['error'] is None and receipt['all_native_resources_closed'] is True
           and receipt['producer_closed_before_capture'] is True and receipt['cli_reaped'] is True
           and receipt['deadline_exceeded'] is False and receipt['enforced_resource_limits']==request['resources'], 'Closed fresh producer')
    natural = receipt['natural_exit']
    C.need(type(natural['ExitCode']) is int and natural['ExitCode']==0 and natural['Running'] is False
           and natural['Status']=='exited' and natural['Dead'] is False and natural['Pid']==0 and natural['OOMKilled'] is False,
           'Natural successful programme exit')
    retired = receipt['retired_resources']
    C.need(type(retired) is list and len(retired)==3 and len({r['name'] for r in retired})==3
           and sorted(r['kind'] for r in retired)==['container','container','volume']
           and all(r['closed'] is True and r.get('absence_observed') is True and r.get('creation_outcome_unknown') is False for r in retired),
           'Three distinct closed owned resources')
    mounts,_ = make_mounts(prepared,runtime,record['projection'])
    validate(runtime,request,mounts,record['exposure'],record['boundary_audit'],receipt['timing']['original_deadline'])
    before=receipt['input_before']
    C.need(before==receipt['input_after'] and set(before)==INPUT_TARGETS, 'No changing or richer participant input')
    for destination,expected in mounts.items():
        C.need(before[destination]['kind']=='file' and before[destination]['files']==expected['files'], 'Exact six file input custody')
    timing=receipt['timing']
    C.need(set(timing)=={'origin','original_deadline','phase_deadline','started','finished'}
           and all(type(v) in (int,float) and math.isfinite(v) for v in timing.values())
           and timing['origin']==request['clock']['origin'] and timing['origin']<=timing['started']<timing['finished']
           <=timing['phase_deadline']<=request['clock']['phase_deadline']<=timing['original_deadline'], 'Finite unchanged clocks')
    inventory=receipt['output_inventory']
    C.need(inventory['complete'] is True and set(inventory['files'])=={'prediction.json','RESULT.json','OUTPUTS.json'}, 'One first final and envelope')
    for filename,key in (('prediction.json','prediction'),('RESULT.json','result')):
        C.need(inventory['files'][filename]==plain(record[key]) and C.ordinary_path(record[key]['path'])==
               C.ordinary_path(Path(receipt['quarantine_root'])/filename), 'Captured output custody')
    prediction=C.decode(C.capture(record['prediction'],8192)); values=checked_prediction(prediction,packet)
    report=C.decode(C.capture(record['result'],8192))
    C.need(report==producer_report(packet,definition,plain(record['prediction'])), 'Exact captured producer envelope')
    return {'epoch_id':packet.epoch_id,'probabilities':values,'definition':plain(prepared['definition']),
            'knowledge':C.pin(C.encode(knowledge)),'resources':retired,'timing':timing,
            'phase_id':request['phase_id'],'request':plain(record['request']), 'qualification':False}


def checked_prediction(value, packet):
    C.need(type(value) is dict and set(value)=={'condition','epoch_id','probabilities'}
           and value['condition']==C.PROGRAMME_CONDITIONS[packet.modality] and value['epoch_id']==packet.epoch_id,
           'Exact modality-specific first target answer')
    return C.probabilities(value['probabilities'])


def producer_report(packet, definition, prediction):
    return {'schema':'neural008_raw_epoch_producer_v1','condition':C.PROGRAMME_CONDITIONS[packet.modality],
            'epoch_id':packet.epoch_id,'programme':definition['programme'],'knowledge':definition['knowledge'],
            'prediction':prediction,'participant_exit':0}


def produce():
    # Only the existing confined Provider invokes this branch; never a host candidate import.
    import subprocess
    request_raw=snapshot('/request.json',32768); request=C.decode(request_raw)
    definition=C.decode(snapshot('/trusted/PROGRAMME.json',32768))
    C.need(definition['schema']=='neural008_raw_programme_definition_v1' and definition['family']==C.FAMILY
           and definition['conditions']==C.PROGRAMME_CONDITIONS and definition['additional_training_or_reference_assets']==[]
           and C.pin(snapshot('/program/program.py',200000))==definition['programme'], 'Frozen two-modality programme')
    packet=C.RawEpochPacket(C.decode(snapshot('/input/case.json',4096)),snapshot('/input/signals.npy',76106))
    C.need({p.name for p in Path('/input').iterdir()}=={'case.json','signals.npy'} and not list(Path('/output').iterdir()),
           'Only current epoch and fresh output')
    result=subprocess.run([sys.executable,'-I','-B','/program/program.py','--input','/input','--out','/output'],
        stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
    C.need(result.returncode==0 and {p.name for p in Path('/output').iterdir()}=={'prediction.json'}, 'One successful first final')
    raw=snapshot('/output/prediction.json',8192); checked_prediction(C.decode(raw),packet)
    report=C.write_new('/output/RESULT.json',C.encode(producer_report(packet,definition,C.pin(raw))))
    C.write_new('/output/OUTPUTS.json',C.encode({'schema':'osl_transport_output_manifest_v1','phase_id':request['phase_id'],
        'request_sha256':C.pin(request_raw)['sha256'],'files':{'prediction.json':C.pin(raw),'RESULT.json':plain(report)}}))


def main(argv=None):
    args=list(sys.argv[1:] if argv is None else argv)
    if args==['produce']: return produce()
    parser=argparse.ArgumentParser(); parser.add_argument('--operation',choices=('prepare','run'),required=True)
    parser.add_argument('--config',required=True); parser.add_argument('--bytes',type=int,required=True); parser.add_argument('--sha256',required=True)
    a=parser.parse_args(args); value=C.decode(C.capture({'path':a.config,'bytes':a.bytes,'sha256':a.sha256},2**20))
    if a.operation=='prepare': result=prepare(**value)
    else:
        runtime=load_runtime(value['source'],value.get('dependency_root'))
        provider=open_provider(runtime,**value['provider'])
        journal=[]
        record=execute_phase(runtime,provider,journal=lambda event,row: journal.append((event,row)),**value['phase'])
        result=C.write_new(value['record_path'],C.encode(record))
    print(C.encode({'status':'complete','result':result,'native_capacity_qualified':False,'scientific_qualification':False}).decode(),end='')
    return result


if __name__=='__main__': main()
