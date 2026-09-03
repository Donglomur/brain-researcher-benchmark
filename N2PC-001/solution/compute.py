"""Reference solution for N2PC-001.

Reproduce the ERP CORE N2pc visual-search effect: the **N2pc component amplitude** at the
**PO7/PO8** electrode pair in its 200-300 ms window, quantified as the
**contralateral-minus-ipsilateral** difference and grand-averaged over subjects
1, 3-13, with the whole pipeline pinned by the task.

The one choice the brief leaves un-cued is **how the contralateral / ipsilateral waveforms
are formed from the two electrodes given the target's visual field**. The N2pc is a
*lateralized* component: for a target in the **left** visual field it appears over the
**right** posterior scalp (PO8), and for a **right**-field target over the **left**
posterior scalp (PO7). The target side is carried by the *tens* digit of the 3-digit
stimulus code (1 = target left, 2 = target right; the hundreds digit is the target colour
and the units digit the gap position, both irrelevant to laterality). The component must
therefore be built by *re-mapping the electrodes per trial*: contralateral =
(PO8 on left-target trials, PO7 on right-target trials), ipsilateral = the mirror. Averaged
this way the contralateral-minus-ipsilateral difference is a robust negativity (~-1.4 uV).

A pipeline that instead takes a **fixed** electrode difference across all trials (e.g.
PO8-PO7, or PO7-PO8, without splitting by target side) *pools the two visual fields*: the
lateralized negativity sits on opposite electrodes for the two fields and, because the
field is balanced, cancels almost completely (grand-average |difference| ~ 0.3 uV). Only the
per-side contralateral/ipsilateral assignment recovers the component; everything else
(subjects, 0.1-30 Hz band-pass, average reference over the 30 scalp electrodes, -200..0
baseline, epochs, the PO7/PO8 pair and the 200-300 ms window, mean amplitude) is pinned.

The contralateral-minus-ipsilateral difference is a difference between two scalp electrodes,
so it is independent of the EEG reference.

Validated (MNE 1.12.1, ERP CORE N2pc, subjects 1/3/4/5/6/7/8/9/10/11/12/13; PO7/PO8;
0.1-30 Hz; -200..0 baseline; 200-300 ms mean amplitude; per subject then mean over the 12):
    contralateral-minus-ipsilateral (correct N2pc)      : -1.38 uV   <-- reported here
    fixed PO8-PO7 across all trials (pooled, naive)      : +0.34 uV
    fixed PO7-PO8 across all trials (pooled, naive)      : -0.34 uV
12/12 subjects show a negative contralateral-minus-ipsilateral N2pc. The correct value is
robust (-1.374 to -1.378 uV across 0.1-20/30/40 Hz low-pass, average vs no re-reference, and
-150/-200 ms baselines); the pooled fixed-electrode difference stays near 0 (|.| ~ 0.3 uV).
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

SUBJECTS = [1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
EOG = ["HEOG_left", "HEOG_right", "VEOG_lower"]
# target side = tens digit of the 3-digit stimulus code
LEFT = {"111", "112", "211", "212"}    # target in LEFT visual field  -> contralateral = PO8
RIGHT = {"121", "122", "221", "222"}   # target in RIGHT visual field -> contralateral = PO7
L_FREQ, H_FREQ = 0.1, 30.0
BASELINE = (-0.2, 0.0)
WIN = (0.200, 0.300)                   # N2pc measurement window, s
# OSF file ids for sub-XXX_task-N2pc_eeg.{set,fdt} (ERP CORE N2pc node yefrq, BIDS-compatible)
OSF = {
    1: ("60078009e80d3708eca59ed0", "60077ffeba010908978910b5"),
    3: ("6007806d86541a092614bc4e", "60078065e80d3708eca5a074"),
    4: ("60078089e80d3708eca5a0f6", "60078084e80d3708eaa592c8"),
    5: ("600780ace80d3708eaa59320", "60078098e80d3708eaa59300"),
    6: ("600780c5ba010908a7893ce5", "600780bfba010908978910d5"),
    7: ("600780e686541a092614bd07", "600780dbe80d3708e7a586fc"),
    8: ("6007810be80d3708e2a57755", "600780ff86541a092c1534dc"),
    9: ("6007812eba010908a7893eae", "60078127ba010908a7893e7e"),
    10: ("6007816b86541a092614be07", "6007815d86541a092c153ba7"),
    11: ("600781a0ba010908a7894081", "6007818eba01090892890b1e"),
    12: ("600781ca86541a092c15443a", "600781c5e80d3708eca5a5e9"),
    13: ("600781f186541a092614bf0b", "600781e4ba0109089e8922f0"),
}


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset_id": "erpcore_n2pc"}, indent=2))
    (OUT / "n2pc.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


def data_dir():
    """Use a local cache if N2PC_DIR holds the files; else fetch the BIDS files from OSF."""
    env = os.environ.get("N2PC_DIR")
    if env and all((Path(env) / f"sub-{s:03d}_task-N2pc_eeg.set").exists() for s in SUBJECTS):
        return Path(env)
    d = Path(tempfile.mkdtemp(prefix="erpcore_n2pc_"))
    for s in SUBJECTS:
        set_id, fdt_id = OSF[s]
        for fid, ext in ((set_id, "set"), (fdt_id, "fdt")):
            dst = d / f"sub-{s:03d}_task-N2pc_eeg.{ext}"
            for attempt in range(4):
                try:
                    urllib.request.urlretrieve(f"https://osf.io/download/{fid}/", dst)
                    break
                except Exception as e:  # pragma: no cover
                    if attempt == 3:
                        fail(f"OSF download failed for sub-{s:03d} .{ext}: {e}")
    return d


try:
    import mne
    mne.set_log_level("ERROR")
except Exception as e:  # pragma: no cover
    fail(f"mne import failed: {e}")

DDIR = data_dir()


def subject_evokeds(subj):
    """Target-left and target-right stimulus-locked averages at PO7/PO8 (average reference,
    0.1-30 Hz, -200..0 baseline)."""
    raw = mne.io.read_raw_eeglab(f"{DDIR}/sub-{subj:03d}_task-N2pc_eeg.set", preload=True)
    raw.set_channel_types({c: "eog" for c in EOG if c in raw.ch_names})
    raw.filter(L_FREQ, H_FREQ, picks="eeg", verbose=False)
    raw.set_eeg_reference("average", projection=False, verbose=False)
    events, eid = mne.events_from_annotations(raw, verbose=False)
    inv = {v: k for k, v in eid.items()}
    rows = [[o, 0, 1 if inv[c] in LEFT else 2]
            for o, _, c in events if inv[c] in LEFT or inv[c] in RIGHT]
    ep = mne.Epochs(raw, np.array(rows), {"left": 1, "right": 2}, tmin=-0.2, tmax=0.45,
                    baseline=BASELINE, reject=None, preload=True, picks=["PO7", "PO8"], verbose=False)
    return ep["left"].average(), ep["right"].average(), len(ep["left"]), len(ep["right"])


def win_mean(evk, ch):
    t = evk.times
    m = (t >= WIN[0]) & (t <= WIN[1])
    return 1e6 * float(evk.data[evk.ch_names.index(ch), m].mean())


try:
    n2pc_list, contra_list, ipsi_list, fixed_list = [], [], [], []
    n_left_tot = n_right_tot = 0
    for s in SUBJECTS:
        L, R, nl, nr = subject_evokeds(s)
        n_left_tot += nl
        n_right_tot += nr
        # contralateral: PO8 for left-field target, PO7 for right-field target
        contra = 0.5 * (win_mean(L, "PO8") + win_mean(R, "PO7"))
        ipsi = 0.5 * (win_mean(L, "PO7") + win_mean(R, "PO8"))
        n2pc_list.append(contra - ipsi)
        contra_list.append(contra)
        ipsi_list.append(ipsi)
        # naive fixed-electrode difference, pooled across visual fields (for reference)
        po8 = 0.5 * (win_mean(L, "PO8") + win_mean(R, "PO8"))
        po7 = 0.5 * (win_mean(L, "PO7") + win_mean(R, "PO7"))
        fixed_list.append(po8 - po7)
    n2pc = float(np.mean(n2pc_list))
    contra = float(np.mean(contra_list))
    ipsi = float(np.mean(ipsi_list))
    fixed = float(np.mean(fixed_list))
    n_neg = int(sum(x < 0 for x in n2pc_list))
except SystemExit:
    raise
except Exception as e:  # pragma: no cover
    fail(f"could not compute the N2pc amplitude: {e}")

(OUT / "n2pc.json").write_text(json.dumps({
    "n2pc_amplitude_uv": n2pc,
    "electrode_pair": "PO7/PO8",
    "measure": "mean contralateral-minus-ipsilateral amplitude, 200-300 ms",
    "window_ms": [200, 300],
    "bandpass_hz": [L_FREQ, H_FREQ],
    "n_subjects": len(SUBJECTS),
    "n_subjects_negative": n_neg,
    "contralateral_amplitude_uv": contra,
    "ipsilateral_amplitude_uv": ipsi,
    "fixed_po8_minus_po7_pooled_uv_for_reference": fixed,
    "n_left_target_trials_total": int(n_left_tot),
    "n_right_target_trials_total": int(n_right_tot),
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset_id": "erpcore_n2pc (ERP CORE, N2pc task, subjects 1/3-13)",
    "subjects": SUBJECTS,
    "electrode_pair": "PO7/PO8",
    "reference": "average (30 scalp electrodes; EOG excluded)",
    "bandpass_hz": [L_FREQ, H_FREQ],
    "baseline_ms": [int(BASELINE[0] * 1000), int(BASELINE[1] * 1000)],
    "measurement_window_ms": [200, 300],
    "measure": "mean contralateral-minus-ipsilateral amplitude at PO7/PO8, grand-averaged",
    "target_side_from": "tens digit of the 3-digit stimulus code (1=left, 2=right)",
}, indent=2))

(OUT / "findings.md").write_text(f"""# N2PC-001 - N2pc component amplitude (ERP CORE N2pc, subjects 1/3-13)

In the ERP CORE N2pc visual-search task, attending to a lateral target elicits a posterior
**N2pc**: a negativity over the hemisphere **contralateral** to the target's visual field,
at the **PO7/PO8** pair. Measured as the **mean contralateral-minus-ipsilateral amplitude in
the 200-300 ms window** (0.1-30 Hz band-pass, average reference, -200..0 baseline) and
grand-averaged over the {len(SUBJECTS)} subjects, the N2pc is **{n2pc:.2f} uV**
(contralateral {contra:.2f} uV, ipsilateral {ipsi:.2f} uV; {n_neg}/{len(SUBJECTS)} subjects
negative).

The component is lateralized relative to the target: for a left-field target it appears over
the right posterior scalp (PO8) and for a right-field target over the left (PO7), so the
contralateral and ipsilateral waveforms are formed by re-mapping the two electrodes per
target side. The reported value ({n2pc:.2f} uV) is that contralateral-minus-ipsilateral
difference.
""")
print(f"OK: N2pc (contra-ipsi) = {n2pc:.3f} uV | fixed PO8-PO7 pooled = {fixed:.3f} uV | "
      f"neg {n_neg}/{len(SUBJECTS)} | trials L={n_left_tot} R={n_right_tot}")
