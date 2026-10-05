"""Genuine-source positives and adversarial mutations; never invent a bank.

Each mutation owns one temporary six-file copy and removes it at teardown, so
the complete dense connectome is not retained once per parameterized case.
"""
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

import numpy as np
import pytest

import graph_contract as q
from proof_of_work import load_reference, METHOD_SHA256

FILES = ("connectomes.csv","graph_metrics.csv","efficiency.csv","ranking.json","run_metadata.json","findings.md")


@pytest.fixture(scope="module")
def reference():
    if not os.environ.get("REPAIR_ORACLE_OUTPUT"):
        pytest.skip("Original-source oracle output not provided")
    return load_reference(Path(os.environ.get("REPAIR_REFERENCE_PATH",Path(__file__).with_name("reference.npz"))))


@pytest.fixture(scope="module")
def original(reference):
    path = Path(os.environ["REPAIR_ORACLE_OUTPUT"])
    assert all((path/name).is_file() for name in FILES)
    return path


@pytest.fixture
def output(original,tmp_path):
    with tempfile.TemporaryDirectory(prefix="actual-source-mutation-",dir=tmp_path) as directory:
        path = Path(directory)
        for name in FILES:
            shutil.copyfile(original/name,path/name)
        yield path


def table(path):
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames,list(reader)


def write_table(path,fields,rows):
    with path.open("w",newline="") as stream:
        writer = csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def change_json(path,operation):
    value = json.loads(path.read_text())
    operation(value)
    path.write_text(json.dumps(value,allow_nan=False))


def test_genuine_original_source_output(original,reference):
    q.validate_output_directory(original,reference)


def test_genuine_independent_source_implementation(reference):
    if not os.environ.get("REPAIR_INDEPENDENT_OUTPUT"):
        pytest.skip("Independent original-source output not provided")
    q.validate_output_directory(Path(os.environ["REPAIR_INDEPENDENT_OUTPUT"]),reference)


def test_public_contract_matches_bank_identity(reference):
    path = Path(__file__).parents[1]/"environment/method_contract.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == METHOD_SHA256
    assert json.loads(path.read_text()) == reference["metadata"]["method_contract"]


def test_reordered_rows_columns_and_extra_information(output,reference):
    for name in FILES[:3]:
        fields,rows = table(output/name)
        for row in rows:
            row["ungraded_note"] = "extra information"
        write_table(output/name,["ungraded_note",*reversed(fields)],list(reversed(rows)))
    def edit(meta):
        meta["source_observed"]["participants"].reverse()
        meta["source_observed"]["atlas"]["parcels"].reverse()
        meta["source_observed"]["atlas"]["source_label_ids"].reverse()
        meta["additional_information"] = {"not_a_required_claim":"Any scientifically honest discussion"}
    change_json(output/"run_metadata.json",edit)
    def reorder(value):
        value["configuration_rankings"].reverse()
        value["density_pairwise_spearman"].reverse()
        value["top_by_efficiency"].reverse()
        for row in value["configuration_rankings"]:
            row["top_by_efficiency"].reverse()
    change_json(output/"ranking.json",reorder)
    q.validate_output_directory(output,reference)


def test_numeric_formatting_and_rounded_measurements(output,reference):
    for name,identities in (("connectomes.csv",q.FC_FIELDS[:3]),("graph_metrics.csv",q.GRAPH_INTS),
            ("efficiency.csv",("participant","n_densities"))):
        fields,rows = table(output/name)
        for row in rows:
            for field in fields:
                if not row[field] or field == "scheme":
                    continue
                value = float(row[field])
                if field in identities:
                    rewritten = format(value,".17e")
                    assert q.integer(rewritten) == q.integer(row[field])
                else:
                    rewritten = format(value,".9e")
                row[field] = rewritten
        write_table(output/name,fields,rows)
    q.validate_output_directory(output,reference)


def test_honest_alternate_versions_free_prose_and_metadata_extras(output,reference):
    def edit(value):
        value["software_versions"] = {"independent_implementation":"documented-local-version"}
        value["source_observed"]["extra_note"] = "Original source remains fixed."
        value["source_observed"]["participants"][0]["extra_note"] = "Harmless observation"
        value["source_observed"]["atlas"]["extra_note"] = "Harmless atlas observation"
    change_json(output/"run_metadata.json",edit)
    (output/"findings.md").write_text("These measurements describe the specified computational exercise.\n")
    q.validate_output_directory(output,reference)


