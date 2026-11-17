"""Trusted post-closure candidate capture/assembly; no scientific scoring."""
import io
import json
import math
import zipfile
import numpy as np

from contract import CONDITION, encoded, need, pin


def strict_json(body):
    def pairs(rows):
        result = {}
        for key,value in rows:
            need(key not in result, 'duplicate output metadata key'); result[key] = value
        return result
    def finite(raw):
        value = float(raw); need(math.isfinite(value), 'finite output metadata'); return value
    return json.loads(body, object_pairs_hook=pairs, parse_constant=lambda _: need(False, 'finite output metadata'), parse_float=finite)


def closed(result):
    need(result.get('status') == 'captured' and result.get('all_resources_closed') is True
         and result.get('cli_reaped') is True and result.get('candidate_closed_before_capture') is True,
         'trusted complete context closure before capture')
    observed = result.get('natural_exit', {})
    need(observed == {'Status':'exited','Running':False,'Dead':False,'Pid':0,'ExitCode':0,'OOMKilled':False},
         'observed natural zero exit without OOM')
    records = result.get('closures', [])
    need(len(records) == 3 and all(row.get('closed') is True for row in records)
         and sorted(row['kind'] for row in records) == ['container','container','volume'],
         'all three owned resources closed')


def collect_fold(binding, result, captured_root, current):
    """Result is supplied by the trusted live lifecycle, never a participant file."""
    closed(result)
    rows = result['outputs']
    need(len(rows) == 2 and {r['path'] for r in rows} == {'fold.json','predictions.npy'}, 'exact trusted captured output roster')
    by_name = {r['path']:r for r in rows}
    fold = strict_json(current.read_pinned(captured_root, by_name['fold.json'], limit=100_000))
    expected = {'schema':'spinal_current_fold_prediction_v1', 'condition_id':CONDITION,
                'held_neuron':binding['held_neuron'], 'arm':binding['arm'], 'purpose':binding['purpose'],
                'program_seal_sha256':binding['program_seal']['sha256'], 'binding_sha256':pin(encoded(binding))['sha256'],
                'unit':binding['output_unit'], 'query_recording_ids':[r['recording_id'] for r in binding['query_records']]}
    need(fold == expected, 'candidate output must match trusted fold binding exactly')
    total = sum(row['samples'] for row in binding['query_records'])
    need(0 < total and 8 * total + 1036 <= 1_000_000, 'whole held-fold extent fits reviewed capture')
    body = current.read_pinned(captured_root, by_name['predictions.npy'], limit=8 * total + 1036)
    # Reuse the existing bounded numerical decoder; the wrapper is operator-made.
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('candidate.npy', body)
    vector = current.read_npz_bytes(stream.getvalue(), {'candidate':('numeric',total)})['candidate']
    values = {}; offset = 0
    for row in binding['query_records']:
        n = row['samples']
        need(row['offset'] == offset and n > 64, 'frozen complete query recording boundaries')
        prediction = vector[offset:offset+n]
        need(np.isfinite(prediction[32:-32]).all(), 'finite predictions on immutable source support')
        need(row['recording_id'] not in values, 'unique held recording')
        values[row['recording_id']] = prediction.astype('<f8')
        offset += n
    need(offset == total, 'whole held-vector accounting')
    return values


def manifest(bank, unit, recordings, provenance):
    need(unit in ('hz','expected_spikes_per_bin'), 'fixed candidate unit')
    need(len(recordings) == 116 and {r['recording_id'] for r in recordings} == {r['recording_id'] for r in bank.eligible},
         'all116 original eligible predictions required')
    return {'schema':'spinal_current_prediction_bundle_v1', 'role':'candidate', 'condition_id':CONDITION,
            'bank_manifest_sha256':bank.manifest_sha256, 'methods':{'candidate':unit},
            'recordings':recordings, 'provenance_note':provenance}
