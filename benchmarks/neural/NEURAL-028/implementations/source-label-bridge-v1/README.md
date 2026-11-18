# NEURAL-028 source stimulus-label bridge

The author code selects a category through `UniqWalls` and `stim_id`, then compares that selected wall identity with `ft_WallID` or `WallName`. The existing evaluator instead requires integer stimulus categories. This component makes that translation explicit; a wall identifier such as17 is never assumed to mean category17. See the pinned [author utility source](https://raw.githubusercontent.com/MouseLand/zhong-et-al-2025/ba64ac697f5d9914926baac79399e80707a5f3a6/utils.py), functions `Get_dprime_selective_neuron` and `Get_dprime_rewPred_neuron`.

The input is an **operator-provided JSON projection**, not a native NPY file. This module does not unpickle, extract data, fit a model, evaluate neural effects or deliver a participant access mode. Native source authentication, session/animal/phase mapping and the complete cohort remain unresolved. Neither successful generated tests nor a well-formed SHA256 declaration establishes those properties.

## Input and output

`project_labels(source)` accepts exactly the following top-level fields:

- `schema`: `neural028-source-label-input/v1`.
- `task_id`: `NEURAL-028`; `source_revision`: `ba64ac697f5d9914926baac79399e80707a5f3a6`.
- `source_asset_sha256`: the operator's declared native behavior-asset digest; it is not verified here.
- `session_id`, explicit `trial_index_base` (0 or1), and `neural_frame_count`.
- `behavior`: exactly `UniqWalls`, `stim_id`, `WallName`, `ft_WallID`, `ft_trInd`, and `ntrials`.

The mapping must be unambiguous, include categories0 and2, and preserve every frame and declared trial. Wall identities may be nonempty JSON strings or integers; bools and other identity types are rejected. Integral floating frame indices are accepted, but the index base is never inferred. Unknown labels, missing trials, out-of-range/nonfinite indices, frame/trial disagreement or unequal frame counts refuse the projection. No observations are filtered, truncated or renumbered beyond the explicitly declared index-base conversion. If native data require outside-behavior frame handling or additional source types, that requires a separately reviewed extraction policy; refusal must not be bypassed by silently dropping rows.

The output provides `evaluator_fields.trial_id`, `stimulus_id` and `trial_stimulus_id`, the complete declared source mapping, source-projection digest, original index-base declaration and explicit zero-discard counts. These fields can feed the existing evaluator only after its other array, cohort and protocol requirements are fulfilled. The evaluator and numerical-claim checker are unchanged.

```sh
python3 -I -S -B label_bridge.py --input /operator/label-projection.json --output /operator/labels.json
```

CLI input defaults to an8MiB limit; an operator may select a positive bound up to64MiB with `--max-input-bytes`. Output creation is exclusive. Input/output must differ. This is an input-size bound, not an admitted native execution budget or an OS security boundary.

## Source clarification and remaining limits

The pinned [processing notebook](https://raw.githubusercontent.com/MouseLand/zhong-et-al-2025/ba64ac697f5d9914926baac79399e80707a5f3a6/data_process_script.ipynb) documents frame timestamps (`ft`), nominal3.17Hz acquisition and outside-behavior missing trial indices. That narrows the earlier timing uncertainty: timestamp fields are documented, while native values, units and alignment remain unverified. It does not justify exact-time inference in the present frame/position contract.

The source notebook and utility text were observed through the primary web reader on2026-11-18. No new raw-source hash, author execution or data payload authentication is claimed. The PMC source page returned a browser challenge. No change to the canonical task, scientific endpoint, access-mode status or readiness is proposed.

## Validation

The generated controls exercise nonidentity and reordered category maps, string identities, explicit one-based conversion, ambiguous and missing source mappings, complete trial/frame support, malformed indices, frame/trial disagreement, source commitments, answer-bearing extra fields, bounded JSON input and immutable CLI output. They contain no native measurements and establish only the label translation's software behavior. For integration, enroll the task-local unittest file in the component's CI command; current central enrollment is unchanged.