@pytest.mark.parametrize("name",FILES)
def test_missing_required_file(output,reference,name):
    (output/name).unlink()
    with pytest.raises((AssertionError,OSError)):
        q.validate_output_directory(output,reference)


@pytest.mark.parametrize("name",FILES)
def test_empty_required_file(output,reference,name):
    (output/name).write_text("")
    with pytest.raises((AssertionError,OSError)):
        q.validate_output_directory(output,reference)


@pytest.mark.parametrize("name",FILES[:3])
@pytest.mark.parametrize("mutation",("drop","duplicate","unknown_person","malformed_row"))
def test_complete_source_membership(output,reference,name,mutation):
    fields,rows = table(output/name)
    if mutation == "drop":
        rows.pop()
    elif mutation == "duplicate":
        rows[-1] = rows[0].copy()
    elif mutation == "unknown_person":
        rows[0]["participant"] = "99999999"
    else:
        rows[0][fields[-1]] = None
    write_table(output/name,fields,rows)
    with pytest.raises(AssertionError):
        q.validate_output_directory(output,reference)


@pytest.mark.parametrize("mutation",("shift","scale","sign","zero","swap_person","lower_triangle","wrong_roi","boolean_id","nan","inf"))
def test_original_connectome_binding(output,reference,mutation):
    fields,rows = table(output/"connectomes.csv")
    if mutation in ("shift","scale","sign","zero"):
        for row in rows:
            x = float(row["correlation"])
            row["correlation"] = {"shift":.01+.98*x,"scale":.9*x,"sign":-x,"zero":0.}[mutation]
    elif mutation == "swap_person":
        for a,b in zip(rows[:4950],rows[4950:9900]):
            a["correlation"],b["correlation"] = b["correlation"],a["correlation"]
    elif mutation == "lower_triangle":
        rows[0]["roi_i"],rows[0]["roi_j"] = rows[0]["roi_j"],rows[0]["roi_i"]
    elif mutation == "wrong_roi":
        rows[0]["roi_i"] = "0"
    elif mutation == "boolean_id":
        rows[0]["participant"] = "true"
    else:
        rows[0]["correlation"] = mutation
    write_table(output/"connectomes.csv",fields,rows)
    with pytest.raises(AssertionError):
        q.validate_output_directory(output,reference)


@pytest.mark.parametrize("field",("n_nodes","n_possible_edges","k_requested","n_at_cutoff","n_edges",
    "n_negative_edges","n_zero_edges","n_components","n_connected_pairs","n_disconnected_pairs"))
def test_graph_source_counts(output,reference,field):
    fields,rows = table(output/"graph_metrics.csv")
    row = next(row for row in rows if row[field])
    row[field] = q.integer(row[field])+1
    write_table(output/"graph_metrics.csv",fields,rows)
    with pytest.raises(AssertionError):
        q.validate_output_directory(output,reference)


@pytest.mark.parametrize("field",("correlation_cutoff","realized_density","minimum_selected_correlation","global_efficiency"))
def test_graph_numeric_receipts(output,reference,field):
    fields,rows = table(output/"graph_metrics.csv")
    row = next(row for row in rows if row[field])
    row[field] = float(row[field])+.02
    write_table(output/"graph_metrics.csv",fields,rows)
    with pytest.raises(AssertionError):
        q.validate_output_directory(output,reference)


def test_omit_required_absolute_sensitivity(output,reference):
    fields,rows = table(output/"graph_metrics.csv")
    write_table(output/"graph_metrics.csv",fields,[row for row in rows if row["scheme"]=="proportional"])
    with pytest.raises(AssertionError):
        q.validate_output_directory(output,reference)


@pytest.mark.parametrize("mutation",("old_uniform_shift","primary_wrong_density_count","strength_definition","all_constant"))
def test_primary_summary_source_binding(output,reference,mutation):
    fields,rows = table(output/"efficiency.csv")
    for row in rows:
        if mutation == "old_uniform_shift":
            row["global_efficiency"] = float(row["global_efficiency"])+.04
        elif mutation == "primary_wrong_density_count":
            row["n_densities"] = "8"
        elif mutation == "strength_definition":
            row["mean_positive_part_correlation"] = float(row["mean_positive_part_correlation"])+.01
        else:
            row["global_efficiency"] = ".5"
    write_table(output/"efficiency.csv",fields,rows)
    with pytest.raises(AssertionError):
        q.validate_output_directory(output,reference)


