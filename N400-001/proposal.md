# N400-001: original-data target-word ERP method control

## Target and paper relationship

This easy method control measures each participant's signed unrelated-minus-related
target-word amplitude at CPz in the 300–500 ms window, then averages 12 participants
equally. It uses original ERP CORE N400 recordings, not synthetic EEG.

[Kappenman et al. (2021)](https://doi.org/10.1016/j.neuroimage.2020.117465), Figure 2
and Tables 1–2, anchors the contrast, electrode and window. The study's N400 sample
was 39 after exclusions. Its preprocessing included a 0.1 Hz Butterworth high-pass,
ICA and artifact/correctness/reaction-time rejection. The current task's 12-person
sample, explicit 0.1–30 Hz FIR and absence of those rejections are deliberate
departures. It must not be represented as reproducing the paper's cleaned numerical
finding. The 20 Hz low-pass used for selected paper measurements is not the mean
amplitude pipeline reproduced here.

## Original source and estimator visibility

Twenty-four OSF node `29xpq`, version-1 `shifted_ds` SET/FDT files are fixed by
original name, byte length, SHA256 and MD5. Build-time acquisition is bounded and
fails closed; analysis is fully offline. The files already include stimulus-delay
correction and downsampling. Source `EEG.event` records, not reconstructed trial
templates, determine identity and selection. Metadata inspection found 4,343 events,
including 1,440 targets, and no boundary events; each subject has 120 targets.
Subject 9 has one fewer prime event, which is preserved rather than repaired.

The processing contract was frozen before inspecting signal values. Target codes,
reference, FIR coefficients/padding, nearest-sample convention, epoch/baseline/
measurement offsets, structural exclusions and aggregation are public. No hidden
estimator, effect direction or requirement that pooled trials halve the result is
used. An optional pooled sensitivity is ungraded. Boundary-safe filtering and
epoching are defined, but this original source has no boundary challenge; such
branches are tested only with small mechanics fixtures.

Source headers lack explicit voltage-unit annotations. The analysis uses the
EEGLAB external-FDT microvolt convention, also implemented by the pinned MNE
reader's conversion to SI volts. Independent direct-FDT and reader-based routes
must agree before acceptance. This is a format convention, not a unit claim read
from a populated header field.

## Verification and limitations

Eight outputs expose every source event, continuous segment, target eligibility,
trial baseline and signed window value, all subject ERP curve samples, subject
amplitudes, source/method identity and headline arithmetic. All subjects must match;
opposing errors cannot cancel to pass a group-only test. Verification has no forced
negative effect, minimum variance, prose-keyword or optional-field regex gate.
Binary reward is stated explicitly. A separate original-source bank builder,
independent implementation and genuine-output mutation tests check numerical
lineage; reference-copy tests alone do not establish execution.

No ICA, behavioral exclusion, additional artifact rejection or amplitude clipping
is performed. Retaining contaminated trials is a limitation, not proof that they
are physiologically valid. A fixed subset's descriptive amplitude does not establish
population inference, artifact robustness, precise onset or coding-agent hardness.
This is labeled easy; no new Sol/model run is claimed.

## Primary provenance

- [ERP CORE paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC7909723/), methods 2.4–2.6,
  Figure 2 and Tables 1–2.
- [Pinned author N400 scripts](https://github.com/lucklab/ERP_CORE/tree/c18b43d70d791ca914d90410afe4ff06d6f7f429/N400):
  import/shift/downsample stage, channel operations, bin descriptors and ERP measurement.
- [OSF N400 node](https://osf.io/29xpq/), exact versioned identities in the manifest.
- [EEGLAB event-boundary documentation](https://eeglab.org/tutorials/ConceptsGuide/Data_Structures.html#event-boundaries).

The OSF node advertises CC-BY 4.0; the author repository's pinned `License.txt`
states CC-BY-SA 4.0. Both notices and author attribution are preserved. Local
validation does not resolve their scope or clear public dataset/image redistribution.

## Evidence state

See `REPAIR_STATUS.md` for completed execution checks. Historical proposal amplitudes,
pooled-halving assertions and unsupported validation claims have been withdrawn;
they are not calibration targets for the revised task.
