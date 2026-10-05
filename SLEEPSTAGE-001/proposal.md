# SLEEPSTAGE-001: subject-held-out sleep-staging baseline

## Scientific scope

An easy method control on six original Sleep-EDF age-cohort recordings (subjects
0–5, night 1). The task measures five-class random-forest staging accuracy and
pooled Cohen kappa when one subject is held out. Its acquired EEG and expert
hypnograms are real; the crop, feature recipe and classifier are declared modern
analysis choices.

The original annotations follow Rechtschaffen–Kales. Combining stages 3 and 4
into N3 yields the declared five labels, not a new AASM expert rescoring. This
task does not reproduce Kemp et al. (2000)'s neuronal feedback/slow-wave result,
and it does not establish clinical or population-wide performance. The age-cohort
source is the Sleep Cassette study; the data-resource citation alone does not
make the random-forest endpoint a result from the cited paper.

## Immutable inputs and execution

The twelve unmodified PSG/hypnogram EDFs are identified in the public manifest.
Their expected SHA256 values come from the primary PhysioNet version-1.0.0
checksum file obtained before download. The build uses the officially documented
public S3 mirror for transport, with exact URL/identity allowlists and the same
checksums. ODC Attribution 1.0 licensing and source attribution are retained.
The task and verifier run offline; no dataset-cache mount or simulated fallback
is required. The same raw source bundle can serve AASMSTAGE-001, but the two tasks
have different feature/classifier/metric contracts and cannot share references.

## Public analysis and verification

The instruction publishes annotation-index cropping, complete 30-second epoch
selection, channel order, Welch window/segment/DC handling, normalized-bin feature
definition, RF settings and subject-wise held-out unit. Subject and epoch order
are pinned for the seeded forest. All source epoch IDs and labels are retained.

The sleepedf-loso-v2 bank is built only from a real repaired oracle execution.
Its builder reopens the hash-verified EDFs to validate epoch onsets/classes before
retaining predictions. The verifier compares source-keyed true and predicted
classes, recomputes every confusion cell, each subject's accuracy/kappa and pooled
metrics, and validates the public source/estimator metadata.

The earlier grade could accept a joint permutation of confusion-matrix class
names, because accuracy and kappa do not change. Source-stage binding closes that
hole. Score-preserving predicted-class mutations are also rejected. Row order,
equivalent integral numeric formats, extra columns and non-English prose are
accepted. Only disclosed rounding tolerances remain; there is no minimum accuracy,
required variability, hidden random-split contrast, or keyword gate.

## Validation boundary

The maintainer retains raw-data oracle outputs, feature receipts, independent
manual epoch/SciPy-Welch checks, actual-output adversarial fixtures and final
clean-commit Harbor receipts outside the task image. See REPAIR_STATUS.md and the
external receipt for measured status. Shared EDF readers/classifier libraries
limit the independence of secondary checks.

Passing these tests supports numerical agreement with this particular public
method contract. It does not prove how an agent trained its model, replicate an
original paper finding, or establish model difficulty. No Sol/frontier calibration
has been run; the public reference history requires contamination-aware later
evaluation. Resource contract: 2 CPUs, 8 GiB RAM, no GPU.

Sources: https://physionet.org/content/sleep-edfx/1.0.0/
and the explicitly adapted MNE sleep-staging tutorial:
https://mne.tools/1.12/auto_tutorials/clinical/60_sleep.html
