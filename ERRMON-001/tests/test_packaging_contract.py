"""Authoring-only packaging checks: execution success must retain its evidence."""
from pathlib import Path
import tomllib


TASK = Path(__file__).parents[1]


def test_harbor_harvests_public_results_and_provenance():
    config = tomllib.loads((TASK / 'task.toml').read_text())
    assert config['artifacts'] == [
        '/app/output', '/app/data/errmon/source_manifest.json', '/app/method_contract.json']
    assert config['environment']['allow_internet'] is False
    assert config['environment']['gpus'] == 0


def test_runtime_does_not_bake_evaluator_or_reference():
    dockerfile = (TASK / 'environment' / 'Dockerfile').read_text()
    runtime = dockerfile.split('FROM dependencies AS runtime\n', 1)[1]
    assert 'COPY --from=source /app/data/errmon /app/data/errmon' in runtime
    assert 'COPY method_contract.json /app/method_contract.json' in runtime
    assert all(name not in runtime for name in ('solution', 'tests', 'reference.npz'))
