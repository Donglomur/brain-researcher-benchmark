# Original-slot integrity for primary choice scoring

This implementation closes a specific complete-support defect in NEURAL-059's
retained scorer. `evaluation._preparation` validates the cases it receives but
does not join them to the retained original trial slots. Deleting an eligible
test case from a prepared session can therefore reduce its expected support
without a scorer failure. A renamed case or altered preceding-trial relation
can likewise become the scorer's new expected identity.

`support.py` reconstructs the required eligible-case list from the original
slots before calling the unchanged probability scorer. It checks:

- The exact ordered 29-session, 13-animal, seven-laboratory roster.
- The complete original-slot order, raw-to-sorted bijection and inverse.
- The one-to-one relationship between eligible slots and cases, including the
  specified SHA-256 case identity and all preparation census fields.
- Recorded choice, stimulus, block and count/log-count joins to each case.
- The half-open one-second movement window and whole-window split containment.
- History from the immediately preceding **original** trial, including an
  excluded no-response trial. Feedback must be strictly before the cutoff.
  A preceding excluded trial may supply history without a retained case ID.

It calls the retained scorer only after these checks pass. Log loss remains
primary; Brier score, balanced accuracy and AUC retain their original definitions,
with pooling within animal and equal weighting of all 13 animals. SH, SHN, SBH,
SBHN and F/I/R identities remain those of the retained implementation. No actor,
reference fit, participant interface or model invocation is added.

The implementation is primary-observation-only. Diagnostic permutations change
labels or neural features intentionally and must continue through the original
diagnostic contract. Passing this validator is internal consistency evidence,
not recording authentication: jointly rewriting the original slots and cases
cannot be detected without an independently authenticated source. Spike-domain
containment and individual spike counting also require the original source;
the prepared object cannot independently prove them.

## Operator use

Inputs and full output contain protected targets and must remain in the operator
workspace outside Git and participant mounts. The CLI reads explicit JSON lists
for the full prepared cohort, captured predictions, and pre-query method
commitments. The latter two formats are the retained `score_panel` formats.
It rejects duplicate JSON keys, limits aggregate input and output bytes, writes
a new mode-0600 output, and prints only its hash and byte count.

```sh
python3 -I -B score.py \
  --prepared /operator/prepared.json \
  --predictions /operator/predictions.json \
  --methods /operator/methods.json \
  --output /operator/new-primary-score.json \
  --max-input-bytes SELECTED_INPUT_CAP \
  --max-output-bytes SELECTED_OUTPUT_CAP
```

The capitalized ceilings must be explicit positive integer selections consistent
with the actual frozen run and its resource authorization. There are no data or
runtime acquisition defaults. Successful output remains
`source_only_unqualified`, with `scientific_qualification=false` inherited from
the original scorer.

The four unchanged source files loaded from `registered-runtime` are byte-pinned
in `_retained.py`; their scientific arithmetic is not copied or modified. A
future reviewed source change requires an explicit pin revision.

## Verification and remaining work

`test_support.py` uses tiny generated original-slot records across the complete
literal roster. It includes the historical omission counterexample, independent
constant-probability endpoint arithmetic, no-response predecessor history,
cutoff equality, identity/axis corruption, and input-parser failures. Generated
controls establish software behavior only. Run these through the coordinated
lightweight test pool; no authentic recordings or historical private targets
are needed.

The package has not extracted any authentic session, reconciled the unresolved
generating-source revision, authenticated the full cohort, run a reference or
actor, or delivered direct/viewer participant modes. The existing exposed
93-query history remains unchanged. This is a new optional protected scoring
entrypoint; selecting it in the canonical registration and existing process
composition is an integration proposal, not a change made by this package.
