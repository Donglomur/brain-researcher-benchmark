# PAPER-FIND-REP-003 initial evaluator v1

This component scores normalized held-out joint-angle predictions for all ten source M1/S1 imaging sessions against a train-only direction/time phase template. It preserves the author's variance-explained metric, reports a separate R² diagnostic, checks whole-trial folds and exact trial identities, and summarizes paired effects at the five-mouse level. A separate command reconstructs the source optogenetic contact-timestamp histogram for the two optogenetic mice; its interpretation as cue-relative timing remains unresolved.

Dependencies: Python 3 and NumPy. The implementation performs no installation or network access. From this package directory:

```sh
python3 evaluator.py decode /absolute/protected-reference.json --submission /absolute/predictions.json --output /absolute/report.json
python3 evaluator.py opto /absolute/opto-reference.json --output /absolute/opto-report.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

See the [full task documentation](../../docs/initial-evaluator-v1.md) for the exact normalized input schemas, source pins, trial eligibility, prospective comparator and aggregation policies, rights, and information boundaries. `provenance.json` maps implemented semantics to the pinned paper/code contract. Tests use generated engineering controls only.

This is a scoring component, not a native MAT loader, neural-model fitting pipeline, full-paper reproduction, or scientifically qualified benchmark. Native completeness of the ten imaging sessions, event locking, source-model parity, protected-reference provisioning, intervention trajectories, native MATLAB parity and scientific grading remain unqualified. The bounded optogenetic population audit below does not clear those gates. Outputs explicitly retain `scientifically_qualified: false` and `full_contract_complete: false`.

The separate `native_clock_audit.py` now checks the exact native optogenetic file's complete population and event-clock lineage using SciPy. It emits an admission receipt only. In the released data, `grabTimeC - waterTime == grabRT`; the source plot uses `grabTimeC / 1000` without that subtraction. The [clock audit section](../../docs/initial-evaluator-v1.md#native-optogenetic-clock-audit) records the source discrepancy and command. Scorer calculations remain unchanged.
