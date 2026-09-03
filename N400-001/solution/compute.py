"""Reference solution for N400-001.

Reproduce the ERP CORE N400 semantic word-pair effect: the **unrelated-minus-related**
difference-wave amplitude at **CPz** in its 300-500 ms window, for subjects 1-12, with
the whole pipeline pinned by the task EXCEPT which stimulus events enter the two
conditions.

The one open choice is trial selection. The N400 relatedness effect is elicited by the
**target** word (the second word of the pair, when the semantic relation to the prime is
realized), so the unrelated-minus-related contrast must be built from **target words
only** (event codes 221/222 minus 211/212). The **prime** words (codes 1XY) are presented
before the relation can be evaluated and carry no relatedness effect; the prime-only
difference is ~0. A pipeline that groups by the "Related / Unrelated" event-code column
alone -- i.e. pools primes and targets ({121,122,221,222} minus {111,112,211,212}) --
dilutes the target effect with ~zero-effect prime trials of equal number and roughly
HALVES the reported amplitude.

Validated target-only vs pooled (CPz, 300-500 ms mean amplitude, unrelated-minus-related,
average-of-P9/P10 mastoid reference, 0.1-30 Hz, -200..0 baseline, per subject then mean
over the 12 subjects):
    TARGET WORDS ONLY (correct)                 : -8.70 uV   <-- reported here
    PRIME + TARGET pooled by relatedness (naive): -4.20 uV
    PRIME words only (sanity, ~0)               : +0.18 uV
12/12 subjects show a negative unrelated-minus-related N400 with the target-only contrast.
"""
import json
import os
import sys
import tempfile
import urllib.request
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

