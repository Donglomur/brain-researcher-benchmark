"""Exact inherited public panel identity; hashes public activity, not targets."""
import hashlib,json,numpy as np
PUBLIC_KEYS={'train_counts_heldin','train_counts_heldout','eval_counts_heldin','train_trial_ids','eval_trial_ids','heldin_unit_ids','heldout_unit_ids','bin_left_edges_ms','train_condition_ids','eval_condition_ids','eval_valid_mask','panel_fingerprint','source_manifest_sha256'}

def compute_panel_fingerprint(packet):
    """Canonical public-only digest; an integrity binding, not an exposure proof.

    Source-manifest digest must refer to operator-validated source versions, asset
    hashes and trial/unit/clock mappings. Never include target counts/null means.
    """
    fields={}
    for key in sorted(PUBLIC_KEYS-{'panel_fingerprint','source_manifest_sha256'}):
        value=np.asarray(packet[key])
        if key.endswith('_ids'):
            encoding='utf8-json-unicode-list-v1'
            payload=json.dumps(value.tolist(),ensure_ascii=False,separators=(',',':')).encode('utf8')
        elif key=='eval_valid_mask':
            encoding='uint8-c-order';payload=np.asarray(value,dtype='u1').tobytes(order='C')
        elif key=='bin_left_edges_ms':
            encoding='little-endian-float64-c-order';payload=np.asarray(value,dtype='<f8').tobytes(order='C')
        else:
            encoding='little-endian-int64-c-order';payload=np.asarray(value,dtype='<i8').tobytes(order='C')
        fields[key]={'shape':list(value.shape),'encoding':encoding,'sha256':hashlib.sha256(payload).hexdigest()}
    frame={'schema':'nlb-cosmoothing-public-v1','source_commit':'42f8410b88e12db136910fa2f888b025ea0aa2ae',
           'dandiset_version':'000128/0.220113.0400','bin_ms':5,'counts_units':'spikes_per_bin',
           'source_manifest_sha256':packet['source_manifest_sha256'],'fields':fields}
    return hashlib.sha256(json.dumps(frame,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf8')).hexdigest()
