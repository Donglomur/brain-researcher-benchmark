# N170PROFILE-001: source-bound ERP CORE processing adaptation

This task estimates signed participant-level PO8 face-minus-car mean voltage
and a sampled negative fractional-peak latency. It is motivated by the N170
characterization in Figure 2 and Tables 1–3 of Kappenman et al. (2021),
[ERP CORE](https://doi.org/10.1016/j.neuroimage.2020.117465).

It is **not** the complete paper pipeline or an exact historical ERPLAB port.
The released shifted/downsampled stage is followed by an explicit 30-channel
average reference, .1–30 Hz FIR, baseline correction and 150 µV rejection.
There is no ICA or extra onset low-pass. The public measurement contract
documents its negative-peak, tie and half-height-equality choices. The sampled
latency describes a waveform; it does not establish exact physiological onset.

## Source and scope

All 37 specified participants remain: IDs 1–40 excluding 1, 5 and 16. The image
fetches 74 original SET/FDT files from the public ERP CORE N170 OSF collection,
then runs offline. Exact source versions, sizes, SHA-256 and MD5 are pinned.
The dataset is 788,438,272 bytes. Source and project license notices are both
retained; local validation does not authorize redistribution of data or images.

The historical waveform bake and numerical answer bank are removed from the
active package. The complete previous task remains recoverable in Git history
and the local repair archive. No historical output is an acceptance target.

## Public contract and acceptance

The instruction, analysis/method contract, output/status schema and downstream
measurement kernel are public. Participants submit all event/trial identities,
condition averages, rejection receipts and signed participant/group results.
The private verifier authenticates original bytes and reconstructs the
preprocessing independently using direct FDT decoding and an analytic FIR.
The oracle uses MNE reading/filtering. Shared bounded MAT parsing and public
downstream measurement arithmetic are disclosed; these are not two independent
implementations of the endpoint estimator.

Submitted source-close condition means are the sole downstream numerical
authority. Their difference, participant descriptors and group intervals are
recomputed from those means. Source-canonical endpoint scalars are not a
second acceptance condition. Missing conditions/onsets remain explicit and
null the corresponding complete-cohort summary; constant defined endpoints
permit point intervals. No sign, variability, significance, onset separation,
paper-number match or prose keyword is required.

Scoring is binary. Manufactured and genuine-output mutation QA are authoring
checks, not hidden demands on a valid submission's tolerance or size headroom.
Optional cluster analyses are ungraded and only support cluster-level inference.

## Validation and interpretation boundary

See authoring/REPAIR_STATUS.md for the exact current local validation state.
Source authentication, fixture tests, independent numerical agreement, oracle
reward and model difficulty are separate evidence tiers. Model calibration is
not performed or inferred by this repair. No claim that this task defeats Sol
or reproduces the paper's published endpoint values is made.
