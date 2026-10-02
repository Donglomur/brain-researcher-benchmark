"""Gated actual-output authoring QA, deliberately excluded from test.sh.

One full original_reference and one validated baseline snapshot per session.
No memoization or replacement of production validation or its numerical kernel.
No new source decoding beyond the explicitly supplied session fixture.
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

import numpy as np
import pytest

import actual_control_helpers as h
import output_contract as c


def encode(value):
    if isinstance(value,Decimal): return float(value)
    if isinstance(value,np.generic): return value.item()
    raise TypeError("not a serialized receipt type")


def raw_snapshot(root):
    caps = c.io.CAPS
    def cap(name):
        if name.endswith(".npz"): return caps["npz"]
        if name.endswith(".csv"): return caps["csv"]
        if name=="summary.json": return caps["summary"]
        if name.endswith(".json"): return caps["evidence"]
        return caps["text"]
    return {name:c.io.read_bytes(root/name,cap(name)) for name in c.io.REQUIRED}


def fingerprint(snapshot):
    return {name:hashlib.sha256(raw).hexdigest() for name,raw in snapshot.items()}


@pytest.fixture(scope="session")
def genuine(original_reference):
    configured = os.environ.get("REPAIR_ORACLE_OUTPUT")
    assert configured,"Actual authoring QA requires explicit REPAIR_ORACLE_OUTPUT; no default/skip."
    root = c.io.guarded_path(configured,directory=True)
    original = raw_snapshot(root)
    baseline = c.validate(root,original_reference)
    documents = c.io.read_artifacts(root)
    context = h.prepare(documents,original_reference)
    yield dict(root=root,reference=original_reference,raw=original,documents=documents,context=context,baseline=baseline)
    assert fingerprint(raw_snapshot(root)) == fingerprint(original),"Original output bytes changed during QA"


def same_document(a,b):
    if isinstance(a,np.ndarray) or isinstance(b,np.ndarray):
        return isinstance(a,np.ndarray) and isinstance(b,np.ndarray) and a.dtype==b.dtype and np.array_equal(a,b)
    if isinstance(a,dict) and isinstance(b,dict):
        return set(a)==set(b) and all(same_document(a[k],b[k]) for k in a)
    if isinstance(a,list) and isinstance(b,list):
        return len(a)==len(b) and all(same_document(x,y) for x,y in zip(a,b))
    return type(a)==type(b) and a==b


@contextmanager
def detached(genuine,candidate,tmp_path):
    root = Path(tempfile.mkdtemp(prefix="fcstab-authoring-",dir=tmp_path))
    try:
        for name in c.io.REQUIRED:
            target = root/name
            value = candidate[name]
            if same_document(value,genuine["documents"][name]):
                with target.open("xb") as handle: handle.write(genuine["raw"][name])
            elif name.endswith(".npz"):
                with target.open("xb") as handle: np.savez_compressed(handle,**value)
            elif name.endswith(".csv"):
                fields = list(value[0]) if value else list(c.CSV_COLUMNS)
                with target.open("x",newline="",encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle,fieldnames=fields)
                    writer.writeheader(); writer.writerows(value)
            elif name.endswith(".json"):
                with target.open("x",encoding="utf-8") as handle: json.dump(value,handle,allow_nan=False,default=encode)
            else:
                with target.open("x",encoding="utf-8") as handle: handle.write(value)
        yield root
    except BaseException:
        # Keep the first unexpected failure's exact candidate for diagnosis.
        # Authoring invocations put pytest basetemp in the retained evidence bind.
        raise
    else:
        # Exact mkdtemp-owned output-only directory after a completed check.
        shutil.rmtree(root)


def recorded(record_property,details):
    record_property("control_mode",details["mode"])
    record_property("control_category",details["category"])
    record_property("prevalidation_classification",details["status"])
    record_property("effect_count",details["effect"]["n_changed"])
    record_property("numeric_effect_count",details["effect"]["n_numeric_changes"])
    record_property("status_effect_count",details["effect"]["n_status_changes"])
    record_property("effect_max_absolute_gap",str(details["effect"]["max_absolute_gap"]))
    record_property("control_details",json.dumps(details,default=encode,sort_keys=True))


def test_genuine_baseline(genuine,record_property):
    assert genuine["baseline"]["status"]=="accepted"
    recorded(record_property,h.report("baseline","positive","constructed"))
    record_property("control_outcome","accepted_genuine")


@pytest.mark.parametrize("mode",h.POSITIVES)
def test_equivalent_representation(genuine,tmp_path,record_property,mode):
    candidate,details = h.positive_candidate(mode,genuine["documents"],genuine["context"])
    recorded(record_property,details)
    if candidate is None:
        assert details["status"]=="not_constructed" and details["reason"]
        record_property("control_outcome","not_constructed"); return
    with detached(genuine,candidate,tmp_path) as root:
        assert c.validate(root,genuine["reference"])["status"]=="accepted"
    record_property("control_outcome","accepted_positive")


@pytest.mark.parametrize("mode",h.NUMERICAL)
def test_numerical_component(genuine,tmp_path,record_property,mode):
    candidate,details = h.numerical_candidate(mode,genuine["documents"],genuine["context"])
    recorded(record_property,details)
    if candidate is None:
        assert details["status"]=="unavailable" and details["reason"]
        record_property("control_outcome","unavailable"); return
    for name in ("connectivity.npz","stability.csv","selection_evidence.json"):
        assert same_document(candidate[name],genuine["documents"][name])
    assert candidate["summary.json"]["source_observed"]==genuine["documents"]["summary.json"]["source_observed"]
    with detached(genuine,candidate,tmp_path) as root:
        for name in ("connectivity.npz","stability.csv","selection_evidence.json"):
            assert (root/name).read_bytes()==genuine["raw"][name]
        if details["status"]=="effective":
            assert details["effect"]["n_numeric_changes"]+details["effect"]["n_status_changes"]>0
            with pytest.raises(ValueError) as error: c.validate(root,genuine["reference"])
            record_property("rejection_reason",str(error.value))
            record_property("control_outcome","effective_numerical_rejection")
        else:
            assert details["status"]=="nondiscriminating" and details["effect"]["n_changed"]==0
            assert c.validate(root,genuine["reference"])["status"]=="accepted"
            record_property("control_outcome","nondiscriminating")


@pytest.mark.parametrize("mode",h.BINDING)
def test_binding_component(genuine,tmp_path,record_property,mode):
    candidate,details = h.binding_candidate(mode,genuine["documents"],genuine["context"])
    recorded(record_property,details)
    if candidate is None:
        assert details["status"]=="not_constructed" and details["reason"]
        record_property("control_outcome","not_constructed"); return
    with detached(genuine,candidate,tmp_path) as root:
        if details["status"]=="effective":
            assert details["effect"]["n_changed"]>0 and details["reason"].startswith("direct required binding discrepancy:")
            with pytest.raises(ValueError) as error: c.validate(root,genuine["reference"])
            record_property("rejection_reason",str(error.value))
            record_property("control_outcome","effective_binding_rejection")
        else:
            assert details["status"]=="nondiscriminating"
            assert c.validate(root,genuine["reference"])["status"]=="accepted"
            record_property("control_outcome","nondiscriminating")
