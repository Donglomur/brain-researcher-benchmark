# Honest PO8 adaptation and executable source pipeline

All 37 IDs and signed measurements/CIs are enforced. The task is explicitly shifted_ds,
no-ICA/no-extra-onset-filter adaptation rather than exact paper processing. The new source
regenerator validates original SET/FDT hashes, exact exclusions/channels, event coding,
average reference, .1–30Hz MNE filter, epoch/baseline and 150 µV rejection; it emits actual
trial exclusions/counts, units, version and hashes. Optional --compare-bake must numerically
match before treating the old bake as regenerated; no such match is claimed yet.

Run: python authoring/regenerate_from_sources.py --source-index SOURCES.json
--output NEW.npz --compare-bake environment/data/n170_diff_waves.npz
Source index maps exact subject IDs to original SET/FDT paths in the same directory.
Pending source-stage independent audit and actual all 37-source regeneration, paper-fidelity
decision if strict reproduction desired, offline container oracle/full fixtures.
A bounded CPU oracle on the retained baked waves passed all 7 current verifier checks.
Its output is retained separately. This does not validate the original-source-to-bake
pipeline, exact paper fidelity, or an in-container Harbor reward.
