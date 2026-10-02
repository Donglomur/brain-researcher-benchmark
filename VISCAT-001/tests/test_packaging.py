"""Source-free portable layout checks; no Docker build or original data reads."""
import ast
import hashlib
import json
from pathlib import Path

import pytest

TASK = Path(__file__).parents[1]
ENV = TASK / "environment"
SOURCE_MANIFEST_SHA256 = "3819f2b5e9403f184b94be7d1374476c964c08c054763ec7b8d40cf6bbf7e7b9"
STAGER_SHA256 = "f844ab4e4bc6d3efccca3c4b19277b2fec5484685b93a2481ca9d882cc99bcf2"
REUSED_PREFIX = """FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3 AS dependencies
RUN apt-get update && \\
    apt-get install -y --no-install-recommends ca-certificates curl git python3 python3-venv python3-pip && \\
    python3 -m pip install --break-system-packages --no-cache-dir \\
      numpy==2.2.6 scipy==1.14.1 scikit-learn==1.8.0 h5py==3.15.1 \\
      pytest==8.4.1 pytest-json-ctrf==0.3.5 && \\
    rm -rf /var/lib/apt/lists/*
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
WORKDIR /app

FROM dependencies AS source
COPY stage_data.py source_manifest.json /opt/source/
RUN python3 /opt/source/stage_data.py --destination /app/data/mtlmemory

"""


def test_reused_source_and_dependency_layer_commands_exact():
    text = (ENV / "Dockerfile").read_text()
    assert text.partition("FROM dependencies AS runtime\n")[0] == REUSED_PREFIX


@pytest.mark.parametrize("name,pin", [("stage_data.py", STAGER_SHA256), ("source_manifest.json", SOURCE_MANIFEST_SHA256)])
def test_source_stage_build_inputs_byte_identical_to_authenticated_predecessor(name, pin):
    assert hashlib.sha256((ENV / name).read_bytes()).hexdigest() == pin


def test_runtime_has_only_public_inputs_no_download_or_authoring_copy():
    text = (ENV / "Dockerfile").read_text()
    assert text.partition("FROM dependencies AS runtime\n")[2].splitlines() == [
        "COPY --from=source /app/data/mtlmemory /app/data/viscat",
        "COPY stage_data.py source_manifest.json /opt/source/",
        "COPY method_contract.json /app/method_contract.json",
    ]


def test_portable_build_has_no_local_image_or_host_cache_dependency():
    text = (ENV / "Dockerfile").read_text()
    for forbidden in ("/home/", "brbench-", "__env-main", "--mount", "COPY . ", "ADD "):
        assert forbidden not in text


def test_obsolete_manifest_and_derived_reference_retired():
    assert not (ENV / "data_manifest.json").exists()
    assert not (TASK / "tests/reference.npz").exists()


def test_public_source_manifest_is_source_only_with_license():
    manifest = json.loads((ENV / "source_manifest.json").read_text())
    assert manifest["license"] == "CC-BY-4.0" and manifest["access"] == "OpenAccess"
    assert manifest["attribution"] and manifest["license_authority"]
    assert len(manifest["files"]) == 87
    assert all(r["role"] == "session_nwb" and r["path"].endswith(".nwb") for r in manifest["files"])
    assert all(r["version_id"] and r["transport_url"].startswith(r["blob_url"] + "?versionId=") for r in manifest["files"])
    assert sum(r["size_bytes"] for r in manifest["files"]) == 6_197_474_020


def test_stager_has_main_guard_and_no_scientific_reader_import():
    tree = ast.parse((ENV / "stage_data.py").read_text())
    imports = {node.names[0].name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)}
    assert not imports.intersection({"h5py", "pynwb", "numpy", "scipy", "sklearn"})
    assert isinstance(tree.body[-1], ast.If)
    assert ast.unparse(tree.body[-1].test) == "__name__ == '__main__'"


def test_source_api_uses_explicit_destination_for_runtime_alias():
    text = (ENV / "stage_data.py").read_text()
    assert "def verify_staged(data_dir):" in text
    assert "--destination" in text and "--verify-existing" in text
    # Historical default is deliberately unchanged to reuse the portable source layer.
    assert "default=Path('/app/data/mtlmemory')" in text
