"""Numeric agreement checks for the public EEGMMIDB alpha-density recipe.

Check every participant's EC/EO densities and ratios, then recompute the group
summary. The reference is derived from the fixed original recordings, not the
historical Berger cohort. Numeric agreement is not proof of solver execution or
sound prose interpretation, and a public reference can be copied.
"""
import json
import os
from pathlib import Path

import numpy as np

import proof_of_work as pw

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF = np.load(Path(__file__).resolve().parent / "reference.npz", allow_pickle=False)

RATIO_VAL_TOL = 0.01
RATIO_REL_TOL = 0.01
GROUP_TOL = 0.2  # Reference tolerance; not table/headline identity tolerance.


def _load(name):
    p = OUT / name
    assert p.exists(), f"missing required output {p}"
    return json.loads(p.read_text(encoding="utf-8"))


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _headline(data):
    if isinstance(data, dict):
        v = data.get("occipital_alpha_ratio_ec_over_eo")
        if v is not None:
            return _num(v)
        for k, val in data.items():
            if isinstance(val, (int, float)) and "ratio" in k.lower() and "wholehead" not in k.lower():
                return float(val)
    return None


def _submitted():
    csvp = OUT / "per_subject.csv"
    assert csvp.exists(), (
        "missing per_subject.csv -- the task requires a per-subject table with each subject's "
        "eyes-closed and eyes-open occipital alpha power and their ratio")
    return pw.load_submitted(str(csvp), {
        "ratio": ["ratio"],
        "ec": ["ec_occipital", "ec_alpha", "ec"],
        "eo": ["eo_occipital", "eo_alpha", "eo"],
    })[0]


# ---- PILLAR 3: occipital-vs-whole-head -------------------------------------------------
def test_headline_is_occipital_ratio():
    data = _load("alpha_ratio.json")
    r = _headline(data)
    occ = float(REF["occ_mean"]); wh = float(REF["wholehead_mean"])
    assert r is not None, "alpha_ratio.json missing the occipital EC/EO ratio"
    assert abs(r - occ) <= GROUP_TOL, (
        f"reported occipital alpha ratio {r:.2f} is not the occipital Berger ratio "
        f"({occ:.2f} +/- {GROUP_TOL}). A whole-head average (~{wh:.1f}) dilutes the effect.")


# ---- PILLAR 1: per-subject occipital ratio proof of work -------------------------------
def test_per_subject_ratio_proof_of_work():
    sub = _submitted()
    expected = [pw.canon_id(x) for x in REF["ref_ids"]]
    assert set(sub) == set(expected), "report exactly the five source subjects"
    for j, sid in enumerate(expected):
        row = sub[sid]
        assert all(row[k] is not None and np.isfinite(row[k]) for k in ("ec", "eo", "ratio"))
        assert row["ec"] > 0 and row["eo"] > 0, "powers must be positive"
        assert np.isclose(row["ratio"], row["ec"] / row["eo"], rtol=1e-3, atol=1e-3), "ratio is not EC/EO"
        for key in ("ec", "eo"):
            assert np.isclose(row[key], REF["ref_" + key][j], rtol=0.01, atol=1e-16), "powers do not match the declared PSD units and recipe"
    present = pw.check_subjects_and_values(
        sub, REF["ref_ids"], REF["ref_ratio"], "ratio", RATIO_VAL_TOL,
        cover=1.0, match=1.0, eps=1e-2, signed=True, rel_tol=RATIO_REL_TOL)
    # Berger direction: eyes-closed occipital alpha exceeds eyes-open for most subjects
    ratios = [sub[i]["ratio"] for i in present]
    assert sum(r > 1.0 for r in ratios) >= 0.8 * len(ratios), \
        f"eyes-closed should exceed eyes-open occipitally for most subjects, got {ratios}"


# ---- PILLAR 2: recompute the group ratio from the rows ---------------------------------
def test_recompute_ratio_from_rows():
    sub = _submitted()
    present = [i for i in (pw.canon_id(x) for x in REF["ref_ids"])
               if i in sub and sub[i].get("ratio") is not None]
    reported = _headline(_load("alpha_ratio.json"))
    recomputed = pw.recompute_mean(sub, present, "ratio")
    assert abs(recomputed - float(REF["occ_mean"])) <= GROUP_TOL
    assert reported is not None and np.isclose(recomputed, reported, rtol=1e-3, atol=1e-3), \
        "headline is not the arithmetic mean of the submitted ratios"


# ---- SECONDARY: the write-up reports the occipital effect ------------------------------
def test_findings_present():
    # Numbers carry the automated gate. Keyword presence does not establish sound
    # scientific interpretation; prose must be reviewed separately.
    text = (OUT / "findings.md").read_text(encoding="utf-8")
    assert text.strip(), "findings.md must contain a written summary"


def test_public_analysis_metadata():
    result = _load("alpha_ratio.json")
    metadata = _load("run_metadata.json")
    for document in (result, metadata):
        assert document["band_hz"] == [8, 13]
        assert {str(channel).lower() for channel in document["channels"]} == {"o1", "oz", "o2"}
        assert len(document["channels"]) == 3
    assert result["n_subjects"] == 5
    subjects = [pw.canon_id(subject) for subject in metadata["subjects"]]
    assert len(subjects) == 5 and set(subjects) == {"1", "2", "3", "4", "5"}
    assert metadata["runs"] == {"eyes_open": 1, "eyes_closed": 2}
    assert any(name in metadata["dataset_id"].lower() for name in ("eegbci", "eegmmidb", "eeg motor movement/imagery"))
    # The public contract requires the Welch settings below, not an additional
    # psd_method key or a particular spelling of optional implementation details.
    assert "average" in metadata["reference"].lower() or metadata["reference"].lower() == "car"
    assert metadata["dataset_version"] == "1.0.0"
    units = metadata["power_units"].replace("²", "2").replace("^", "").replace(" ", "").lower()
    assert units == "v2/hz"
    assert metadata["aggregation"] == "mean_of_subject_ratios"
    settings = metadata["welch"]
    for key, value in {"segment_sec": 2, "n_fft": 320, "n_overlap": 0,
                       "remove_dc": True}.items():
        assert settings[key] == value
    assert settings["window"].lower() in {"hamming", "periodic_hamming", "periodic hamming"}
    assert settings["average"].lower() == "mean"
    assert np.isfinite(result["wholehead_alpha_ratio_for_reference"])
    assert np.isclose(result["wholehead_alpha_ratio_for_reference"], REF["wholehead_mean"], rtol=0.01)