@pytest.mark.parametrize("mutation",("prefix","reverse","duplicate","wrong_top","missing_configs","duplicate_config","missing_pairs","fake_correlation","missing_null"))
def test_ranking_and_sensitivity_source_binding(output,reference,mutation):
    def edit(value):
        if mutation == "prefix":
            value["ranking_by_efficiency"] = value["ranking_by_efficiency"][:2]
        elif mutation == "reverse":
            order = value["ranking_by_efficiency"]
            assert reference["exact_primary"][0] != reference["exact_primary"][1] or len(set(reference["exact_primary"]))>1
            order.reverse()
        elif mutation == "duplicate":
            value["ranking_by_efficiency"][-1] = value["ranking_by_efficiency"][0]
        elif mutation == "wrong_top":
            value["top_by_efficiency"] = []
        elif mutation == "missing_configs":
            value["configuration_rankings"].pop()
        elif mutation == "duplicate_config":
            value["configuration_rankings"][-1] = value["configuration_rankings"][0]
        elif mutation == "missing_pairs":
            value["density_pairwise_spearman"].pop()
        elif mutation == "fake_correlation":
            value["primary_correlations"]["efficiency_vs_mean_signed_correlation"]["value"] = 9
        else:
            found = next(row["correlations"]["realized_density_vs_mean_signed_correlation"] for row in value["configuration_rankings"]
                if row["correlations"]["realized_density_vs_mean_signed_correlation"]["value"] is None)
            del found["value"]
    change_json(output/"ranking.json",edit)
    with pytest.raises(AssertionError):
        q.validate_output_directory(output,reference)


@pytest.mark.parametrize("mutation",("method_hash","source_hash","extra_source","changed_method","extra_method","empty_versions",
    "missing_observation","wrong_tr","wrong_scaling","wrong_rank","wrong_voxel_count","wrong_label","missing_confounds","wrong_units","boolean_count"))
def test_source_and_public_method_metadata(output,reference,mutation):
    def edit(value):
        observed = value["source_observed"]
        if mutation == "method_hash":
            value["method_contract_sha256"] = "0"*64
        elif mutation == "source_hash":
            value["source_sha256"][next(iter(value["source_sha256"]))] = "0"*64
        elif mutation == "extra_source":
            value["source_sha256"]["invented_source.nii"] = "0"*64
        elif mutation == "changed_method":
            value["method_contract"]["pipeline_id"] = "invented-method"
        elif mutation == "extra_method":
            value["method_contract"]["undeclared_smoothing"] = 10
        elif mutation == "empty_versions":
            value["software_versions"] = {}
        elif mutation == "missing_observation":
            observed["participants"].pop()
        elif mutation == "wrong_tr":
            observed["participants"][0]["tr_s"] += .1
        elif mutation == "wrong_scaling":
            observed["participants"][0]["intensity_slope"] *= 2
        elif mutation == "wrong_rank":
            observed["participants"][0]["confound_rank"] += 1
        elif mutation == "wrong_voxel_count":
            observed["atlas"]["parcels"][0]["n_voxels"] += 1
        elif mutation == "wrong_label":
            observed["atlas"]["parcels"][0]["label"] = "invented-label"
        elif mutation == "missing_confounds":
            observed["participants"][0]["confound_columns"].pop()
        elif mutation == "wrong_units":
            observed["participants"][0]["temporal_units"] = "msec"
        else:
            observed["participants"][0]["n_frames"] = True
    change_json(output/"run_metadata.json",edit)
    with pytest.raises(AssertionError):
        q.validate_output_directory(output,reference)


def test_coherent_rank_preserving_fabricated_source(output,reference):
    """Regenerate every graph/summary honestly from wrong FC, then reject source."""
    forged = q.derive(reference["participants"],.9*reference["weights"])
    fields,rows = table(output/"connectomes.csv")
    for row in rows:
        row["correlation"] = .9*float(row["correlation"])
    write_table(output/"connectomes.csv",fields,rows)
    write_table(output/"graph_metrics.csv",q.GRAPH_FIELDS,forged["graph_rows"])
    write_table(output/"efficiency.csv",q.EFFICIENCY_FIELDS,forged["efficiency_rows"])
    (output/"ranking.json").write_text(json.dumps(forged["ranking"],allow_nan=False))
    with pytest.raises(AssertionError,match="Connectome differs"):
        q.validate_output_directory(output,reference)
