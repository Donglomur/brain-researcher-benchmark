# N2PC-001 — signed lateralization method control

This is a fixed twelve-person, original-data methods adaptation using the ERP
CORE N2pc visual-search recordings. It is not a reproduction of the paper's
cleaned N=35 characterization or its recommended 200–275 ms endpoint.

## Scientific target

Measure the signed PO7/PO8 contralateral-minus-ipsilateral mean over 200–300 ms.
Average trials within target field, give left and right fields equal weights,
then give the twelve fixed participants equal weights. Report the component
channel means and fixed PO8-minus-PO7 comparator without requiring any sign,
magnitude, cancellation, between-person variance or minimum negative count.

The mapping is public: left targets use PO8 as contralateral, right targets use
PO7. Difficulty must not come from withholding this definition or an estimator.

## Paper and adaptation boundary

[Kappenman et al. (2021), ERP CORE](https://doi.org/10.1016/j.neuroimage.2020.117465)
provides the public recordings and the component characterization. Table 1
identifies the paper's N2pc sample and PO7/PO8 readout; Table 2 specifies its
measurement window. The task retains its pre-existing twelve IDs, 200–300 ms
window, average EEG reference and all-target simplified analysis instead.
No ICA, ocular/behavioral/RT rejection, subject exclusion, display-delay
correction or resampling is silently inferred from the paper.

The independent reporting unit is the participant. The task does not establish
population generalization, artifact-free covert attention, significance, onset
or electrode localization. The simplified signal can contain ocular activity.

## Sources

The fixed IDs are 1,3,4,5,6,7,8,9,10,11,12,13. No claim is made that subject2 was
unreleased. The public source manifest binds all24 original raw BIDS-compatible
SET/FDT files to OSF version1, exact lengths, SHA256 and MD5. Original bytes total
1,051,981,416. Acquisition receipts remain external to the task.

Runtime is offline; the intended image contains authenticated originals and
public contracts, not derived EEG arrays or numerical answers. The source notice
retains both the component node's CC-BY4.0 and the official resource page's
CC-BY-SA4.0 notices without declaring which controls redistribution. Local
validation is not authorization to publish the data or image.

## Verification and delivery status

The repair replaces the old broad aggregate answer bank with authenticated
source epochs and complete signed arithmetic recomputation. Baseline, filter,
clock, retention and weighting rules must be public before numerical execution;
equivalent implementations are accepted within prospectively fixed tolerances.
Prose keywords and a preferred biological finding are not grading criteria.

See REPAIR_STATUS.md for measured validation and delivery evidence. The `easy`
metadata label marks this as a method control, not an empirical model-difficulty
estimate. No Sol/frontier calibration, public data release, push or merge is
implied by a local repair or an oracle passing its verifier.