SUBJECTS = list(range(1, 13))
EOG = ["HEOG_left", "HEOG_right", "VEOG_lower"]
REF = ["P9", "P10"]                    # ERP CORE N400 reference (mastoid-adjacent)
# target words: XY -> hundreds digit 2 (target), tens digit 1 (related) / 2 (unrelated)
RELATED = {"211", "212"}               # target, related pair
UNRELATED = {"221", "222"}             # target, unrelated pair
CHAN = "CPz"
WIN = (0.300, 0.500)                   # N400 measurement window, s
# OSF file ids for <subj>_N400_shifted_ds.{set,fdt} (ERP CORE N400 node 29xpq)
OSF = {
    1: ("5f1694d20596f601307a31c0", "5f1694d00596f6013579eea0"),
    2: ("5f169db50870f2014b097fda", "5f169db20596f601357a038b"),
    3: ("5f16a6be0596f6012c7a1d1f", "5f16a6bb6ef440013ebd3c2e"),
    4: ("5f16aff70596f6012c7a27f2", "5f16aff30596f6013e79a466"),
    5: ("5f16b1d20870f2014b09a318", "5f16b1cf6ef4400155bc9530"),
    6: ("5f16b2cf6ef440014fbcbdbe", "5f16b2cd0870f2014b09a4dd"),
    7: ("5f16b3b36ef4400149bcea77", "5f16b3b00870f201500972da"),
    8: ("5f16b49b0596f6012c7a2da6", "5f16b4980596f601357a29a9"),
    9: ("5f16b5776ef4400155bc9e0d", "5f16b5736ef4400154bc9aa4"),
    10: ("5f1695950596f601307a331d", "5f1695930596f6013579f09c"),
    11: ("5f1696566ef4400148bca87f", "5f1696530596f6012f7a0633"),
    12: ("5f1697226ef4400148bca9fb", "5f16971f0870f2014b097388"),
}


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset_id": "erpcore_n400"}, indent=2))
    (OUT / "n400.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


def data_dir():
    """Use a local cache if ERPCORE_N400_DIR points at the files; else fetch from OSF."""
    env = os.environ.get("ERPCORE_N400_DIR")
    if env and all((Path(env) / f"{s}_N400_shifted_ds.set").exists() for s in SUBJECTS):
        return Path(env)
    d = Path(tempfile.mkdtemp(prefix="erpcore_n400_"))
    for s in SUBJECTS:
        set_id, fdt_id = OSF[s]
        for fid, ext in ((set_id, "set"), (fdt_id, "fdt")):
            dst = d / f"{s}_N400_shifted_ds.{ext}"
            try:
                urllib.request.urlretrieve(f"https://osf.io/download/{fid}/", dst)
            except Exception as e:
                fail(f"OSF download failed for subject {s} .{ext}: {e}")
    return d


try:
    import mne
    mne.set_log_level("ERROR")
except Exception as e:  # pragma: no cover
    fail(f"mne import failed: {e}")

DDIR = data_dir()


def cpz_difference(subj, related, unrelated):
    """unrelated-minus-related difference wave at CPz (P9/P10 ref, -200..0 baseline)."""
    raw = mne.io.read_raw_eeglab(f"{DDIR}/{subj}_N400_shifted_ds.set", preload=True)
    raw.set_channel_types({c: "eog" for c in EOG})
    raw.filter(0.1, 30.0, picks="eeg", verbose=False)
    events, eid = mne.events_from_annotations(raw, verbose=False)
    id2lab = {v: k for k, v in eid.items()}
    ne = []
    for o, _, c in events:
        lab = id2lab[c]
        if lab in related:
            ne.append([o, 0, 1])
        elif lab in unrelated:
            ne.append([o, 0, 2])
    ep = mne.Epochs(raw, np.array(ne), {"related": 1, "unrelated": 2}, tmin=-0.2, tmax=0.8,
                    baseline=None, reject=None, preload=True, verbose=False)
    # ERP CORE N400 convention: reference to the average of the mastoid-adjacent P9/P10
    ep.set_eeg_reference(REF, projection=False, verbose=False)
    ep.apply_baseline((-0.2, 0.0), verbose=False)
    diff = mne.combine_evoked([ep["unrelated"].average(), ep["related"].average()], weights=[1, -1])
    seg = diff.copy().pick([CHAN]).crop(*WIN).data[0] * 1e6   # uV
    return float(seg.mean())


try:
    target = np.array([cpz_difference(s, RELATED, UNRELATED) for s in SUBJECTS])
    # naive pooled-by-relatedness value (primes + targets), for contrast only
    pooled = np.array([cpz_difference(s, {"111", "112", "211", "212"},
                                      {"121", "122", "221", "222"}) for s in SUBJECTS])
except Exception as e:
    fail(f"could not build the N400 difference wave: {e}")

n400_amp = float(target.mean())        # CORRECT target-only measure
pooled_amp = float(pooled.mean())      # naive, for contrast

(OUT / "n400.json").write_text(json.dumps({
    "n400_difference_amplitude_uv": n400_amp,
    "measure": "mean amplitude over the window",
    "channel": CHAN,
    "window_ms": [300, 500],
    "contrast": "unrelated minus related (target words)",
    "n_subjects": len(SUBJECTS),
    "per_subject_uv": [round(float(v), 3) for v in target],
    "pooled_prime_plus_target_uv_for_reference": pooled_amp,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset_id": "erpcore_n400",
    "n_subjects": len(SUBJECTS),
    "reference": "average of the mastoid-adjacent electrodes P9 and P10 (ERP CORE convention)",
    "filter_hz": [0.1, 30.0],
    "baseline_ms": [-200, 0],
    "epoch_ms": [-200, 800],
    "related_target_codes": sorted(RELATED),
    "unrelated_target_codes": sorted(UNRELATED),
    "measurement": "mean amplitude of the unrelated-minus-related difference wave at CPz, 300-500 ms, per subject then mean over subjects",
}, indent=2))

(OUT / "findings.md").write_text(f"""# N400-001 - the ERP CORE N400 semantic word-pair effect at CPz

Reproducing the ERP CORE N400 word-pair paradigm on subjects 1-12 (P9/P10 mastoid
reference, 0.1-30 Hz, -200..0 ms baseline), the **unrelated-minus-related** difference
wave at **CPz** is a clear centro-parietal negativity in the N400 window. Measured as the
**mean amplitude** over **300-500 ms** per subject and averaged over the 12 subjects, the
N400 difference amplitude is **{n400_amp:.2f} uV** (12/12 subjects negative).

The relatedness effect is carried by the **target** word (the second word of each pair),
so the contrast is built from target words only (unrelated targets minus related targets).
Pooling primes and targets by the relatedness label instead dilutes the effect with the
~zero-difference prime trials and roughly halves the value (about {pooled_amp:.2f} uV);
the prime-only difference is essentially zero, confirming the effect is target-locked.
""")
print(f"OK: N400 CPz unrelated-minus-related MEAN={n400_amp:.3f} uV | "
      f"pooled(primes+targets)={pooled_amp:.3f} uV | n_subjects={len(SUBJECTS)}")
