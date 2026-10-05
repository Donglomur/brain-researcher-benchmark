# ERRMON-001 — single-person response-locked methods control

The task computes a signed FCz error-minus-correct voltage contrast from the
public MNE-modified ERP CORE participant-001 Flankers release. It is an easy
computational adaptation, not a difficult-agent claim or the paper's group ERN
reproduction. The independent biological unit is one participant.

## Paper and dataset connection

Kappenman et al. (2021), NeuroImage, DOI
[10.1016/j.neuroimage.2020.117465](https://doi.org/10.1016/j.neuroimage.2020.117465),
provides the component rationale, FCz measurement site and 0–100 ms window
(Tables 1–2). Its ERN cohort and preprocessing differ: 36 retained participants,
P9/P10 reference, an earlier baseline and additional filtering/ICA/artifact/RT
handling. This task does not claim those group findings or paper amplitudes.

The substrate is a genuine released recording, not a synthetic cohort. The exact
92,046,226-byte OSF version-1 archive is authenticated by its published MD5 and
SHA256 before extraction. Its three unchanged members, including the FIF,
upstream license README and release date, have individually recorded byte counts
and SHA256 hashes. Member hashes are locally measured, not independently
published by the authors. Portable Docker build stages the source; agent and
verifier execution require no internet. No oracle, tests or reference bank is
baked into the runtime image.

MNE modified the original resource's representation/reference/montage. Exact
historical export and processing lineage are not established; source headers
remain unchanged. The archive's CC BY-SA 4.0 attribution/share-alike notice is
retained. MNE's software license is not the data license. Local validation does
not by itself authorize publishing data or images.

## Repair design

The public method contract fixes event pairing, calibration, all 30 EEG
channels, FIR kernel/padding, common epoch support, inclusive baseline/window
samples, empty-condition handling and numerical tolerances before original
EEG-value analysis. There is no hidden estimator, forced negativity or hidden
stimulus-versus-response effect gap. Unknown preprocessing history is disclosed.

Seven purposeful artifacts connect original annotations to stimulus/response
pairs, full retained prebaseline FCz epochs, per-trial measurements, condition
waveforms and the signed headline result. The verifier binds complete source
support and voltage primitives, then independently recomputes all downstream
quantities from accepted submitted epochs. It does not accept a plausible
scalar, magnitude-only answer, high correlation or polished prose as evidence.
Ordering and reasonable numerical serialization are flexible; scoring is binary
and described as such.

## Validation boundary

See `REPAIR_STATUS.md` for the validation state of this commit, and external
receipts for any subsequent clean-commit Harbor execution. Source-free tests,
original-source numerical agreement, native adversarial checks and an offline
oracle are distinct evidence levels. They do not establish population validity,
clinical usefulness, model difficulty or successful Sol calibration. No mandatory
effect direction, minimum amplitude or positive negative-control gap is used.
