"""Gated genuine-output authoring QA, EXCLUDED from the production test.sh.

Requires caller-owned session original_reference and explicit
REPAIR_ORACLE_OUTPUT. No original reconstruction or source-table reads here.
Equivalent transformations are QA on the chosen genuine fixture only, never
additional acceptance requirements on arbitrary valid agent artifacts.
"""
from contextlib import contextmanager
import csv
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

import pytest

import actual_control_helpers as h
import output_contract as c


def encode(value):
    if isinstance(value, Decimal): return float(value)
    raise TypeError('not a JSON receipt type')


def fingerprints(root):
    return {name: hashlib.sha256(c.io.read_bytes(root / name, c.io.CAPS[
        'csv' if name.endswith('.csv') else 'json' if name.endswith('.json') else 'text'])).hexdigest()
            for name in c.io.REQUIRED}


@pytest.fixture(scope='session')
def genuine(original_reference):
    path = os.environ.get('REPAIR_ORACLE_OUTPUT')
    assert path, 'Authoring-only genuine QA requires explicit REPAIR_ORACLE_OUTPUT; no skip or default source run.'
    root = c.io.guarded_path(Path(path), directory=True)
    hashes = fingerprints(root)
    baseline = c.validate(root, original_reference)
    docs = c.io.read_artifacts(root)
    yield dict(root=root, reference=original_reference, documents=docs, baseline=baseline)
    assert fingerprints(root) == hashes, 'Genuine fixture changed during authoring QA'


@contextmanager
def detached(genuine, candidate, tmp_path):
    # One unique owned directory per case, removed immediately afterwards;
    # no accumulating copies, hardlinks or writes through to genuine outputs.
    root = Path(tempfile.mkdtemp(prefix='fcmatur-authoring-', dir=tmp_path))
    try:
        for name in c.io.REQUIRED:
            shutil.copyfile(genuine['root'] / name, root / name)
            assert (root / name).stat().st_ino != (genuine['root'] / name).stat().st_ino or \
                   (root / name).stat().st_dev != (genuine['root'] / name).stat().st_dev
            if candidate[name] == genuine['documents'][name]: continue
            if name.endswith('.csv'):
                rows = candidate[name]
                fields = list(rows[0]) if rows else list(c.CSV_COLUMNS)
                with (root / name).open('w', newline='') as stream:
                    writer = csv.DictWriter(stream, fieldnames=fields)
                    writer.writeheader(); writer.writerows(rows)
            elif name.endswith('.json'):
                (root / name).write_text(json.dumps(candidate[name], allow_nan=False, default=encode))
            else:
                (root / name).write_text(candidate[name])
        yield root
    finally:
        shutil.rmtree(root)


def recorded(record_property, details):
    record_property('control_mode', details['mode'])
    record_property('control_category', details['category'])
    record_property('prevalidation_classification', details['status'])
    record_property('effect_count', details['effect']['n_changed'])
    record_property('numeric_effect_count', details['effect'].get('n_numeric_changes', 0))
    record_property('inference_status_effect_count', details['effect'].get('n_inference_status_changes', 0))
    record_property('effect_max_absolute_gap', str(details['effect']['max_absolute_gap']))
    record_property('control_details', json.dumps(details, default=encode, sort_keys=True))


def test_genuine_baseline(genuine, record_property):
    assert genuine['baseline']['status'] == 'accepted'
    record_property('control_category', 'positive')
    record_property('control_outcome', 'accepted_genuine')


@pytest.mark.parametrize('mode', h.POSITIVES)
def test_equivalent_representation(genuine, tmp_path, record_property, mode):
    candidate, details = h.positive_candidate(mode, genuine['documents'], genuine['reference'])
    recorded(record_property, details)
    if candidate is None:
        assert details['status'] == 'not_constructed' and details['reason']
        record_property('control_outcome', 'positive_not_constructed')
        return
    with detached(genuine, candidate, tmp_path) as root:
        assert c.validate(root, genuine['reference'])['status'] == 'accepted'
    record_property('control_outcome', 'accepted_positive')


@pytest.mark.parametrize('mode', h.NUMERICAL)
def test_numerical_component(genuine, tmp_path, record_property, mode):
    candidate, details = h.numerical_candidate(mode, genuine['documents'], genuine['reference'])
    recorded(record_property, details)
    if candidate is None:
        assert details['status'] in ('unavailable', 'not_constructed') and details['reason']
        record_property('control_outcome', details['status'])
        return
    assert candidate['run_metadata.json'] == genuine['documents']['run_metadata.json']
    if mode != 'stale_affine_receipts':
        assert candidate['connectivity.csv'] == genuine['documents']['connectivity.csv']
    with detached(genuine, candidate, tmp_path) as root:
        assert (root / 'run_metadata.json').read_bytes() == (genuine['root'] / 'run_metadata.json').read_bytes()
        if mode != 'stale_affine_receipts':
            assert (root / 'connectivity.csv').read_bytes() == (genuine['root'] / 'connectivity.csv').read_bytes()
        if details['status'] == 'effective':
            assert details['effect']['n_changed'] > 0
            with pytest.raises((ValueError, TypeError)) as error:
                c.validate(root, genuine['reference'])
            record_property('rejection_reason', str(error.value))
            outcome = ('effective_numerical_rejection' if details['effect']['n_numeric_changes']
                       else 'effective_inference_status_rejection')
            record_property('control_outcome', outcome)
        else:
            assert details['status'] == 'nondiscriminating' and details['effect']['n_changed'] == 0
            assert c.validate(root, genuine['reference'])['status'] == 'accepted'
            record_property('control_outcome', 'nondiscriminating')


@pytest.mark.parametrize('mode', h.BINDING)
def test_binding_component(genuine, tmp_path, record_property, mode):
    candidate, details = h.binding_candidate(mode, genuine['documents'], genuine['reference'])
    recorded(record_property, details)
    if candidate is None:
        assert details['status'] == 'unavailable' and details['reason']
        record_property('control_outcome', 'unavailable')
        return
    with detached(genuine, candidate, tmp_path) as root:
        if details['status'] == 'effective':
            assert details['effect']['n_changed'] > 0 and details['reason']
            with pytest.raises((ValueError, TypeError)) as error:
                c.validate(root, genuine['reference'])
            record_property('rejection_reason', str(error.value))
            record_property('control_outcome', 'effective_binding_rejection')
        else:
            assert details['status'] == 'nondiscriminating'
            assert c.validate(root, genuine['reference'])['status'] == 'accepted'
            record_property('control_outcome', 'nondiscriminating')
