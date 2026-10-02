"""Source-free packaging/trust boundaries; no production source invocation."""
import ast
from pathlib import Path

import pytest

import artifact_reader as io
import proof_of_work as p

ROOT=Path(__file__).resolve().parents[1]


def test_public_contract_pins_and_complete_artifacts():
    method=p.authenticated_json(ROOT/"environment/method_contract.json",p.METHOD_SHA256)
    schema=p.authenticated_json(ROOT/"environment/output_schema.json",p.SCHEMA_SHA256)
    assert schema["serialization"]["required_files"]==list(io.REQUIRED)
    assert method["source_manifest_sha256"]==schema["source_manifest_sha256"]==p.SOURCE_SHA256
    assert method["status"]=="frozen_before_original_BOLD_signal_analysis"


@pytest.mark.parametrize("name",["proof_of_work.py","reference_composition.py","numerical_contract.py"])
def test_no_oracle_bank_or_stage_helper_dependency(name):
    text=(ROOT/"tests"/name).read_text()
    tree=ast.parse(text)
    imports=[node.module if isinstance(node,ast.ImportFrom) else alias.name
             for node in ast.walk(tree) if isinstance(node,(ast.Import,ast.ImportFrom))
             for alias in (node.names if isinstance(node,ast.Import) else [None])]
    assert not any(value and (value.startswith("solution") or value in {"stage_data","compute","sensitivity"}) for value in imports)
    assert '"reference.npz"' not in text and "'reference.npz'" not in text


def test_grade_entrypoint_reconstructs_no_fixture_emitter():
    text=(ROOT/"tests/test_outputs.py").read_text()
    assert "load_reference()" in text and "validate_output_directory" in text
    assert "fixture_support" not in text and "reference.npz" not in text


def test_bootstrap_is_offline_isolated_and_failure_first():
    path=ROOT/"tests/test.sh"
    text=path.read_text()
    assert path.stat().st_mode & 0o111
    assert "python3 -I -B" in text and 'sys.path.insert(0, "/tests")' in text
    assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1" in text and "sys.pycache_prefix" in text
    assert "--junitxml=/logs/verifier/junit.xml" in text and "--ctrf" in text
    assert text.index("printf '0")<text.index("if python3")
    assert not any(s in text for s in ("curl ","apt-get","uvx","$HOME","source "))


@pytest.mark.parametrize("payload",[b'{"status":"wrong"}',b'{"a":1,"a":2}',b'{"x":1e999}'])
def test_contract_authentication_fails_unpinned_bytes(tmp_path,payload):
    target=tmp_path/"method.json";target.write_bytes(payload)
    with pytest.raises(ValueError): p.authenticated_json(target,p.METHOD_SHA256)
