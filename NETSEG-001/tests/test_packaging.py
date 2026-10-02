"""Source-free packaging checks; these do not establish scientific validity."""
from pathlib import Path
import re
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_shell_entrypoints_are_executable():
    for name in ('solution/solve.sh', 'tests/test.sh'):
        assert (ROOT / name).stat().st_mode & 0o111, name


def test_runtime_is_offline_cpu_and_bounded():
    config = tomllib.loads((ROOT / 'task.toml').read_text())
    env = config['environment']
    assert env['allow_internet'] is False
    assert env['gpus'] == 0 and env['cpus'] == 2 and env['memory_mb'] == 8192
    assert config['metadata']['category'] == 'Method control'
    assert config['metadata']['difficulty'] == 'easy'


def test_harvest_includes_output_and_both_public_contracts():
    config = tomllib.loads((ROOT / 'task.toml').read_text())
    assert set(config['artifacts']) == {
        '/app/output', '/app/data/netseg/source_manifest.json', '/app/method_contract.json'}


def test_verifier_uses_preinstalled_python_and_initializes_zero_reward():
    script = (ROOT / 'tests/test.sh').read_text()
    assert 'set -euo pipefail' in script and 'python3 -m pytest' in script
    assert script.index('echo 0 > /logs/verifier/reward.txt') < script.index('python3 -m pytest')
    assert '--junitxml=/logs/verifier/junit.xml' in script
    assert not any(token in script for token in ('apt-get', 'pip install', 'uvx', 'curl ', 'wget ', '$HOME'))


def test_pinned_base_and_required_dependencies_are_build_time_only():
    docker = (ROOT / 'environment/Dockerfile').read_text()
    assert re.search(r'^FROM ubuntu:24\.04@sha256:[0-9a-f]{64} AS dependencies$', docker, re.M)
    for name, version in {'numpy': '2.1.3', 'scipy': '1.14.1', 'pandas': '2.2.3',
                          'nibabel': '5.3.2', 'scikit-learn': '1.5.2',
                          'nilearn': '0.12.1', 'pytest': '8.4.1', 'pytest-json-ctrf': '0.3.5'}.items():
        assert f'{name}=={version}' in docker
    assert 'COPY --from=source /app/data/netseg /app/data/netseg' in docker
    assert 'COPY method_contract.json /app/method_contract.json' in docker
    assert 'stage_data.py --destination /app/data/netseg' in docker


def test_image_inputs_do_not_include_solutions_tests_or_answers():
    docker = (ROOT / 'environment/Dockerfile').read_text()
    copies = [line for line in docker.splitlines() if line.startswith(('COPY ', 'ADD '))]
    assert copies
    assert not any(re.search(r'(^|[ /])(solution|tests|reference|output)([ /.]|$)', line) for line in copies)
    assert not (ROOT / 'tests/reference.npz').exists()


@pytest.mark.parametrize('filename', ['instruction.md', 'proposal.md'])
def test_no_runtime_download_or_old_answer_narrative(filename):
    text = (ROOT / filename).read_text()
    assert 'method' in text.lower() and 'offline' in text.lower()
    assert '0.374' not in text and '0.554' not in text and 'un-cued lever' not in text
    assert 'fetched at runtime' not in text


def test_public_scoring_and_failure_boundary():
    text = (ROOT / 'instruction.md').read_text()
    assert 'Scoring is binary' in text and 'no proportional partial credit' in text
    assert 'failure_receipt.json' in text
    assert 'No effect direction or significance is required' in text
