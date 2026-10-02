"""Read public metadata/code only; never open old references or originals."""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import pytest

ENV = Path(__file__).parents[1] / 'environment'


def test_exact_portable_manifest_pin():
    raw = (ENV / 'source_manifest.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '18fd1271190687765461243943ced2b82d5d5fb703c3d675a2f7586992b5f932'
    document = json.loads(raw)
    assert document['n_original_files'] == len(document['files']) == 121
    assert document['total_original_bytes'] == sum(r['size_bytes'] for r in document['files']) == 4_997_109_352
    assert len({r['path'] for r in document['files']}) == 121
    assert sum(r['role'] == 'surface_timeseries' for r in document['files']) == 118
    assert len({r['subject_id'] for r in document['files'] if r['role'] == 'surface_timeseries'}) == 59
    assert {r['nitrc_file_id'] for r in document['files']} == (set(range(8260, 8380)) - {8342, 8343}) | {8470, 9342, 9343}


def test_provenance_does_not_assert_publisher_hash_or_license():
    document = json.loads((ENV / 'source_manifest.json').read_text())
    assert 'not publisher' in document['identity_policy']
    assert 'unresolved' in document['redistribution_license']
    assert document['provenance']['code_license_not_substituted_for_data_license'] is True
    assert document['provenance']['nilearn_tag'] == '0.13.1'
    text = json.dumps(document)
    assert '/home/' not in text and 'cache_path' not in text


def test_three_stage_portable_originals_only():
    text = (ENV / 'Dockerfile').read_text()
    assert 'ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3 AS dependencies' in text
    assert 'FROM dependencies AS source' in text and 'FROM dependencies AS runtime' in text
    assert 'RUN python3 /opt/source/stage_data.py --destination /app/data/lifespan' in text
    assert 'COPY --from=source /app/data/lifespan /app/data/lifespan' in text
    assert 'COPY stage_data.py source_manifest.json /opt/source/' in text
    assert 'COPY cohort_manifest.json method_contract.json output_contract.md SOURCE_NOTICE.md /app/' in text
    for forbidden in ['build_bundle', 'BUNDLE_DIR', 'solution', 'tests/', 'reference.npz', 'fetch_surf_nki', 'rm -rf /root', '/home/', ':local']:
        assert forbidden not in text
    runtime = text.split('FROM dependencies AS runtime', 1)[1]
    assert 'RUN ' not in runtime


@pytest.mark.parametrize('pin', ['numpy==2.1.3', 'scipy==1.14.1', 'pandas==2.2.3', 'nibabel==5.3.2',
                                  'scikit-learn==1.5.2', 'nilearn==0.12.1', 'pytest==8.4.1', 'pytest-json-ctrf==0.3.5'])
def test_reviewed_exact_dependency_pins(pin):
    assert pin in (ENV / 'Dockerfile').read_text()


@pytest.mark.parametrize('name', ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'])
def test_single_thread_runtime(name):
    assert name + '=1' in (ENV / 'Dockerfile').read_text()


def test_stager_has_no_scientific_imports_or_host_dependency():
    text = (ENV / 'stage_data.py').read_text()
    tree = ast.parse(text)
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): names.extend(x.name.split('.')[0] for x in node.names)
        elif isinstance(node, ast.ImportFrom): names.append(node.module.split('.')[0])
    assert not {'numpy', 'nibabel', 'nilearn', 'pandas', 'sklearn'} & set(names)
    assert '/home/' not in text and 'read1(' in text
    assert "if __name__ == '__main__':" in text


def test_grader_wrapper_resets_numeric_threads_without_launching_pytest(tmp_path):
    script = (ENV.parent / 'tests/test.sh').read_text()
    variables = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')
    for key in variables:
        assert key + '=1' in script
    assert 'PYTHONDONTWRITEBYTECODE=1' in script
    assert script.index('OMP_NUM_THREADS=1') < script.index('python3 -m pytest')
    # Only redirect the immutable script's log namespace into this fixture's
    # temporary directory. Execute through bash stdin, not a /tmp executable.
    logs = tmp_path / 'logs'; logs.mkdir()
    adapted = script.replace('/logs/verifier', str(logs))
    assert '/logs/verifier' not in adapted
    stub = '''python3() {
  /usr/bin/printf 'captured_threads=%s,%s,%s,%s,%s\\n' "$OMP_NUM_THREADS" "$OPENBLAS_NUM_THREADS" "$MKL_NUM_THREADS" "$NUMEXPR_NUM_THREADS" "$PYTHONDONTWRITEBYTECODE"
  /usr/bin/printf 'captured_argument=%s\\n' "$@"
  return 0
}
'''
    env = dict(os.environ, **{key: '9' for key in variables}, PYTHONDONTWRITEBYTECODE='0')
    result = subprocess.run(['/bin/bash'], input=stub + adapted, text=True, capture_output=True,
                            check=True, env=env, cwd=tmp_path)
    assert 'captured_threads=1,1,1,1,1' in result.stdout
    assert 'captured_argument=-m\ncaptured_argument=pytest\n' in result.stdout
    assert result.stderr == '' and (logs / 'reward.txt').read_text() == '1\n'
    assert {p.name for p in logs.iterdir()} == {'reward.txt'}
