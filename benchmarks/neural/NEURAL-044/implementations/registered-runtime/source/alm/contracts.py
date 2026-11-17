"""Finite metadata contracts; configuration records facts, never grants authority."""
import hashlib
import json
import math
from pathlib import PurePosixPath

TASKS = ('NEURAL-043', 'NEURAL-044')
RELEASE = '001612/0.250927.1801'
GATES = (
    'complete_release_local_identity', 'full_mouse_session_population',
    'nwb_field_mapping', 'roi_region_table_identity', 'cross_epoch_roi_identity',
    'exposure_and_clock_alignment', 'tracking_movement_onset',
    'calcium_processing_temporal_support', 'target_grid_identity',
    'stimulation_assignment_schedule', 'artifact_mask_and_power_units',
    'independent_tuning_split', 'protocol_selection', 'code_license',
    'private_packet_separation', 'provider_sandbox_and_resource_owner',
    'native_dependencies', 'reference_and_controls', 'scorer_replication',
    'scientific_qualification', 'central_registration', 'publication',
)

class Refusal(ValueError):
    pass

def require(condition, reason):
    if not condition:
        raise Refusal(reason)

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()

def unique(rows, name):
    require(len(rows) == len(set(rows)), 'duplicate ' + name)

def finite(value):
    require(type(value) in (int, float) and math.isfinite(value), 'nonfinite scalar')
    return value

def local_name(value):
    p = PurePosixPath(value)
    require(bool(value) and not p.is_absolute() and '..' not in p.parts and
            '.' not in p.parts and str(p) == value, 'noncanonical relative path')
    return value

def scalar_text(value):
    if isinstance(value, bytes):
        value = value.decode('utf8', 'strict')
    require(isinstance(value, str) and bool(value), 'empty/non-text identity')
    return value

def metadata_contract(manifest):
    require(manifest['release'] == RELEASE, 'wrong fixed release')
    require(manifest['mapping_status'] == 'field_verified', 'mapping is not field verified')
    require(manifest['population_status'] == 'complete_release_disposition', 'partial population')
    rows = manifest['recordings']
    unique([r['asset_id'] for r in rows], 'asset')
    unique([(r['mouse'], r['session']) for r in rows], 'mouse/session recording')
    require(len(rows) == 61 and len({r['mouse'] for r in rows}) == 15,
            'release roster does not cover 61 files / 15 mice')
    for r in rows:
        local_name(r['path'])
        require(r['disposition'] in ('include', 'exclude'), 'missing asset disposition')
        require(bool(r['reason']), 'missing inclusion/exclusion reason')
        require(type(r['bytes']) is int and r['bytes'] > 0, 'invalid extent')
        require(len(r['sha256']) == 64 and all(c in '0123456789abcdef' for c in r['sha256']), 'bad hash')
        require(r['scope'] in ('behavior', 'behavior_and_stimulation'), 'unknown recording scope')
    stim=[r for r in rows if r['scope']=='behavior_and_stimulation']
    require(len(stim)==52 and len({r['mouse'] for r in stim})==13,
            'source disposition must reconcile reported 52 stimulation sessions / 13 mice')
    return rows

def prediction_identity(row):
    return (row['mouse'], row['session'], row['trial_id'])

def stimulus_identity(row):
    return (row['mouse'], row['session'], row['epoch'], row['stim_id'])

def readiness():
    return {'tasks': list(TASKS), 'gates': {x: False for x in GATES},
            'runnable': False, 'registered': False, 'research_qualified': False,
            'submission_ready': False, 'source_only': True}
