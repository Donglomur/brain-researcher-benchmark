## MEGAEF-001

**Proposal Title:** Auditory M100 latency in the Brainstorm bst_auditory MEG recording — an un-cued stimulus-timing trap (the digital trigger leads the acoustic onset by ~14 ms, inflating the apparent latency)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** auditory MEG / evoked fields

**Source finding / dataset:** The **auditory M100** (N100m, the magnetic counterpart of the EEG N100), quantified as the **latency of the peak magnetometer Global Field Power (GFP)** in the 60-160 ms window for the standard tones of the Brainstorm **bst_auditory** dataset (single-subject CTF-MEG auditory oddball; standard + deviant tones). **Dataset:** fetched at runtime with `mne.datasets.brainstorm.bst_auditory.data_path(accept=True)` (no credentials; `accept=True` agrees to the license). Genre: **reproduction**.

### The un-cued lever (PRIVATE — reviewers only)

The deliverable ("report the M100 peak latency relative to the onset of the auditory stimulus") never says **what marks the stimulus onset**. In this recording the digital stimulus trigger on `UPPT001` does **not** coincide with the acoustic delivery of the tone: the sound reaches the subject about **14 ms after** the trigger fires (a fixed presentation/soundcard delay). The recording captures the delivered sound itself on an analog audio channel (`UADC001`), so the true acoustic onset is recoverable and the M100 latency should be measured relative to it. Timing the epochs to the raw digital trigger (the naive choice) over-states the M100 latency by the fixed ~14 ms trigger delay. This trigger-delay correction is exactly what the official Brainstorm/MNE bst_auditory tutorial performs ("Trigger delay removed").

Everything else is pinned so only the stimulus-timing choice moves the number: **run 1** (`S01_AEF_20131218_01.ds`), the **standard-tone** trigger code 1, the **MEG magnetometers**, the **-0.1..0.4 s** epoch with a **pre-stimulus baseline**, a **40 Hz low-pass**, and the **GFP peak in the 60-160 ms window**. GFP-peak latency is chosen as the readout because it is reference-free and needs no channel hand-selection, so the correct value is a single well-defined number. The instruction gives the trigger code (needed to identify the standards) but never states that the trigger equals the acoustic onset, and never mentions timing, the trigger delay, the analog audio channel, or a "correction".

### Step-0 (validated, real data — MNE 1.12.1)

Pinned pipeline; peak magnetometer GFP latency in the 60-160 ms window, standard tones (run 1, 200 trials):

| stimulus timing | reported M100 latency |
|---|---|
| **aligned to the true acoustic onset (correct)** | **93.3 ms** |
| raw digital trigger `UPPT001` (naive) | **107.5 ms** (~+14 ms) |

Measured trigger→sound delay from the analog audio channel: **13.9 ± 0.3 ms** (matched all 240 stimulus events). The correct value is robust: **92.1–94.2 ms** across low-pass 30/40 Hz and no low-pass, across measurement windows (50-180 / 60-160 / 70-150 ms), and across audio-detection thresholds 1.5–3.0 × σ (93.3, 93.3, 93.3, 92.9 ms). The naive raw-trigger value is **107.1–108.8 ms** across the same variations. The correct GFP-peak amplitude is ~57 fT.

### Why latency (reviewers): the amplitude has no fair sensor-space lever here

The M100 **amplitude** (peak GFP) on this dataset is ~58 fT and is remarkably robust — it barely moves under 60 Hz notch (±0.02 fT), low-pass choice, or peak-to-peak epoch rejection (58–61 fT). The only large amplitude mover is baseline correction, but that is **degenerate** on CTF axial gradiometers: MNE's `Epochs` applies a pre-stimulus baseline by default (so the naive path is already correct), and disabling it gives an absurd ~148 000 fT (the large per-channel DC offset), which no competent agent would report — not a subtle trap. So amplitude offers no fair, well-posed, non-degenerate lever on this recording. The **timing** correction, by contrast, moves the latency by a clean, robust, documented ~14 ms and is a real, dataset-specific analytic pitfall. (This is a different lever from AUDN1-001, where baseline-on-amplitude was the lever and latency was stable; here the lever is the stimulus-timing correction and it moves latency specifically.) The graded latency is well-posed: the auditory M100 is a physiological response to the **sound**, so its latency is defined relative to the true acoustic onset, and the digital trigger in this dataset is a known-mistimed proxy.

### Verifier (3 plain checks)

`tests/test_outputs.py`: (1) an M100 latency averaged over the standard-tone trials is reported; (2) the reported latency is the **acoustic-onset-aligned** value (`|reported − 93.3| < 8.0 ms`) — the raw-trigger value (~107.5 ms) is well outside and fails; (3) `findings.md` reports a latency consistent with `m100.json`. The grader searches the output at any depth, requires a latency-ish key with a plausible-millisecond magnitude, and **excludes** explicitly-labelled trigger/reference/delay/amplitude/metadata fields (so the reference `latency_from_raw_trigger_ms_for_reference` field is never mistaken for the answer). No weighted rubric / score.json.

### Validation (MEASURED locally)

- **Oracle** (`solution/compute.py`, bst_auditory run 1, 200 standard tones): M100 latency = **93.3 ms** (raw-trigger 107.5 ms for contrast); verifier **PASS (3/3)**. End-to-end through the real `mne.datasets.brainstorm.bst_auditory.data_path(accept=True)` fetcher.
- **Naive** raw-trigger fixture (107.5 ms): verifier **FAIL** (`test_m100_latency_is_acoustic_onset_aligned`). Task has teeth.
- Data fetches at runtime via the MNE brainstorm fetcher (no credentials; `accept=True`); `allow_internet=true`.
- **Step-5 frontier calibration PENDING** (maintainer step).

### Cost

`hard`. cpus 2, mem 16 GB, storage 40 GB, internet on (downloads the ~1.6 GB bst_auditory dataset once). Deps: mne 1.12.1 + numpy/scipy/pooch. No source localization (sensor-space only).
