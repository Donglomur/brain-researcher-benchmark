"""Versioned exact-ID and component-specific robustness evidence.
The retained v1 subspace alone cannot authenticate a claimed first-component identity.
"""
import hashlib
import json
from pathlib import Path
import numpy as np

VERSION = "gradient-config-v2"

def validate_evidence(out, reference):
    assert str(reference["schema_version"]) == VERSION, "regenerate a v2 reference from genuine oracle outputs"
    ids = json.loads((out / "subject_ids.json").read_text())
    expected = [str(x) for x in reference["ref_ids"]]
    assert len(ids) == len(set(ids)) == 20 and set(ids) == set(expected), "exact20 unique participant IDs required"
    aligned = np.load(out / "gradients_aligned.npy", allow_pickle=False)
    assert aligned.shape[0] == 20 and np.isfinite(aligned).all()
    ref_aligned = reference["ref_aligned"]
    for sid, row in zip(ids, aligned):
        target = ref_aligned[expected.index(sid)]
        for component in range(3):
            # Component correspondence matters for identity: no arbitrary subspace rotations.
            corr = np.corrcoef(row[:, component], target[:, component])[0, 1]
            assert np.isfinite(corr) and abs(corr) >= 0.85, f"wrong subject/component: {sid}"
    report = json.loads((out / "robustness.json").read_text())
    configs = report["configs"]
    canonical = json.loads(str(reference["ref_config_metadata"]))
    assert len(configs) == len(canonical) and len({x["config"] for x in configs}) == len(configs)
    expected_configs = {x["config"]: x for x in canonical}
    networks = np.asarray(reference["ref_networks"]).astype(str)
    apexes = []
    parameter_sets = []
    for conf in configs:
        expected_conf = expected_configs[conf["config"]]
        for key in ("subject_ids", "bandpass", "method", "sign_convention"):
            assert conf[key] == expected_conf[key], f"configuration metadata mismatch: {key}"
        assert len(conf["subject_ids"]) == len(set(conf["subject_ids"])) and set(conf["subject_ids"]) <= set(ids)
        artifact = out / conf["gradient_path"]
        assert artifact.resolve().parent == out.resolve(), "configuration artifacts must be local output files"
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == conf["gradient_sha256"]
        gradient = np.load(artifact, allow_pickle=False)
        target = reference["config_" + conf["config"]]
        assert gradient.shape == target.shape and np.isfinite(gradient).all()
        corr = np.corrcoef(gradient[:, 0], target[:, 0])[0, 1]
        assert corr >= 0.85, "first component does not match declared computed configuration"
        means = {network: float(gradient[networks == network, 0].mean()) for network in set(networks)}
        # Public Default >= Vis orientation anchors sign; no rotation of the leading component.
        assert means["Default"] >= means["Vis"]
        apex = max(means, key=means.get)
        assert conf["apex_network"] == apex
        apexes.append(apex)
        parameter_sets.append((tuple(conf["subject_ids"]), bool(conf["bandpass"])))
    assert len(set(parameter_sets)) >= 2, "dummy/identical configurations"
    assert report["principal_gradient_identity_robust"] is (len(set(apexes)) == 1)
    return len(set(apexes)) == 1
