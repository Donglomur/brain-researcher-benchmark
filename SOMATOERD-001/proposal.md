# SOMATOERD-001: fixed-sensor total beta-power method control

This task retains the original public somato MEG acquisition and makes the
estimator explicit. Pfurtscheller & Lopes da Silva (1999), section 3.1/Figure 3,
provides the power-averaging/percent-change method anchor, not an empirical
source for this recording or a numerical target. The four sensors, Morlet
settings and time windows are task-defined. Total trial power is not isolated
induced activity; no contralateral cortical localization or exact onset is claimed.

Original archive version 8 and every selected file are checksum-bound. Only the
raw MEG and necessary provenance/sidecars enter the final runtime image, which is
fully offline. Source metadata identify Lauri Parkkonen/PDDL. Do not inherit a
different license or byte identity from a related anonymized BIDS release.

The numerical contract and output schema are public in `instruction.md` and
`environment/method_contract.json`. The verifier requires complete event identity,
dense trial-mean power, per-trial window power, full percentage curve and internally
consistent headline/metadata. No forced sign, old effect-size band, correlation
shortcut, prose keyword or magic trial count is a correctness gate. The reference
must be regenerated from the pinned acquisition, not relabeled from legacy output.

Role: **easy/method control**, with model difficulty unmeasured. Local engineering
validation does not establish population physiology, a paper finding, independent
data replication or Sol failure. See `REPAIR_STATUS.md` for actual execution
evidence and outstanding gates. No frontier calibration is claimed.
