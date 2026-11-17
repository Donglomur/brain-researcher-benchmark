# Calcium-state task prompts

These are future participant prompts. No authentic packet is admitted and no
participant run is authorized by this file. The evaluator must first close all
admission gates in CONTRACT.json and freeze equal resource limits for both modes.

## Shared scientific question and information

Predict the independently annotated state for every supplied calcium window in
each held-out animal. Decide whether population organization contributes evidence
beyond global activity and acquisition context. Treat natural sleep and anesthesia
as distinct regimes. Quiet wake is a distinct sleep label; state code1 has different
meanings in the two regimes. The packet uses named labels, not ambiguous raw codes.

You receive complete training/validation cases and their labels, the declared
outer-fold assignment, signal units/sampling metadata, a neutral mathematical
specification, the paper context, and the same allowed Python/reference tools.
Each candidatecase uses an opaque evaluator-keyed identifier. You receive neuron-by-relative-frame signal windows with authenticated samplingrate/units and, only if the spatialcontract requires them, neuroncoordinates. The natural-sleep versus anesthesia regime is an explicit permittedcontext and is also supplied to the metadata-onlybaseline. You receive no absolute frame offsets, sourcefilenames, animalidentifiers, state-specificpaths, used_frame lists or acquisitionorder. Test labels and expected scores are private. You may not infer them from filenames,
metadata fields, absolute session order, archive paths, or Internet retrieval.
All preprocessing and tuning use training/validation animals only. Test animals
are not unlabeled fit material. The complete context/guard convention is binding.

Submit one JSON object matching `calcium-state-predictions-v1`. For each exact
case_id, emit all named probabilities for its regimen, summing to1. Sleep fields
are awake, quiet_wake, nrem, rem. Anesthesia fields are awake, anesthesia. Include
every case exactly once. Do not include labels, subjects, narrative or extra keys
in the prediction file. Also supply a separate short analysis explaining the
signal evidence, nuisance controls, held-animal limits and alternative explanations.
Narrative scientific correctness is reviewed separately; it is not folded into
the probability score by an arbitrary rubric or LLM judge.

The primary score averages state recalls within regimen, regimens within animal,
then animals. The evaluator also reports log loss, class coverage, frame exclusions
and paired differences from its fixed global-activity reference. Improvement in
this prediction endpoint does not demonstrate a consciousness mechanism or
anatomical connectivity.

## Fixed-program mode

Using the shared training/validation packet, implement and commit one reusable
prediction program before the evaluator reveals held-out signal arrays. Your
program will be run separately for every outer fold under the declared limits.
It must write all probabilities before any private grading occurs. No manual
post-test changes or target-dependent retry is allowed.

## Interactive-investigation mode

Using the same training/validation packet and tools, investigate each held-out
animal's signal arrays under the same total resource budget. You may choose
analyses and run the allowed references, but cannot fit or tune on held-out data
or receive its labels or scores. Commit all outputs once before private grading.
Log tool activity so any gain can be distinguished from extra computation,
information or case selection.

## Optional official-code information arm

This arm is currently held because code redistribution permission is unresolved.
If later admitted, give exactly the same pinned official source to both workflow
modes. Keep paper/data-only and paper/data/code conditions separate; do not quietly
give only one mode the authors' implementation or saved results.
