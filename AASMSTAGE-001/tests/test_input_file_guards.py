"""Source-free pre-read guards; FIFOs must never be opened or block a run."""
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

TASK = Path(__file__).parents[1]
sys.path.insert(0, str(TASK/'solution'))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


oracle = load_module('aasmstage_input_guard_oracle', TASK/'solution'/'compute.py')
stage = load_module('aasmstage_input_guard_stage', TASK/'environment'/'stage_data.py')


def invalid_path(root, mode):
    path = root/'input.json'
    if mode == 'fifo':
        os.mkfifo(path)
    elif mode == 'directory':
        path.mkdir()
    elif mode in ('symlink', 'dangling'):
        target = root/'target'
        if mode == 'symlink':
            target.write_bytes(b'unchanged')
        path.symlink_to(target)
    elif mode == 'ancestor':
        target = root/'target'; target.mkdir(); (target/'input.json').write_bytes(b'unchanged')
        link = root/'linked'; link.symlink_to(target, target_is_directory=True)
        path = link/'input.json'
    return path


@pytest.mark.parametrize('reader', ['method', 'manifest'])
@pytest.mark.parametrize('mode', ['fifo', 'directory', 'symlink', 'dangling', 'ancestor', 'missing'])
def test_nonregular_and_symlink_inputs_rejected_before_read(tmp_path, monkeypatch, reader, mode):
    path = invalid_path(tmp_path, mode)
    calls = []

    def no_read(self):
        calls.append(str(self))
        pytest.fail('Non-regular/symlink input must be rejected before any read')

    monkeypatch.setattr(Path, 'read_bytes', no_read)
    with pytest.raises(ValueError, match='regular file|[Ss]ymlink'):
        if reader == 'method':
            oracle.load_inputs(tmp_path/'unused-source', path)
        else:
            stage.read_manifest(path)
    assert not calls


@pytest.mark.parametrize('kind', ['method', 'manifest'])
def test_fifo_failure_writes_parseable_artifacts_without_source_processing(tmp_path, monkeypatch, kind):
    source = tmp_path/'source'; source.mkdir()
    method = TASK/'environment'/'method_contract.json'
    fifo = tmp_path/'method.json' if kind == 'method' else source/'source_manifest.json'
    os.mkfifo(fifo)
    if kind == 'method':
        method = fifo
    output, private = tmp_path/'output', tmp_path/'private'
    monkeypatch.setattr(sys, 'argv', ['compute.py', '--data-dir', str(source), '--method-contract', str(method),
                                    '--output-dir', str(output), '--private-dir', str(private)])
    monkeypatch.setattr(oracle, 'inspect_subject', lambda *_: pytest.fail('EEG/source processing is forbidden'))
    assert oracle.main() == 1
    for name in ('run_metadata.json', 'staging_results.json'):
        result = json.loads((output/name).read_text())
        assert result['status'] == 'failed_precondition' and 'regular file' in result['reason']
    assert (output/'findings.md').read_text().strip()
    assert fifo.exists() and not fifo.is_file()
