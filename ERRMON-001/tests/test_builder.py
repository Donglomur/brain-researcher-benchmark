"""Source-free bank construction/safety mechanics; no released EEG is read."""
import copy
import os
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
import build_reference as b
import proof_of_work as p
from fixture_support import toy_reference


def test_toy_bank_roundtrip(tmp_path):
    ref = toy_reference(); path = tmp_path / 'toy.npz'
    b.write_bank(path, ref)
    got = p.load_reference(path)
    np.testing.assert_array_equal(got['epochs'], ref['epochs'])
    with pytest.raises(FileExistsError):
        b.write_bank(path, ref)


@pytest.mark.parametrize('mode', ['existing', 'same', 'nested', 'source', 'source_parent', 'dotdot', 'method'])
def test_unsafe_destinations(tmp_path, mode):
    source = tmp_path / 'source'; source.mkdir()
    method = tmp_path / 'method.json'; method.write_text('{}')
    out = tmp_path / 'new' / 'bank.npz'; report = tmp_path / 'report.json'
    if mode == 'existing': out.parent.mkdir(); out.write_bytes(b'preserve')
    elif mode == 'same': report = out
    elif mode == 'nested': report = out / 'report.json'
    elif mode == 'source': out = source / 'bank.npz'
    elif mode == 'source_parent': out = tmp_path
    elif mode == 'dotdot': out = tmp_path / 'source' / '..' / 'source' / 'bank.npz'
    elif mode == 'method': out = method
    with pytest.raises(AssertionError):
        b.destinations(source, method, out, report)
    assert list(source.iterdir()) == []


@pytest.mark.parametrize('mode', ['leaf', 'ancestor', 'dangling'])
def test_symlink_destinations(tmp_path, mode):
    source = tmp_path / 'source'; source.mkdir()
    method = tmp_path / 'method'; method.write_text('{}')
    actual = tmp_path / 'actual'; actual.mkdir()
    link = tmp_path / 'link'
    link.symlink_to(actual if mode != 'dangling' else tmp_path / 'missing')
    out = link / 'bank' if mode == 'ancestor' else link
    with pytest.raises(AssertionError, match='symlink'):
        b.destinations(source, method, out, tmp_path / 'report')


def test_fifo_rejected_before_open(tmp_path):
    path = tmp_path / 'fifo'; os.mkfifo(path)
    with pytest.raises(AssertionError, match='regular'):
        p.read_json(path)


def test_source_method_pin_fails_before_fif(tmp_path):
    source = tmp_path / 'source'; source.mkdir()
    method = tmp_path / 'method'; method.write_text('{}')
    with pytest.raises(AssertionError, match='fingerprint'):
        b.load_inputs(source, method)


@pytest.mark.parametrize('mode', ['directory', 'extra', 'fifo'])
def test_inventory_is_closed(tmp_path, monkeypatch, mode):
    # Bypass digests ONLY in this manufactured inventory test, before member reads.
    source = tmp_path / 'source'; source.mkdir()
    method = p.public_method_path()
    manifest = p.read_json(method.parents[0] / 'source_manifest.json')
    import json
    (source / 'source_manifest.json').write_text(json.dumps(manifest))
    for row in manifest['files']:
        (source / row['path']).touch()
    if mode == 'directory': (source / 'unexpected').mkdir()
    elif mode == 'extra': (source / 'unexpected').touch()
    else: os.mkfifo(source / 'unexpected')
    monkeypatch.setattr(p, 'sha256', lambda path: p.METHOD_SHA if Path(path) == method else p.SOURCE_SHA)
    with pytest.raises(AssertionError, match='inventory'):
        b.load_inputs(source, method)


def fake_raw():
    ref = toy_reference(); method = ref['method']; inp = method['input']
    base = ref['annotations']
    raw = SimpleNamespace(n_times=inp['n_samples'], first_samp=0,
        ch_names=inp['eeg_channels'] + inp['eog_channels'],
        get_channel_types=lambda: ['eeg'] * 30 + ['eog'] * 3,
        info=dict(sfreq=1024., bads=[], projs=[], custom_ref_applied=1, meas_date=None,
                  chs=[dict(unit=107, unit_mul=0, range=1., cal=9.999999974752427e-7) for _ in range(33)]),
        annotations=SimpleNamespace(orig_time=None, onset=np.array([r['onset_s'] for r in base]),
                   duration=np.zeros(len(base)), description=np.array([r['description'] for r in base])))
    return raw, method


def test_manufactured_header_and_original_indices():
    raw, method = fake_raw(); annotations, trials = b.header_and_events(raw, method)
    assert len(annotations) == 14 and len(trials) == 6


@pytest.mark.parametrize('mode', ['sfreq', 'n_times', 'first_samp', 'channels', 'bad', 'projector', 'reference',
                                'date', 'unit', 'unit_mul', 'cal', 'range', 'origin', 'duration', 'bad_annotation',
                                'nonfinite', 'outside', 'tie'])
def test_source_preconditions(mode):
    raw, method = fake_raw()
    if mode == 'sfreq': raw.info['sfreq'] = 1024.01
    elif mode == 'n_times': raw.n_times -= 1
    elif mode == 'first_samp': raw.first_samp = 1
    elif mode == 'channels': raw.ch_names[0] = 'Other'
    elif mode == 'bad': raw.info['bads'] = ['FCz']
    elif mode == 'projector': raw.info['projs'] = [{}]
    elif mode == 'reference': raw.info['custom_ref_applied'] = 0
    elif mode == 'date': raw.info['meas_date'] = 123
    elif mode in ('unit', 'unit_mul', 'cal', 'range'): raw.info['chs'][0][mode] = 2
    elif mode == 'origin': raw.annotations.orig_time = 123
    elif mode == 'duration': raw.annotations.duration[0] = .1
    elif mode == 'bad_annotation': raw.annotations.description[0] = 'BAD'
    elif mode == 'nonfinite': raw.annotations.onset[0] = np.nan
    elif mode == 'outside': raw.annotations.onset[0] = -1
    elif mode == 'tie': raw.annotations.onset[2] = raw.annotations.onset[1]
    with pytest.raises(AssertionError):
        b.header_and_events(raw, method)


def test_no_oracle_or_old_bank_inputs():
    text = Path(b.__file__).read_text()
    assert 'solution.compute' not in text and 'allow_pickle=True' not in text
    assert text.index('ref = construct(source, method)') < text.index('p.validate_output_directory(args.oracle_output')
