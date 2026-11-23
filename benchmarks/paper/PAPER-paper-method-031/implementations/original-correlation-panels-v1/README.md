# FAST original correlation panels

This operator-side arithmetic component recomputes the structured correlation panels requested by PAPER-paper-method-031. It keeps every per-neuron or per-pixel result. It does not replace the existing prospective recording-disjoint evaluator, run a denoiser, or select preprocessing.

`evaluate_panel(support, reference, methods, candidate=None)` accepts an operator-frozen support roster and complete source-preprocessed trace packets. Its two independently named inputs are:

- `synthetic_fig3b`: the2/4/6/8ms conditions,10 neurons per condition, and raw plus DeepCAD-RT,SRDTrans,DeepVid,SUPPORT,FAST. All240 source coefficients remain separate. Synthetic frame counts must come from the original source; this component cannot recover them.
- `voltage_fig3f`:100 quantitative pixels,4982 original imaging frames, raw and FAST traces, and one pre-synchronized simultaneous electrophysiology trace. All200 coefficients remain separate. The separately displayed1000-pixel panel is not evaluated or substituted here.

The operator supplies ΔF/F traces after an independently qualified original baseline, pixel selection and synchronization procedure. No lag, sign, gain, smoothing or ROI is fitted here. Real electrophysiology is a temporal comparator, not clean fluorescence ground truth. Positive affine amplitude changes can preserve Pearson correlation; correlation alone does not establish amplitude fidelity.

The support object has exactly `schema`, `task_id`, `family`, `source_commit`, `source_provenance` and `strata`. Each stratum contains `condition_id`, `recording_id`, ordered unique `frame_ids` and ordered unique `unit_ids`. `support_sha256` validates these fields and returns a canonical commitment. The source-provenance string identifies an external operator record; its truth or original-paper lineage is not established by this component.

Each trace packet contains exactly `support_sha256` and `strata`. Every stratum repeats the frozen identities and adds unit-major `traces`. A voltage reference uses the single role ID `synchronized_electrophysiology`; synthetic clean references use the frozen neuron IDs. Methods must cover the entire original method set. The optional candidate is a separate packet and cannot replace FAST or a source control.

Outputs retain signed zero-lag Pearson coefficients, explicit constant-trace undefined states, per-trace float64 value commitments and optional per-unit candidate-minus-FAST differences. There is no scalar average, significance test, tolerance, binary reward or paper-win decision. No undefined entry is dropped. Packet identities, exact shape, complete original support and finite values are checked before comparison. Hash equality establishes a supplied value/ordering commitment, not authenticity or scientific validity.

Pearson preparation subtracts a finite midrange offset before scaling and mean centering. This preserves small representable dynamics on a nonzero baseline while avoiding overflow for traces spanning both float64 extremes. The offset is an algebraic device inside the unchanged correlation formula, not a fitted ΔF/F baseline or additional preprocessing. Trace commitments continue to hash the original supplied float64 values.

Only the standard library is needed. Run the focused generated controls from this directory with `python3 -I -S -B tests/test_correlations.py`. The16 controls include the complete real-panel shape, an independent orthogonal-vector calculation, negative correlations, constant references/predictions, large finite values, small dynamics on nonzero baselines, independent high-precision Pearson calculations, subnormal dynamics, omitted/reordered/extra-frame support and input immutability. These controls use invented engineering fixtures, never paper recordings or scientific observations.

This new component needs explicit registry/component CI enrollment before integration; its test file is not claimed to be discovered automatically. It is operator-only by default because it encodes author-code/source-panel knowledge. Paper+data and paper+data+author-code participant conditions must remain distinct.

Original data/ROI identities, ΔF/F baseline, synchronization, exact author route, numerical source baseline, full calcium/morphology/timing panels, candidate custody and dependence-aware inference remain unresolved. Supplied-panel arithmetic does not qualify reproduction, improvement, native execution or SOTA. See SOURCE.json for evidence and existing-component boundaries.
