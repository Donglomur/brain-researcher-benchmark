This additive operator component implements the three matched observation conditions already requested by NEURAL-034's evaluation contract. It selects the permitted signal before computing images or participant metadata, retains the original combined pixels, and rejects mixed-condition histories. It does not start participant processes, call models, qualify their contexts, or grade predictions.

| Condition | Visible observations | Explicitly unavailable |
| --- | --- | --- |
| `combined_calcium_behavior_v1` | Original twelve calcium traces and aligned binary behavior | Neither modality |
| `calcium_only_v1` | The same twelve calcium traces | Behavior lane |
| `behavior_only_v1` | The same binary behavior trace | All calcium lanes and calcium clipping statistics |

All conditions use the same selected seven held-mouse folds, 120 labeled training windows and 20 queries per fold, original case order, 300 sample centers from 0.05 to 29.95 seconds, 10 Hz sampling, and 140 required probabilities. They keep the 1400 by 820 canvas, time axis, included-lane positions, original gain range and typed actions. Omitted lanes are blank and explicitly marked unavailable; they do not display synthetic zero observations. The combined condition delegates to the unchanged renderer. The behavior-only view reports zero displayed calcium cells and no calcium clipping flags; these fields cannot depend on withheld calcium.

Choose one explicit `viewer-transport-v1` `Limits` value for the whole design. `Selection` is frozen and the participant has no modality-switch action. Each `Session` takes one previously authenticated operator `Packet`, a selection and a distinct opaque episode ID. `ProjectedPacket` accesses only the selected arrays and permitted training labels; it never calls the original combined `Packet.observation`. `ready_header` and `projection` bind the condition in participant-visible instructions and images. There are no query labels, fold identities, input hashes or source paths in those projections.

`finish_record` requires all twenty first-final responses and a successful finish. `collect` replays exactly seven histories under one condition, source identity, input binding and budget, then returns the original `schema_version=1` / `probabilities` submission. `collect_matched` requires all three conditions to use the same budget and distinct episode IDs across all 21 folds/conditions. Each returned submission contains the same 140 cases. Reusing these cases across conditions does not create 420 independent cases or additional benchmark IDs. Replay of authentic inputs requires separate execution admission.

These are operator histories, not transport attestations. The old combined-only restricted collector deliberately cannot accept them. A later participant adapter must bind the exact new projection and condition, the same frozen client/model and inference policy, fresh process/writable state and model context for every condition/fold, and complete image delivery. Episode-ID uniqueness and new in-memory state do not prove an external provider reset. This component matches the declared wall budget but does not enforce elapsed wall time; the participant transport must enforce it. The previously accepted macOS combined transport run provides no empirical qualification for these new arms. No source arrays, authentic renders, participants, models or private scoring were executed for this revision.

The source-only API is:

```python
limits = controls.T.Limits(161, 140, 64 * 1024**2, 900)
selection = controls.Selection("calcium_only_v1", limits)
session = controls.Session(authenticated_active_packet, selection, opaque_episode_id)
header = session.ready
response = session.handle({"action": "training", "index": 0})
public_header, png_bytes = controls.projection(response, selection.condition)
# Supply all required actions and twenty first-final probabilities, then finish.
record = session.finish_record()
# All seven same-condition records are needed for controls.collect(...).
```

The budget above matches the earlier fixed transport check and permits exactly all 120 training views, 20 query views, 20 answers and one finish. It leaves no extra gain/inspection actions. A future interactive experiment may predeclare a larger common budget using the existing `Limits` bounds, identically for all three conditions; it must not select budgets after observing outcomes.

Run `python3 -B test_controls.py` from this directory for the 13 portable generated controls. Full 21-fold enumeration and replay use generated protocol stubs; separate tests exercise real generated raster output, included-lane pixel geometry, hidden-modality invariance, clipping metadata, labels, frozen conditions, first-final responses, and refusal of altered/mixed/legacy histories. There are no skipped macOS tests because this suite does not claim OS isolation. It does not repeat the older transport or renderer suites.

The [policy](POLICY.json) records source provenance and the limits of modality attribution. The original scorer and six fixed reference streams are unchanged. Compare the same model and inference policy across the three viewer conditions; historical numerical-reference versus viewer differences also change representation and algorithm and cannot isolate modality. Even matched viewer differences do not establish causal biology, eliminate context/day-order or ROI/preprocessing confounding, or convert this tool-mediated task into a no-tools test.
