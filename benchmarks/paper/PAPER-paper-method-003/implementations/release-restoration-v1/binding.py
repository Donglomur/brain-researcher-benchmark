"""Retain the completed REVE release through unchanged private ID restoration.

Trusted operator metadata continuation, not a runner, execution attestation,
budget authorization, or scientific qualification. No targets or arrays opened.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat
from types import ModuleType

HERE = Path(__file__).resolve().parent
BOUNDARY_SHA = 'b097287c39bb175613d74b48671df75c600dfb9391a0b2cf509124a9abb31562'
ADAPTER_SHA = 'b69ff59cd7fb164833b816821b14d86b1f2f2a5e556a2842b9c70f9360a00faf'
MAX_METADATA = 4 * 1024**2
MAX_RESULT = 1024**2
PROFILES = ('original-like-no-target-calibration-v1', 'frozen-program-full-test-context-v1')
CONTEXT = {'episode_id','role','profile','declaration','artifact_identity','design_identity',
           'roster_identity','materials_identity','release_identity'}
RELEASE_FIELDS = CONTEXT | {'schema','predictions_pin','complete_test_epochs',
                            'scientific_qualification','current_paper_win_qualified',
                            'requires_separate_outcome_binding'}


class Refusal(ValueError): pass


class BindingFailure(Refusal):
    def __init__(self, error, audit, output):
        self.detail = {**deepcopy(audit),'status':'failed','output':str(output),
                       'error_type':type(error).__name__,
                       'reason':str(error)[:240] if isinstance(error,ValueError) else type(error).__name__,
                       'errno':error.errno if isinstance(error,OSError) else None,
                       'strerror':error.strerror[:160] if isinstance(error,OSError) and isinstance(error.strerror,str) else None,
                       'partial_output_must_not_be_used':True}
        super().__init__(self.detail['reason'])


def need(ok, message):
    if not ok: raise Refusal(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode() + b'\n'


def pin(body):
    return {'bytes':len(body), 'sha256':hashlib.sha256(body).hexdigest()}


def dependencies():
    boundary = HERE.parent/'development-boundary-v1/boundary.py'
    need(hashlib.sha256(boundary.read_bytes()).hexdigest() == BOUNDARY_SHA, 'release producer source changed')
    path = HERE.parent/'opaque-submission-v1/adapter.py'
    body = path.read_bytes()
    need(hashlib.sha256(body).hexdigest() == ADAPTER_SHA, 'original opaque adapter changed')
    adapter = ModuleType('_reve_bound_restoration_adapter'); adapter.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), adapter.__dict__)
    return adapter, adapter.materials_module()


def directory(path, private=False):
    path = Path(path)
    need(path.is_absolute() and path.anchor == '/' and '..' not in path.parts, 'ordinary absolute directory required')
    for ancestor in (path, *path.parents):
        info = ancestor.lstat()
        need(stat.S_ISDIR(info.st_mode), 'directory aliases are not accepted')
    if private:
        need(path.stat().st_uid == os.getuid() and stat.S_IMODE(path.stat().st_mode) == 0o700,
             'operator-owned mode0700 parent required')
    return path


def read_document(path, materials, expected=None, cap=MAX_METADATA, audit=None):
    path = Path(path); directory(path.parent)
    with materials.regular(path, cap) as (stream, size):
        if audit is not None: audit['metadata_read_charge_bytes'] += size
        body = stream.read(size)
        need(len(body) == size, 'metadata changed during capture')
    actual = pin(body)
    if expected is not None: need(actual == expected, 'externally retained file pin differs')
    value = json.loads(body, object_pairs_hook=materials._unique,
                       parse_constant=lambda _: (_ for _ in ()).throw(Refusal('nonfinite metadata')))
    need(type(value) is dict, 'closed metadata object required')
    return value, actual


def validate_release(released, expected_context, info, adapter):
    """Join genuine producer-shaped metadata to separately selected context.

    A forged release and forged caller expectations do not attest execution.
    The existing live campaign owner remains the execution/chronology authority.
    """
    need(type(released) is dict and set(released) == {'release','predictions'}, 'mandatory full release wrapper required')
    release = deepcopy(released['release']); predictions = deepcopy(released['predictions'])
    need(type(release) is dict and set(release) == RELEASE_FIELDS, 'exact original release fields required')
    need(type(expected_context) is dict and set(expected_context) == CONTEXT,
         'independently retained complete release context required')
    need(all(release[key] == expected_context[key] for key in CONTEXT), 'release/context identity mismatch')
    need(release['schema'] == 'reve-protected-prediction-release-v1' and release['profile'] in PROFILES,
         'supported original release schema/profile required')
    need(release['role'] == info['role'] and release['materials_identity'] == info['materials_identity'],
         'release arm/material identity differs from selected packet')
    for key in ('episode_id','artifact_identity','design_identity','roster_identity','materials_identity','release_identity'):
        need(type(release[key]) is str and adapter.HEX.fullmatch(release[key]), 'release identity must be SHA256-shaped')
    declaration = release['declaration']
    need(type(declaration) is dict and set(declaration) == {'uses_unlabeled_test_context','description'} and
         type(declaration['uses_unlabeled_test_context']) is bool and
         type(declaration['description']) is str and 0 < len(declaration['description']) <= 4096,
         'exact original method declaration required')
    need(release['profile'] != PROFILES[0] or declaration['uses_unlabeled_test_context'] is False,
         'original-like profile cannot declare test-context adaptation')
    need(type(release['complete_test_epochs']) is int and release['complete_test_epochs'] == 1803 and
         release['scientific_qualification'] is False and release['current_paper_win_qualified'] is False,
         'complete unqualified source release required')
    need(release['requires_separate_outcome_binding'] is (release['profile'] == PROFILES[1]),
         'prospective outcome separation cannot be removed')
    need(adapter.digest({k:v for k,v in release.items() if k != 'release_identity'}) == release['release_identity'],
         'release digest changed')
    adapter.admit_result(predictions, info)
    adapter.descriptor(release['predictions_pin'])
    need(pin(canonical(predictions)) == release['predictions_pin'], 'released predictions changed')
    return {'release':release,'predictions':predictions}


def write_private(path, body, audit=None):
    if audit is not None: audit['write_charge_upper_bytes'] += len(body)
    fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        need(stream.write(body) == len(body), 'short private output write')
        stream.flush(); os.fsync(stream.fileno())


def restore(released, *, expected_context, panel_path, mapping_path, materials_path,
            expected_panel_identity, expected_mapping_identity, expected_data_identity, output):
    """Restore once; publish the bound manifest only after complete validation.

    Reads bounded JSON only. Original restore reads the same three inputs plus
    captured predictions again. No score is computed and failures retain partial
    private output without a valid complete manifest. External supervision and
    cumulative campaign accounting remain the admitted operator's obligation.
    """
    audit = {'stage':'preflight','metadata_read_charge_bytes':0,'write_charge_upper_bytes':0,
             'accounting':'own requested metadata I/O plus unchanged restorer maximum4x16MiB reads/16MiB write, including failure; imports/runtime/filesystem metadata excluded'}
    try:
        return _restore(released, expected_context, panel_path, mapping_path, materials_path,
                        expected_panel_identity, expected_mapping_identity, expected_data_identity, output, audit)
    except Exception as error:
        raise BindingFailure(error, audit, output) from error


def _restore(released, expected_context, panel_path, mapping_path, materials_path,
             expected_panel_identity, expected_mapping_identity, expected_data_identity, output, audit):
    adapter, materials = dependencies()
    need(type(expected_context) is dict and set(expected_context) == CONTEXT,
         'independently retained complete release context required')
    paths = {key:Path(value) for key,value in
             {'panel':panel_path,'mapping':mapping_path,'materials':materials_path}.items()}
    audit['stage'] = 'capture_inputs'
    captured = {key:read_document(path, materials, audit=audit) for key,path in paths.items()}
    document = captured['materials'][0]
    info = adapter.packet_info(document, expected_context['materials_identity'], expected_panel_identity)
    need(info['data_identity'] == expected_data_identity, 'shared paired data identity differs')
    accepted = validate_release(released, expected_context, info, adapter)
    output = Path(output); parent = directory(output.parent, private=True)
    need(output.is_absolute() and output.anchor == '/' and '..' not in output.parts and
         not output.exists() and not output.is_symlink(), 'fresh private output directory required')
    need(all(not output.is_relative_to(path.parent) for path in paths.values()),
         'private continuation must be outside all input directories')
    input_directory_ids = {(path.parent.stat().st_dev,path.parent.stat().st_ino) for path in paths.values()}
    need(all((ancestor.stat().st_dev,ancestor.stat().st_ino) not in input_directory_ids
             for ancestor in (parent,*parent.parents)), 'output parent aliases an input directory')
    output.mkdir(mode=0o700)
    audit['stage'] = 'capture_released_predictions'
    opaque = output/'opaque.json'; original = output/'original.json'
    opaque_body = canonical(accepted['predictions']); write_private(opaque, opaque_body, audit)
    audit['stage'] = 'original_private_restoration'
    # The unchanged helper may read four16MiB JSON documents and write one16MiB
    # result before our postflight. Charge those actual source caps, including
    # changed-input and failed-call paths, rather than observed preflight sizes.
    audit['metadata_read_charge_bytes'] += 4 * (materials.MAX_JSON_BYTES + 1)
    audit['write_charge_upper_bytes'] += materials.MAX_JSON_BYTES
    receipt = materials.restore_predictions(paths['panel'], paths['mapping'], paths['materials'], opaque, original,
        expected_panel_identity=expected_panel_identity, expected_mapping_identity=expected_mapping_identity,
        expected_materials_identity=info['materials_identity'])
    restored, original_pin = read_document(original, materials, cap=MAX_RESULT, audit=audit)
    need(restored['candidate_submission_identity'] == adapter.digest(accepted['predictions']) and
         restored['panel_identity'] == expected_panel_identity and
         restored['private_mapping_identity'] == expected_mapping_identity and
         restored['materials_identity'] == info['materials_identity'] and receipt['test_predictions'] == 1803,
         'unchanged private restorer output bindings differ')
    audit['stage'] = 'verify_unchanged_inputs'
    for key,path in paths.items(): read_document(path, materials, expected=captured[key][1], audit=audit)
    read_document(opaque, materials, expected=pin(opaque_body), cap=MAX_RESULT+1, audit=audit)
    binding = {'schema':'reve-release-restoration-binding-v1', 'release':accepted['release'],
               'expected_context':deepcopy(expected_context), 'panel_identity':expected_panel_identity,
               'mapping_identity':expected_mapping_identity, 'data_identity':expected_data_identity,
               'preprocessing_profile':document['data']['profile'],
               'input_pins':{key:item[1] for key,item in captured.items()},
               'opaque':{'name':'opaque.json',**pin(opaque_body)},
               'restored':{'name':'original.json',**original_pin}, 'native_restoration_receipt':receipt,
               'runtime_qualified':False,'scientific_qualification':False,'current_paper_win_qualified':False,
               'scope':'release binding and original-ID restoration only; no independent execution attestation or scoring'}
    body = canonical(binding); need(len(body) <= 65536, 'bounded private binding required')
    audit['stage'] = 'publish_binding'
    pending = output/'BINDING.pending.json'; write_private(pending, body, audit)
    need(not (output/'BINDING.json').exists() and not (output/'BINDING.json').is_symlink(), 'binding already exists')
    os.rename(pending, output/'BINDING.json')
    return {'binding_pin':pin(body), 'output':str(output), 'scientific_qualification':False,
            'created_file_bytes':len(opaque_body)+original_pin['bytes']+len(body), 'accounting':deepcopy(audit)}


def verify(output, *, expected_binding_pin, expected_context, expected_data_identity,
           expected_panel_identity, expected_mapping_identity, original_like_only=False):
    """Read the externally pinned binding; return bound documents, never authority."""
    adapter, materials = dependencies(); root = directory(output, private=True)
    adapter.descriptor(expected_binding_pin)
    binding, _ = read_document(root/'BINDING.json', materials, expected_binding_pin, cap=65536)
    need(type(expected_context) is dict and set(expected_context) == CONTEXT and
         set(binding) == {'schema','release','expected_context','panel_identity','mapping_identity','data_identity',
                          'preprocessing_profile','input_pins','opaque','restored','native_restoration_receipt',
                          'runtime_qualified','scientific_qualification','current_paper_win_qualified','scope'},
         'closed bound restoration and context schema required')
    need(binding['schema'] == 'reve-release-restoration-binding-v1' and
         binding['expected_context'] == expected_context and binding['data_identity'] == expected_data_identity and
         binding['panel_identity'] == expected_panel_identity and binding['mapping_identity'] == expected_mapping_identity,
         'bound restoration context differs')
    need(binding['runtime_qualified'] is False and binding['scientific_qualification'] is False and
         binding['current_paper_win_qualified'] is False, 'restoration cannot promote qualification')
    release = binding['release']
    need(type(release) is dict and set(release) == RELEASE_FIELDS and
         all(release[key] == expected_context[key] for key in CONTEXT), 'release was detached from retained context')
    need(adapter.digest({k:v for k,v in release.items() if k != 'release_identity'}) == release['release_identity'] and
         release['scientific_qualification'] is False and release['current_paper_win_qualified'] is False and
         release['requires_separate_outcome_binding'] is (release['profile'] == PROFILES[1]),
         'retained release identity or qualification declarations differ')
    need(type(original_like_only) is bool, 'explicit original-like routing boolean')
    if original_like_only:
        need(release['profile'] == PROFILES[0] and release['requires_separate_outcome_binding'] is False,
             'prospective full-test-context release cannot enter unchanged original-like outcome route')
    need(binding['opaque']['name'] == 'opaque.json' and binding['restored']['name'] == 'original.json',
         'closed private output names required')
    predictions, op = read_document(root/'opaque.json', materials,
        {k:binding['opaque'][k] for k in ('bytes','sha256')}, cap=MAX_RESULT+1)
    restored, rp = read_document(root/'original.json', materials,
        {k:binding['restored'][k] for k in ('bytes','sha256')}, cap=MAX_RESULT)
    need(op == release['predictions_pin'] and restored['candidate_submission_identity'] == adapter.digest(predictions) and
         restored['panel_identity'] == expected_panel_identity and
         restored['materials_identity'] == expected_context['materials_identity'] and
         restored['private_mapping_identity'] == expected_mapping_identity and len(restored['predictions']) == 1803,
         'private numerical artifact joins differ')
    return {'binding':binding,'binding_pin':deepcopy(expected_binding_pin),
            'restored':restored,'restored_path':str(root/'original.json'),'restored_pin':rp,
            'runtime_qualified':False,'scientific_qualification':False}


def join_score(output, score_path, *, expected_score_pin, **verification):
    """Pure metadata join; the native score and metrics remain unchanged.

    The caller must independently capture the actual score bytes and retain its
    exact byte pin. Serialization is preserved in that identity; canonical JSON
    document hashes are not substituted. No scorer is called here.
    """
    verified = verify(output, **verification)
    adapter, materials = dependencies()
    adapter.descriptor(expected_score_pin)
    score_document, score_pin = read_document(Path(score_path), materials, expected_score_pin)
    binding = verified['binding']
    need(score_document.get('prediction_file_sha256') == verified['restored_pin']['sha256'] and
         score_document.get('panel_identity') == binding['panel_identity'] and
         score_document.get('profile') == binding['preprocessing_profile'],
         'native score must identify the exact restored bytes, panel and preprocessing profile')
    return {'schema':'reve-release-bound-native-score-v1','restoration_binding_pin':deepcopy(verified['binding_pin']),
            'release':deepcopy(binding['release']),'native_score_pin':score_pin,
            'native_score':deepcopy(score_document),'scientific_qualification':False,
            'current_paper_win_qualified':False,'scope':'private score provenance only; native metrics unchanged'}
