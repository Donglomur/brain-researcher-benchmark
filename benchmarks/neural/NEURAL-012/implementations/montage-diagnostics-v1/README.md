# Complete-panel montage diagnostics

This operator utility identifies every missing or ambiguous M1 edge in declared
header-label metadata for the complete NEURAL-012 panel. The preserved source
validator stops at the first invalid edge. This diagnostic retains all 727
recordings and all 18 edges per recording, including forward/reverse duplicate
candidates and original channel positions. It never chooses a duplicate,
constructs a missing channel, or removes an inconvenient recording.

The utility checks the frozen scientific-contract and header-selector hashes.
It uses the existing electrode aliases and cross-checks structural edge
acceptance against the preserved `edge_mapping` implementation. Siena's complete
release whitelist is checked separately, including electrodes outside the
18-edge montage. EDF label padding is stripped before eligibility, matching the
preserved parser; original submitted label text and source positions are retained.
ECG, dummy and other nonselected labels remain visible.

Input schema `neural012_declared_header_labels_v1` contains `task_id: NEURAL-012`
and exactly 727 `records`. Each record has `recording_id`, `patient_id`, `cohort`,
`channel_labels` in original EDF order, `release_eeg_labels` (empty for CHB),
`header_sha256`, and `original_source_sha256`. IDs are the existing opaque
24-character lowercase hexadecimal form. The full 686 CHB/41 Siena and 23/14
disjoint declared-person supports are mandatory. Input and output belong to the
operator; no participant receives the source-identifying metadata.

From the repository root after integration:

```sh
python3 -I -B benchmarks/neural/NEURAL-012/implementations/montage-diagnostics-v1/montage_diagnostics.py \
  --input /operator/private/header-labels.json --input-sha256 EXACT_SHA256 \
  --output /operator/private/montage-diagnostics.json
```

The CLI reads at most 2 MiB of input and writes at most 8 MiB to a fresh output.
These limits describe this metadata utility, not signal-processing resources.
It makes no network request and opens no EEG or target data. The generated tests
exercise the complete 727-record roster in memory and compare label selection
against the actual frozen header parser using invented EDF headers.

**A label-only report is not authentic source validation.** The hashes of original
sources and headers are declarations in this input; their bodies are not read.
Physical calibration, sample rates, reference physics, source origin, genuine
biological grouping, clock adjudication and full native execution remain
unqualified. Every report retains `runnable: false` and
`scientifically_qualified: false`, even when all structural edges are present.
No direct/viewer neural-understanding, detector-performance or improvement
result is established.

The original sources support keeping these distinctions: the
[Siena release](https://physionet.org/content/siena-scalp-eeg/1.0.0/)
instructs users to select EEG/EKG channels from each subject's seizure-list file;
10–20 placement and 512 Hz sampling alone do not identify a common reference.
The [CHB release](https://physionet.org/content/chbmit/1.0.0/)
documents dummy and auxiliary channels and the chb01/chb21 repeated person.
The release landing-page count must not replace the separately pinned 686-path
roster used by the existing task. These pages were observed through the web
tool; no new raw source capture or identity certificate is claimed.
