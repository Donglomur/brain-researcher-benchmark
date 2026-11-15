# Local engineering validation

The portable source passed all 31 invented-data controls on macOS with Python 3.11.6: one invocation of the 28 analytical controls, followed by one invocation of the three numerical-boundary controls. Both returned exit code 0; their owned worker groups were reaped and absent. No retry was used.

The checks exercise complete 56-cell/560,000-null-profile traversal, malformed or incomplete streams, protected-binding refusal, and explicit overflow, subnormal and strict-tail boundary behavior. Scalar agreement within tolerance does not imply exact strict-tail agreement.

`PROVENANCE.json` preserves the earlier source-freeze snapshot, when these portable controls were still unrun. This note records the subsequent local execution on 2026-11-14. GitHub CI repeats the same 28-then-3 sequence and uploads its original streams, statuses and generated evidence.

These results concern invented scalar/stream inputs. No authentic neural arrays, NumPy matrix reference execution, model evaluation, arbitrary-program isolation validation or scientific benchmark qualification is established by this component.
